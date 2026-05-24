from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pix.config import AppConfig
from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.models import AlipayGatewayMessage, AssetPackItem, CreditTransaction, GenerationBatch, GenerationJob, GenerationOutput, SystemSetting
from pix_web.payment_providers import _alipay_sign_content, _is_rsa_certificate, _rsa_sign
from pix_web.pipeline_adapter import asset_pipeline_input_from_job, run_job_pipeline
from pix_web.worker import process_next_job
from pix_web.system_settings import managed_pix_overrides_from_db


@pytest.fixture()
def client(tmp_path):
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'pix_web_test.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
        email_debug_codes=True,
    )
    app = create_app(settings)
    db = app.state.SessionLocal()
    try:
        bonus = db.scalar(select(SystemSetting).where(SystemSetting.key == "registration_bonus_credits"))
        if bonus is None:
            db.add(SystemSetting(key="registration_bonus_credits", value="0"))
        else:
            bonus.value = "0"
        db.commit()
    finally:
        db.close()
    with TestClient(app) as c:
        yield c


def _cors_preflight(client: TestClient, origin: str):
    return client.options(
        "/auth/register-code",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


def _register_and_login(client: TestClient, email: str = "admin@example.com") -> tuple[dict, dict]:
    code_response = client.post("/auth/register-code", json={"email": email})
    code = code_response.json()["debug_code"]
    user = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": "Admin",
            "verification_code": code,
        },
    ).json()
    token = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    ).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    return user, headers


def test_cors_allows_local_dev_origins(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'cors-local.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        response = _cors_preflight(c, "http://localhost:5174")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_cors_allows_configured_production_origin(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'cors-production.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
        cors_origins=("https://pix.example.com",),
    )
    app = create_app(settings)
    with TestClient(app) as c:
        response = _cors_preflight(c, "https://pix.example.com")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://pix.example.com"


def test_setup_status_and_bootstrap_admin(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'setup.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        status_response = c.get("/auth/setup-status")
        assert status_response.status_code == 200
        assert status_response.json()["needs_admin"] is True

        bootstrap = c.post(
            "/auth/bootstrap-admin",
            json={"email": "owner@example.com", "password": "password123", "display_name": "Owner"},
        )
        assert bootstrap.status_code == 200
        assert bootstrap.json()["user"]["role"] == "admin"
        headers = {"Authorization": f"Bearer {bootstrap.json()['access_token']}"}
        assert c.get("/auth/me", headers=headers).json()["email"] == "owner@example.com"
        assert c.get("/auth/setup-status").json()["needs_admin"] is False

        second = c.post(
            "/auth/bootstrap-admin",
            json={"email": "second@example.com", "password": "password123", "display_name": "Second"},
        )
        assert second.status_code == 409


def test_local_test_login_only_available_for_local_requests(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'local_test.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as local_client:
        setup = local_client.get("/auth/setup-status", headers={"Origin": "http://localhost:5173"})
        assert setup.status_code == 200
        assert setup.json()["local_test_login_available"] is True
        assert setup.json()["local_test_account_email"] == "local-test@pix.example"

        login = local_client.post("/auth/local-test-login", headers={"Origin": "http://localhost:5173"})
        assert login.status_code == 200
        local_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        me = local_client.get("/auth/me", headers=local_headers)
        assert me.status_code == 200
        assert me.json()["email"] == "local-test@pix.example"
        assert me.json()["role"] == "user"
        balance = local_client.get("/credits/balance", headers=local_headers).json()
        assert balance["available_credits"] == 1000

        wrong_password = local_client.post(
            "/auth/login",
            json={"email": "local-test@pix.example", "password": "password123"},
        )
        assert wrong_password.status_code == 401

    with TestClient(app, base_url="https://pix.example.com", client=("203.0.113.10", 50000)) as remote_client:
        remote_setup = remote_client.get("/auth/setup-status", headers={"Origin": "https://pix.example.com"})
        assert remote_setup.status_code == 200
        assert remote_setup.json()["local_test_login_available"] is False
        assert remote_setup.json()["local_test_account_email"] is None
        assert remote_client.post("/auth/local-test-login").status_code == 404
        assert remote_client.get("/auth/me", headers=local_headers).status_code == 401


def test_local_test_login_available_behind_local_reverse_proxy(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'local_proxy.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
    )
    app = create_app(settings)
    headers = {
        "Host": "localhost:8080",
        "Origin": "http://localhost:8080",
        "X-Forwarded-For": "172.17.0.1",
        "X-Forwarded-Host": "localhost:8080",
    }
    with TestClient(app, base_url="http://localhost:8080", client=("172.18.0.5", 50000)) as c:
        setup = c.get("/auth/setup-status", headers=headers)
        assert setup.status_code == 200
        assert setup.json()["local_test_login_available"] is True
        login = c.post("/auth/local-test-login", headers=headers)
        assert login.status_code == 200


def test_local_test_login_does_not_block_admin_bootstrap(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'local_bootstrap.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://localhost:8000", client=("127.0.0.1", 50000)) as c:
        assert c.post("/auth/local-test-login").status_code == 200
        setup = c.get("/auth/setup-status").json()
        assert setup["needs_admin"] is True
        assert setup["user_count"] == 1
        assert setup["admin_count"] == 0

        bootstrap = c.post(
            "/auth/bootstrap-admin",
            json={"email": "owner@example.com", "password": "password123", "display_name": "Owner"},
        )
        assert bootstrap.status_code == 200
        assert bootstrap.json()["user"]["role"] == "admin"
        assert c.get("/auth/setup-status").json()["needs_admin"] is False


def test_register_login_and_admin_adjust_credits(client: TestClient) -> None:
    user, headers = _register_and_login(client)

    assert user["role"] == "admin"
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"

    adjusted = client.post(
        f"/admin/users/{user['id']}/adjust-credits",
        headers=headers,
        json={"amount": 50, "note": "seed credits"},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["amount"] == 50

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 50
    assert balance["reserved_credits"] == 0


def test_register_requires_email_verification_code(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "needs-code@example.com",
            "password": "password123",
            "display_name": "Needs Code",
            "verification_code": "000000",
        },
    )

    assert response.status_code == 422
    assert "验证码" in response.json()["detail"]


def test_register_rejects_wrong_email_verification_code(client: TestClient) -> None:
    code_response = client.post("/auth/register-code", json={"email": "wrong-code@example.com"})
    code = code_response.json()["debug_code"]
    wrong_code = "000000" if code != "000000" else "000001"

    response = client.post(
        "/auth/register",
        json={
            "email": "wrong-code@example.com",
            "password": "password123",
            "display_name": "Wrong Code",
            "verification_code": wrong_code,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "验证码错误"

    ok = client.post(
        "/auth/register",
        json={
            "email": "wrong-code@example.com",
            "password": "password123",
            "display_name": "Wrong Code",
            "verification_code": code,
        },
    )
    assert ok.status_code == 200


def test_register_code_returns_debug_code_for_console_provider(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'console_email.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
        email_provider="console",
        email_debug_codes=False,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        response = c.post("/auth/register-code", json={"email": "console@example.com"})

    assert response.status_code == 200
    assert response.json()["debug_code"]


def test_register_code_reports_smtp_delivery_failure(tmp_path) -> None:
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'smtp_email.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
        email_provider="smtp",
        smtp_host="",
        smtp_from="Pix <noreply@example.com>",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        response = c.post("/auth/register-code", json={"email": "smtp-fail@example.com"})

    assert response.status_code == 503
    assert "SMTP 配置不完整" in response.json()["detail"]


def test_register_code_rejects_existing_email(client: TestClient) -> None:
    _user, _headers = _register_and_login(client, "existing@example.com")

    response = client.post("/auth/register-code", json={"email": "existing@example.com"})

    assert response.status_code == 409
    assert response.json()["detail"] == "邮箱已注册"


def test_register_code_resend_is_throttled(client: TestClient) -> None:
    first = client.post("/auth/register-code", json={"email": "throttle@example.com"})
    second = client.post("/auth/register-code", json={"email": "throttle@example.com"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


def test_admin_settings_metadata_secret_masking_and_pix_override(client: TestClient) -> None:
    _user, headers = _register_and_login(client, "settings-admin@example.com")

    settings_response = client.get("/admin/settings", headers=headers)
    assert settings_response.status_code == 200
    settings_payload = settings_response.json()
    image_key = next(item for item in settings_payload if item["key"] == "pix.api.image_api_key")
    assert image_key["secret"] is True
    assert image_key["category"] == "模型与 API"
    assert image_key["value"] == ""

    update = client.put(
        "/admin/settings/pix.api.image_api_key",
        headers=headers,
        json={"value": "sk-test-managed"},
    )
    assert update.status_code == 200
    assert update.json()["masked"] is True
    assert update.json()["value"] == ""

    session_factory = client.app.state.SessionLocal
    with session_factory() as db:
        overrides = managed_pix_overrides_from_db(db)
    assert overrides["api"]["image_api_key"] == "sk-test-managed"


def test_admin_test_email_uses_effective_settings(client: TestClient) -> None:
    _admin, headers = _register_and_login(client, "mail-admin@example.com")

    response = client.post("/admin/settings/test-email", headers=headers, json={"email": "mail-target@example.com"})

    assert response.status_code == 200
    assert response.json()["debug_code"]


def test_admin_settings_reject_non_admin(client: TestClient) -> None:
    _admin, _admin_headers = _register_and_login(client, "settings-owner@example.com")
    _user, user_headers = _register_and_login(client, "settings-user@example.com")

    response = client.get("/admin/settings", headers=user_headers)

    assert response.status_code == 403


def test_admin_can_manage_credit_packages(client: TestClient) -> None:
    _admin, headers = _register_and_login(client, "packages-admin@example.com")

    created = client.post(
        "/admin/packages",
        headers=headers,
        json={
            "key": "tiny",
            "name": "Tiny",
            "credits": 10,
            "amount_cents": 100,
            "currency": "cny",
            "enabled": True,
            "sort_order": 5,
        },
    )
    assert created.status_code == 200
    assert created.json()["key"] == "tiny"

    disabled = client.put(
        "/admin/packages/tiny",
        headers=headers,
        json={
            "name": "Tiny",
            "credits": 10,
            "amount_cents": 100,
            "currency": "cny",
            "enabled": False,
            "sort_order": 5,
        },
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    public_keys = {item["key"] for item in client.get("/billing/packages").json()}
    assert "tiny" not in public_keys


def test_admin_dashboard_requires_admin_and_reports_counts(client: TestClient) -> None:
    admin, admin_headers = _register_and_login(client)
    user, user_headers = _register_and_login(client, "player@example.com")

    assert client.get("/admin/dashboard", headers=user_headers).status_code == 403
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=admin_headers, json={"amount": 50})
    client.post("/jobs", headers=user_headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})
    client.post("/jobs", headers=user_headers, json={"job_type": "text_to_image", "prompt": "pixel dog"})
    client.post(f"/admin/users/{admin['id']}/adjust-credits", headers=admin_headers, json={"amount": 50})
    order = client.post("/billing/orders", headers=admin_headers, json={"package_key": "starter"}).json()
    client.post(f"/billing/mock-pay/{order['id']}", headers=admin_headers)

    image = Image.new("RGB", (4, 4), (20, 30, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    client.post("/uploads/image", headers=admin_headers, files={"file": ("icon.png", buffer.getvalue(), "image/png")})

    dashboard = client.get("/admin/dashboard", headers=admin_headers)

    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_users"] == 2
    assert body["jobs_today"] == 2
    assert body["pending_jobs"] == 2
    assert body["orders_paid_today"] == 1
    assert body["uploads_today"] == 1
    assert body["credits_recharged_today"] >= order["credits"]


def _rsa_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def test_alipay_rsa_certificate_filter_ignores_unsupported_public_key() -> None:
    class UnsupportedPublicKeyCert:
        signature_algorithm_oid = SimpleNamespace(_name="SM2-with-SM3")

        def public_key(self):
            raise RuntimeError("unsupported public key algorithm")

    assert _is_rsa_certificate(UnsupportedPublicKeyCert()) is False



def _rsa_key_pair_with_cert(common_name: str = "Alipay Test") -> tuple[str, str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Pix Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    return private_pem, public_pem, cert_pem


def test_alipay_checkout_and_webhook_are_idempotent(client: TestClient) -> None:
    private_pem, public_pem = _rsa_key_pair()
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        public_base_url="https://pix.example.com/api",
        alipay_app_id="app-id",
        alipay_private_key=private_pem,
        alipay_public_key=public_pem,
    )
    _user, headers = _register_and_login(client)
    starting_credits = client.get("/credits/balance", headers=headers).json()["available_credits"]
    checkout = client.post(
        "/billing/checkout",
        headers={**headers, "Origin": "https://pix.example.com"},
        json={"package_key": "starter", "provider": "alipay"},
    )

    assert checkout.status_code == 200
    body = checkout.json()
    assert body["provider"] == "alipay"
    assert "alipay.trade.page.pay" in body["payment_url"]
    assert "sign=" in body["payment_url"]

    order = body["order"]
    payment_params = parse_qs(urlsplit(body["payment_url"]).query)
    return_url = payment_params["return_url"][0]
    return_params = parse_qs(urlsplit(return_url).query)
    assert return_params["order_id"] == [str(order["id"])]
    assert return_params["return_to"] == ["https://pix.example.com"]
    form = {
        "out_trade_no": order["provider_order_id"],
        "trade_no": "ali-trade-1",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": f"{order['amount_cents'] / 100:.2f}",
        "sign_type": "RSA2",
    }
    sign_payload = {key: value for key, value in form.items() if key != "sign_type"}
    form["sign"] = _rsa_sign(private_pem, _alipay_sign_content(sign_payload))
    paid = client.post("/billing/webhook/alipay", data=form)
    again = client.post("/billing/webhook/alipay", data=form)

    assert paid.status_code == 200
    assert paid.text == "success"
    assert again.status_code == 200
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == starting_credits + order["credits"]


def test_alipay_return_redirects_to_frontend_billing(client: TestClient) -> None:
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        public_base_url="https://api.pix.example.com",
        frontend_base_url="https://www.pix.example.com",
        cors_origins=("https://www.pix.example.com",),
    )

    response = client.get(
        "/billing/return/alipay?order_id=6&return_to=https%3A%2F%2Fwww.pix.example.com",
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("https://www.pix.example.com/#/billing?")
    params = parse_qs(urlsplit(location).fragment.split("?", 1)[1])
    assert params["payment"] == ["alipay"]
    assert params["status"] == ["returned"]
    assert params["order_id"] == ["6"]

    unsafe = client.get(
        "/billing/return/alipay?order_id=7&return_to=https%3A%2F%2Fevil.example.com",
        follow_redirects=False,
    )
    assert unsafe.status_code == 303
    assert unsafe.headers["location"].startswith("https://www.pix.example.com/#/billing?")


def test_custom_alipay_checkout_and_webhook_recharges_exact_credits(client: TestClient) -> None:
    private_pem, public_pem = _rsa_key_pair()
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        public_base_url="https://pix.example.com/api",
        alipay_app_id="app-id",
        alipay_private_key=private_pem,
        alipay_public_key=public_pem,
    )
    _user, headers = _register_and_login(client, "custom-alipay@example.com")
    checkout = client.post("/billing/checkout", headers=headers, json={"custom_credits": 75, "provider": "alipay"})

    assert checkout.status_code == 200
    body = checkout.json()
    order = body["order"]
    assert order["credits"] == 75
    assert order["amount_cents"] == 743
    assert order["status"] == "pending"
    assert "Pix+Credits" in body["payment_url"] or "Pix%20Credits" in body["payment_url"]

    form = {
        "out_trade_no": order["provider_order_id"],
        "trade_no": "ali-custom-trade-1",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": f"{order['amount_cents'] / 100:.2f}",
        "sign_type": "RSA2",
    }
    sign_payload = {key: value for key, value in form.items() if key != "sign_type"}
    form["sign"] = _rsa_sign(private_pem, _alipay_sign_content(sign_payload))
    paid = client.post("/billing/webhook/alipay", data=form)

    assert paid.status_code == 200
    assert paid.text == "success"
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == 75


def test_custom_mock_order_can_be_created_and_admin_paid(client: TestClient) -> None:
    _admin, admin_headers = _register_and_login(client)
    _user, headers = _register_and_login(client, "custom-mock@example.com")

    options = client.get("/billing/custom-recharge-options")
    assert options.status_code == 200
    assert options.json()["min_credits"] == 10
    assert options.json()["base_package_amount_cents"] == 990

    order = client.post("/billing/orders", headers=headers, json={"custom_credits": 75, "provider": "mock"})
    assert order.status_code == 200
    order_body = order.json()
    assert order_body["credits"] == 75
    assert order_body["amount_cents"] == 743
    assert order_body["status"] == "pending"
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == 0

    paid = client.post(f"/billing/mock-pay/{order_body['id']}", headers=admin_headers)
    assert paid.status_code == 200
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == 75


def test_custom_recharge_rejects_invalid_credit_payloads(client: TestClient) -> None:
    _user, headers = _register_and_login(client)

    too_small = client.post("/billing/orders", headers=headers, json={"custom_credits": 9, "provider": "mock"})
    both_sources = client.post(
        "/billing/orders",
        headers=headers,
        json={"package_key": "starter", "custom_credits": 75, "provider": "mock"},
    )
    no_source = client.post("/billing/orders", headers=headers, json={"provider": "mock"})

    assert too_small.status_code == 422
    assert both_sources.status_code == 422
    assert no_source.status_code == 422


def test_alipay_app_gateway_message_is_verified_and_idempotent(client: TestClient) -> None:
    private_pem, public_pem = _rsa_key_pair()
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        alipay_app_id="app-id",
        alipay_private_key=private_pem,
        alipay_public_key=public_pem,
    )
    form = {
        "charset": "UTF-8",
        "biz_content": json.dumps({"audit_text": "通过", "service_code": "s1243453", "audit_status": "AGREE"}, ensure_ascii=False),
        "utc_timestamp": "1514210452731",
        "app_id": "app-id",
        "version": "1.1",
        "sign_type": "RSA2",
        "notify_id": "gateway-notify-1",
        "msg_method": "alipay.open.app.service.audit.notify",
    }
    sign_payload = {key: value for key, value in form.items() if key != "sign_type"}
    form["sign"] = _rsa_sign(private_pem, _alipay_sign_content(sign_payload))

    first = client.post("/billing/webhook/alipay/app-gateway", data=form)
    second = client.post("/billing/webhook/alipay/app-gateway", data=form)

    assert first.status_code == 200
    assert first.text == "success"
    assert second.status_code == 200
    db = client.app.state.SessionLocal()
    try:
        messages = list(db.scalars(select(AlipayGatewayMessage).where(AlipayGatewayMessage.notify_id == "gateway-notify-1")))
        assert len(messages) == 1
        assert messages[0].msg_method == "alipay.open.app.service.audit.notify"
        assert messages[0].biz_content_json["audit_status"] == "AGREE"
    finally:
        db.close()


def test_alipay_app_gateway_rejects_bad_signature_and_wrong_app(client: TestClient) -> None:
    private_pem, public_pem = _rsa_key_pair()
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        alipay_app_id="app-id",
        alipay_private_key=private_pem,
        alipay_public_key=public_pem,
    )
    form = {
        "charset": "UTF-8",
        "biz_content": json.dumps({"audit_status": "AGREE"}, ensure_ascii=False),
        "utc_timestamp": "1514210452731",
        "app_id": "app-id",
        "version": "1.1",
        "sign_type": "RSA2",
        "notify_id": "gateway-notify-bad",
        "msg_method": "alipay.open.app.service.audit.notify",
    }
    sign_payload = {key: value for key, value in form.items() if key != "sign_type"}
    form["sign"] = _rsa_sign(private_pem, _alipay_sign_content(sign_payload))

    wrong_app_form = {**form, "app_id": "other-app"}
    wrong_app_payload = {key: value for key, value in wrong_app_form.items() if key not in {"sign", "sign_type"}}
    wrong_app_form["sign"] = _rsa_sign(private_pem, _alipay_sign_content(wrong_app_payload))
    bad_signature = client.post("/billing/webhook/alipay/app-gateway", data={**form, "sign": "bad-signature"})
    wrong_app = client.post("/billing/webhook/alipay/app-gateway", data=wrong_app_form)

    assert bad_signature.status_code == 400
    assert "验签失败" in bad_signature.json()["detail"]
    assert wrong_app.status_code == 400
    assert "app_id 不匹配" in wrong_app.json()["detail"]


def test_alipay_certificate_checkout_and_webhook_are_idempotent(client: TestClient) -> None:
    private_pem, _public_pem, cert_pem = _rsa_key_pair_with_cert()
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        public_base_url="https://pix.example.com/api",
        alipay_app_id="app-id",
        alipay_private_key=private_pem,
        alipay_mode="certificate",
        alipay_app_cert=cert_pem,
        alipay_public_cert=cert_pem,
        alipay_root_cert=cert_pem,
    )
    _user, headers = _register_and_login(client, "alipay-cert@example.com")
    starting_credits = client.get("/credits/balance", headers=headers).json()["available_credits"]
    checkout = client.post("/billing/checkout", headers=headers, json={"package_key": "starter", "provider": "alipay"})

    assert checkout.status_code == 200
    body = checkout.json()
    query = parse_qs(urlsplit(body["payment_url"]).query)
    assert query["app_cert_sn"][0]
    assert query["alipay_root_cert_sn"][0]
    assert query["sign_type"] == ["RSA2"]

    order = body["order"]
    form = {
        "out_trade_no": order["provider_order_id"],
        "trade_no": "ali-cert-trade-1",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": f"{order['amount_cents'] / 100:.2f}",
        "sign_type": "RSA2",
    }
    sign_payload = {key: value for key, value in form.items() if key != "sign_type"}
    form["sign"] = _rsa_sign(private_pem, _alipay_sign_content(sign_payload))
    paid = client.post("/billing/webhook/alipay", data=form)
    again = client.post("/billing/webhook/alipay", data=form)

    assert paid.status_code == 200
    assert paid.text == "success"
    assert again.status_code == 200
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == starting_credits + order["credits"]


def _insert_succeeded_job(client: TestClient, user_id: int, prompt: str) -> int:
    db = client.app.state.SessionLocal()
    try:
        job = GenerationJob(
            user_id=user_id,
            client_request_id=f"test-pack-{uuid4().hex}",
            job_type="text_to_image",
            status="succeeded",
            prompt=prompt,
            params_json={},
            price_credits=1,
            finished_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.flush()
        run_dir = client.app.state.web_settings.storage_root / "runs" / f"job-{job.id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        image_path = run_dir / "pixel.png"
        image_path.write_bytes(b"fake-png")
        db.add(
            GenerationOutput(
                job_id=job.id,
                run_dir=str(run_dir),
                source_path=str(image_path),
                pixelized_path=str(image_path),
                meta_json_path=str(image_path),
            )
        )
        db.commit()
        return job.id
    finally:
        db.close()


def test_asset_pack_create_add_expand_and_capacity(client: TestClient) -> None:
    user, headers = _register_and_login(client, "pack-owner@example.com")
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 150, "note": "pack test"})
    first_job_id = _insert_succeeded_job(client, user["id"], "crystal")
    second_job_id = _insert_succeeded_job(client, user["id"], "ore")

    initial_quota = client.get("/packs/quota", headers=headers)
    created = client.post("/packs", headers=headers, json={"name": "玄幻材料"})
    blocked = client.post("/packs", headers=headers, json={"name": "第二个素材包"})
    expanded = client.post("/packs/expand", headers=headers)
    second_pack = client.post("/packs", headers=headers, json={"name": "第二个素材包"})

    assert initial_quota.status_code == 200
    assert initial_quota.json()["pack_limit"] == 1
    assert initial_quota.json()["pack_capacity"] == 100
    assert created.status_code == 200
    pack = created.json()
    assert pack["capacity"] == 100
    assert pack["item_count"] == 0
    assert blocked.status_code == 409
    assert expanded.status_code == 200
    assert expanded.json()["pack_limit"] == 2
    assert second_pack.status_code == 200

    added = client.post(f"/packs/{pack['id']}/items", headers=headers, json={"job_id": first_job_id})
    duplicate = client.post(f"/packs/{pack['id']}/items", headers=headers, json={"job_id": first_job_id})
    added_second = client.post(f"/packs/{pack['id']}/items", headers=headers, json={"job_id": second_job_id})

    assert added.status_code == 200
    assert duplicate.status_code == 200
    assert added_second.status_code == 200
    assert added_second.json()["item_count"] == 2
    downloaded = client.get(f"/packs/{pack['id']}/download", headers=headers)
    assert downloaded.status_code == 200
    with ZipFile(BytesIO(downloaded.content)) as archive:
        names = set(archive.namelist())
    assert any(name.endswith(f"crystal_{first_job_id}_03_pixelized.png") for name in names)
    assert any(name.endswith(f"ore_{second_job_id}_03_pixelized.png") for name in names)
    assert not any("preview" in name for name in names)
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == 51


def test_delete_gallery_work_removes_outputs_and_pack_references(client: TestClient) -> None:
    user, headers = _register_and_login(client, "delete-work@example.com")
    job_id = _insert_succeeded_job(client, user["id"], "delete me")
    pack = client.post("/packs", headers=headers, json={"name": "临时包"}).json()
    assert client.post(f"/packs/{pack['id']}/items", headers=headers, json={"job_id": job_id}).status_code == 200

    db = client.app.state.SessionLocal()
    try:
        output = db.scalar(select(GenerationOutput).where(GenerationOutput.job_id == job_id))
        assert output is not None
        run_dir = Path(output.run_dir)
        db.add(CreditTransaction(user_id=user["id"], type="consume", amount=-1, balance_after=0, job_id=job_id, note="delete-link"))
        db.commit()
    finally:
        db.close()

    deleted = client.delete(f"/jobs/{job_id}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert not run_dir.exists()
    assert client.get(f"/jobs/{job_id}", headers=headers).status_code == 404
    assert client.get(f"/packs/{pack['id']}/jobs", headers=headers).json() == []
    db = client.app.state.SessionLocal()
    try:
        assert db.scalar(select(AssetPackItem).where(AssetPackItem.job_id == job_id)) is None
        assert db.scalar(select(GenerationOutput).where(GenerationOutput.job_id == job_id)) is None
        assert db.scalar(select(GenerationJob).where(GenerationJob.id == job_id)) is None
        transaction = db.scalar(select(CreditTransaction).where(CreditTransaction.note == "delete-link"))
        assert transaction is not None
        assert transaction.job_id is None
    finally:
        db.close()


def test_delete_gallery_work_rejects_running_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client, "delete-running@example.com")
    db = client.app.state.SessionLocal()
    try:
        job = GenerationJob(user_id=user["id"], client_request_id=f"running-{uuid4().hex}", job_type="text_to_image", status="running", prompt="busy", params_json={}, price_credits=1)
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    deleted = client.delete(f"/jobs/{job_id}", headers=headers)

    assert deleted.status_code == 409


def test_asset_pack_keeps_saved_work_out_of_retention(client: TestClient) -> None:
    user, headers = _register_and_login(client, "pack-retention@example.com")
    saved_job_id = _insert_succeeded_job(client, user["id"], "saved forever")
    for index in range(12):
        _insert_succeeded_job(client, user["id"], f"ordinary {index}")
    pack = client.post("/packs", headers=headers, json={"name": "永久保存"}).json()
    assert client.post(f"/packs/{pack['id']}/items", headers=headers, json={"job_id": saved_job_id}).status_code == 200

    jobs = client.get("/jobs", headers=headers)
    pack_jobs = client.get(f"/packs/{pack['id']}/jobs", headers=headers)

    assert jobs.status_code == 200
    assert pack_jobs.status_code == 200
    assert any(job["id"] == saved_job_id for job in pack_jobs.json())
    assert len(jobs.json()) == 11


def test_batch_generation_no_longer_creates_asset_pack(client: TestClient) -> None:
    user, headers = _register_and_login(client, "batch-gallery@example.com")
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50, "note": "batch test"})
    payload = {
        "jobs": [
            {"job_type": "text_to_image", "prompt": "ruby", "client_request_id": f"batch-{uuid4().hex}"},
            {"job_type": "text_to_image", "prompt": "sapphire", "client_request_id": f"batch-{uuid4().hex}"},
        ],
        "batch_name": "should-not-create-pack",
        "mode": "text_to_image",
    }

    response = client.post("/jobs/batch", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["batch_id"] is not None
    assert client.get("/packs", headers=headers).json() == []


def test_wechat_checkout_is_disabled(client: TestClient) -> None:
    _user, headers = _register_and_login(client)
    starting_credits = client.get("/credits/balance", headers=headers).json()["available_credits"]
    checkout = client.post("/billing/checkout", headers=headers, json={"package_key": "starter", "provider": "wechat"})
    assert checkout.status_code == 422
    assert "微信支付已关闭" in checkout.json()["detail"]
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == starting_credits


def test_billing_order_mock_pay_and_idempotent_webhook(client: TestClient) -> None:
    user, headers = _register_and_login(client)

    packages = client.get("/billing/packages")
    assert packages.status_code == 200
    package_key = packages.json()[0]["key"]

    order = client.post("/billing/orders", headers=headers, json={"package_key": package_key})
    assert order.status_code == 200
    order_body = order.json()
    assert order_body["status"] == "pending"
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == 0

    paid = client.post(f"/billing/mock-pay/{order_body['id']}", headers=headers)
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    balance_after_pay = client.get("/credits/balance", headers=headers).json()["available_credits"]
    assert balance_after_pay == order_body["credits"]

    paid_again = client.post(f"/billing/mock-pay/{order_body['id']}", headers=headers)
    assert paid_again.status_code == 200
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == balance_after_pay

    event = {"order_id": order_body["id"], "event_id": "evt_same"}
    first_event = client.post("/billing/webhook/mock", json=event)
    second_event = client.post("/billing/webhook/mock", json=event)
    assert first_event.status_code == 200
    assert second_event.status_code == 200
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == balance_after_pay


def test_non_admin_cannot_mock_pay_order(client: TestClient) -> None:
    _admin, admin_headers = _register_and_login(client)
    _user, headers = _register_and_login(client, "buyer@example.com")
    package_key = client.get("/billing/packages").json()[0]["key"]
    order = client.post("/billing/orders", headers=headers, json={"package_key": package_key}).json()

    response = client.post(f"/billing/mock-pay/{order['id']}", headers=headers)

    assert response.status_code == 403
    assert client.post(f"/billing/mock-pay/{order['id']}", headers=admin_headers).status_code == 200


def test_create_job_reserves_credits_idempotently(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(
        f"/admin/users/{user['id']}/adjust-credits",
        headers=headers,
        json={"amount": 50},
    )

    payload = {
        "job_type": "text_to_image",
        "prompt": "pixel cat",
        "client_request_id": "same-click",
        "pixelize": {"output_size": [16, 16], "colors": 4, "preview_scale": 0},
    }
    first = client.post("/jobs", headers=headers, json=payload)
    second = client.post("/jobs", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["price_credits"] == 20
    assert first.json()["reserved_credits"] == 20

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 30
    assert balance["reserved_credits"] == 20


def test_create_job_rejects_sub16_asset_sizes(client: TestClient) -> None:
    _user, headers = _register_and_login(client)

    for size in ([12, 12], [8, 8], [16, 8]):
        response = client.post(
            "/jobs",
            headers=headers,
            json={
                "job_type": "text_to_image",
                "prompt": "tiny mushroom",
                "pixelize": {"output_size": size, "colors": 8},
            },
        )

        assert response.status_code == 422
        assert "16x16" in response.json()["detail"]


def test_create_asset_job_reserves_credits_and_stores_asset_params(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})

    response = client.post(
        "/jobs",
        headers=headers,
        json={
            "job_type": "asset",
            "prompt": "血气灵玉",
            "client_request_id": "asset-click",
            "pixelize": {"output_size": [16, 16], "colors": 12, "palette_mode": "auto"},
            "grid": {"mode": "extract"},
            "asset": {"name": "血气灵玉", "extra_prompt": "红色晶体，深色描边", "asset_kind": "ui_component", "subject_kind": "single_ui"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_type"] == "asset"
    assert body["prompt"] == "血气灵玉"
    assert body["price_credits"] == 20
    assert body["reserved_credits"] == 20
    assert body["params_json"]["asset"]["name"] == "血气灵玉"
    assert body["params_json"]["asset"]["extra_prompt"] == "红色晶体，深色描边"
    assert body["params_json"]["asset"]["asset_kind"] == "ui_component"
    assert body["params_json"]["asset"]["subject_kind"] == "single_ui"
    assert body["params_json"]["pixelize"]["palette_mode"] == "auto"
    assert "palette_mode" in body["params_json"]["pixelize_fields"]

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 30
    assert balance["reserved_credits"] == 20


def test_create_asset_job_rejects_sub16_sizes(client: TestClient) -> None:
    _user, headers = _register_and_login(client)

    response = client.post(
        "/jobs",
        headers=headers,
        json={
            "job_type": "asset",
            "asset": {"name": "小蘑菇"},
            "pixelize": {"output_size": [8, 8], "colors": 8},
        },
    )

    assert response.status_code == 422
    assert "16x16" in response.json()["detail"]


def test_create_job_enqueues_pending_job(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    calls: list[list[int]] = []

    def fake_enqueue(_settings, job_ids):
        calls.append(list(job_ids))
        return len(calls[-1])

    monkeypatch.setattr("pix_web.routers.jobs.enqueue_jobs", fake_enqueue)
    response = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})

    assert response.status_code == 200
    assert calls == [[response.json()["id"]]]


def test_admin_can_update_operational_settings(client: TestClient) -> None:
    _user, headers = _register_and_login(client)

    settings = client.get("/admin/settings", headers=headers)
    assert settings.status_code == 200
    payload = settings.json()
    assert {item["key"] for item in payload} >= {
        "generation_enabled",
        "max_pending_jobs_per_user",
        "daily_job_limit_per_user",
    }
    retired_pending_limit = next(item for item in payload if item["key"] == "max_pending_jobs_per_user")
    assert retired_pending_limit["value"] == "0"
    assert retired_pending_limit["editable"] is False

    updated = client.put("/admin/settings/daily_job_limit_per_user", headers=headers, json={"value": "2"})
    assert updated.status_code == 200
    assert updated.json()["value"] == "2"

    disabled = client.put("/admin/settings/max_pending_jobs_per_user", headers=headers, json={"value": "2"})
    assert disabled.status_code == 422


def test_non_admin_cannot_update_operational_settings(client: TestClient) -> None:
    _admin, _admin_headers = _register_and_login(client)
    _user, headers = _register_and_login(client, "user@example.com")

    response = client.put("/admin/settings/generation_enabled", headers=headers, json={"value": "false"})

    assert response.status_code == 403


def test_generation_disabled_blocks_job_creation(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    client.put("/admin/settings/generation_enabled", headers=headers, json={"value": "false"})

    response = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})

    assert response.status_code == 403


def test_blocked_prompt_terms_reject_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 100})
    client.put("/admin/settings/blocked_prompt_terms", headers=headers, json={"value": "blood, forbidden"})

    single = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "tiny blood sword"})
    assert single.status_code == 422

    batch = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "safe cat"}, {"job_type": "text_to_image", "prompt": "forbidden orb"}]},
    )
    assert batch.status_code == 422
    assert client.get("/jobs", headers=headers).json() == []


def test_pending_limit_no_longer_blocks_extra_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 100})

    first = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})
    second = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel dog"})

    assert first.status_code == 200
    assert second.status_code == 200


def test_batch_no_longer_respects_pending_limit(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 100})

    response = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "cat"}, {"job_type": "text_to_image", "prompt": "dog"}]},
    )

    assert response.status_code == 200
    assert len(client.get("/jobs", headers=headers).json()) == 2


def test_daily_limit_blocks_extra_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 100})
    client.put("/admin/settings/daily_job_limit_per_user", headers=headers, json={"value": "1"})

    first = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})
    second = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel dog"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_batch_create_jobs_reserves_atomically(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    calls: list[list[int]] = []

    def fake_enqueue(_settings, job_ids):
        calls.append(list(job_ids))
        return len(calls[-1])

    monkeypatch.setattr("pix_web.routers.jobs.enqueue_jobs", fake_enqueue)
    response = client.post(
        "/jobs/batch",
        headers=headers,
        json={
            "batch_name": "Test Pack",
            "mode": "text_to_image",
            "jobs": [
                {"job_type": "text_to_image", "prompt": "pixel cat", "client_request_id": "batch-a"},
                {"job_type": "text_to_image", "prompt": "pixel dog", "client_request_id": "batch-b"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_price_credits"] == 40
    assert body["batch_id"] is not None
    assert len(body["jobs"]) == 2
    assert {job["batch_id"] for job in body["jobs"]} == {body["batch_id"]}
    assert calls == [[job["id"] for job in body["jobs"]]]

    batches = client.get("/batches", headers=headers).json()
    assert batches[0]["name"] == "Test Pack"
    assert batches[0]["mode"] == "text_to_image"
    assert batches[0]["job_count"] == 2
    assert batches[0]["pending_count"] == 2
    assert batches[0]["total_price_credits"] == 40
    batch_jobs = client.get(f"/batches/{body['batch_id']}/jobs", headers=headers).json()
    assert len(batch_jobs) == 2
    assert {job["batch_id"] for job in batch_jobs} == {body["batch_id"]}

    _other, other_headers = _register_and_login(client, "other@example.com")
    forbidden = client.get(f"/batches/{body['batch_id']}/jobs", headers=other_headers)
    assert forbidden.status_code == 404

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 10
    assert balance["reserved_credits"] == 40


def test_batch_create_is_atomic_when_credits_are_insufficient(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    response = client.post(
        "/jobs/batch",
        headers=headers,
        json={
            "jobs": [
                {"job_type": "text_to_image", "prompt": "pixel cat"},
                {"job_type": "text_to_image", "prompt": "pixel dog"},
            ]
        },
    )
    assert response.status_code == 402
    assert client.get("/jobs", headers=headers).json() == []
    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 20
    assert balance["reserved_credits"] == 0


def test_batch_create_reuses_existing_idempotent_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 60})
    first = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "text_to_image", "prompt": "pixel cat", "client_request_id": "already"},
    ).json()
    response = client.post(
        "/jobs/batch",
        headers=headers,
        json={
            "jobs": [
                {"job_type": "text_to_image", "prompt": "pixel cat", "client_request_id": "already"},
                {"job_type": "text_to_image", "prompt": "pixel dog", "client_request_id": "new-one"},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["jobs"][0]["id"] == first["id"]
    assert body["total_price_credits"] == 20
    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 20
    assert balance["reserved_credits"] == 40


def test_update_batch_name_and_archive_status(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"batch_name": "Old Name", "jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()

    renamed = client.patch(f"/batches/{created['batch_id']}", headers=headers, json={"name": "New Name"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "New Name"
    assert renamed.json()["status"] == "active"

    archived = client.patch(f"/batches/{created['batch_id']}", headers=headers, json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    restored = client.patch(f"/batches/{created['batch_id']}", headers=headers, json={"status": "active"})
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    _other, other_headers = _register_and_login(client, "batch-manager-other@example.com")
    forbidden = client.patch(f"/batches/{created['batch_id']}", headers=other_headers, json={"name": "Hacked"})
    assert forbidden.status_code == 404


def test_delete_batch_allows_only_empty_batches(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()
    non_empty = client.delete(f"/batches/{created['batch_id']}", headers=headers)
    assert non_empty.status_code == 409

    session_factory = client.app.state.SessionLocal
    with session_factory() as db:
        empty = GenerationBatch(user_id=user["id"], name="Empty Pack", mode="mixed")
        db.add(empty)
        db.commit()
        empty_id = empty.id

    deleted = client.delete(f"/batches/{empty_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert client.get(f"/batches/{empty_id}/jobs", headers=headers).status_code == 404


def test_download_batch_zip_includes_successful_outputs(client: TestClient, tmp_path, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"batch_name": "Download Pack", "jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()

    run_dir = tmp_path / "download-run"
    run_dir.mkdir()
    source = run_dir / "01_source.png"
    pixel = run_dir / "03_pixelized.png"
    preview = run_dir / "04_preview.png"
    analysis = run_dir / "02_analysis.json"
    meta = run_dir / "meta.json"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(pixel)
    Image.new("RGBA", (4, 4), (0, 0, 255, 255)).save(preview)
    analysis.write_text("{}", encoding="utf-8")
    meta.write_text("{}", encoding="utf-8")

    def fake_run(_job, _settings, *, cfg=None):
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=source,
            pixel_path=pixel,
            preview_path=preview,
            analysis_path=analysis,
            meta_path=meta,
        )

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fake_run)
    process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    response = client.get(f"/batches/{created['batch_id']}/download", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
    job_id = created["jobs"][0]["id"]
    assert any(name.endswith(f"pixel_cat_{job_id}_01_source.png") for name in names)
    assert any(name.endswith(f"pixel_cat_{job_id}_03_pixelized.png") for name in names)
    assert not any("preview" in name for name in names)
    assert any(name.endswith(f"pixel_cat_{job_id}_02_analysis.json") for name in names)
    assert any(name.endswith(f"pixel_cat_{job_id}_meta.json") for name in names)

    _other, other_headers = _register_and_login(client, "download-other@example.com")
    forbidden = client.get(f"/batches/{created['batch_id']}/download", headers=other_headers)
    assert forbidden.status_code == 404


def test_download_batch_zip_requires_successful_outputs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()
    response = client.get(f"/batches/{created['batch_id']}/download", headers=headers)
    assert response.status_code == 409


def test_retry_failed_job_requeues_single_failed_job(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    starting_credits = client.get("/credits/balance", headers=headers).json()["available_credits"]
    created = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"}).json()

    def fail(_job, _settings, *, cfg=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)
    assert processed is not None
    assert processed.status == "failed"

    retry = client.post(f"/jobs/{created['id']}/retry", headers=headers)
    assert retry.status_code == 200
    body = retry.json()
    assert body["id"] != created["id"]
    assert body["status"] == "pending"
    assert body["prompt"] == "pixel cat"
    assert body["batch_id"] is None

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == starting_credits - 20
    assert balance["reserved_credits"] == 20


def test_retry_failed_job_requires_failed_status(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"}).json()

    retry = client.post(f"/jobs/{created['id']}/retry", headers=headers)
    assert retry.status_code == 409


def test_retry_failed_batch_jobs_requeues_into_same_batch(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    starting_credits = client.get("/credits/balance", headers=headers).json()["available_credits"]
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"batch_name": "Retry Pack", "jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()

    def fail(_job, _settings, *, cfg=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)
    assert processed is not None
    assert processed.status == "failed"

    retry = client.post(f"/batches/{created['batch_id']}/retry-failed", headers=headers)
    assert retry.status_code == 200
    body = retry.json()
    assert body["batch_id"] == created["batch_id"]
    assert body["total_price_credits"] == 20
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["batch_id"] == created["batch_id"]
    assert body["jobs"][0]["status"] == "pending"
    assert body["jobs"][0]["id"] != created["jobs"][0]["id"]

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == starting_credits - 20
    assert balance["reserved_credits"] == 20


def test_retry_failed_batch_requires_failed_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()
    retry = client.post(f"/batches/{created['batch_id']}/retry-failed", headers=headers)
    assert retry.status_code == 409


def test_retry_failed_batch_is_atomic_when_credits_are_insufficient(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()

    def fail(_job, _settings, *, cfg=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": -20})

    retry = client.post(f"/batches/{created['batch_id']}/retry-failed", headers=headers)
    assert retry.status_code == 402
    jobs = client.get(f"/batches/{created['batch_id']}/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"


def test_retry_failed_batch_rejects_other_users(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 20})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()

    def fail(_job, _settings, *, cfg=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    _other, other_headers = _register_and_login(client, "retry-other@example.com")
    retry = client.post(f"/batches/{created['batch_id']}/retry-failed", headers=other_headers)
    assert retry.status_code == 404


def test_asset_pipeline_adapter_uses_asset_defaults_and_keeps_config_isolated(tmp_path, monkeypatch) -> None:
    cfg = AppConfig()
    cfg.asset.pixel_size = (16, 16)
    cfg.asset.colors = 12
    cfg.asset.preview_scale = 12
    cfg.asset.image_quality = "low"
    cfg.asset.skip_vl = True
    cfg.asset.remove_bg = True
    cfg.asset.bg_tolerance = 26
    cfg.asset.auto_crop = True
    cfg.asset.palette_mode = "auto"
    cfg.asset.grid_mode = True
    cfg.image_gen.contact_sheet_enabled = True
    cfg.image_gen.prompt_guard_remote = True
    settings = WebSettings(storage_root=tmp_path / "storage")
    job = SimpleNamespace(
        id=42,
        job_type="asset",
        prompt="紫檀木",
        params_json={
            "asset": {"name": "紫檀木", "extra_prompt": "warm wood grain", "asset_kind": "ui_component", "subject_kind": "single_ui"},
            "request_fields": ["asset"],
            "pixelize_fields": [],
        },
    )

    inputs = asset_pipeline_input_from_job(job, settings, cfg)

    assert "紫檀木" in inputs.prompt
    assert "16×16 像素游戏UI组件" in inputs.prompt
    assert "单个UI" in inputs.prompt
    assert "主体：紫檀木" in inputs.prompt
    assert "warm wood grain" in inputs.prompt
    assert inputs.pixelize_params.output_size == (16, 16)
    assert inputs.pixelize_params.colors == 12
    assert inputs.pixelize_params.preview_scale == 12
    assert inputs.pixelize_params.remove_bg is True
    assert inputs.pixelize_params.bg_tolerance == 26
    assert inputs.pixelize_params.auto_crop is True
    assert inputs.pixelize_params.palette_mode == "auto"
    assert inputs.grid.mode == "extract"
    assert inputs.image_quality == "low"
    assert inputs.skip_vl is True

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps({"outputs": {}}, ensure_ascii=False), encoding="utf-8")
    captured = {}

    def fake_run(run_cfg, run_inputs):
        captured["cfg"] = run_cfg
        captured["inputs"] = run_inputs
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=run_dir / "01_source.png",
            pixel_path=run_dir / "03_pixelized.png",
            preview_path=None,
            analysis_path=None,
            meta_path=meta_path,
            meta={"outputs": {}},
        )

    monkeypatch.setattr("pix_web.pipeline_adapter.run_pipeline", fake_run)
    result = run_job_pipeline(job, settings, cfg=cfg)

    assert result.meta["asset"]["name"] == "紫檀木"
    assert result.meta["asset"]["asset_kind"] == "ui_component"
    assert result.meta["asset"]["subject_kind"] == "single_ui"
    assert result.meta["asset"]["palette_mode"] == "auto"
    assert captured["cfg"].image_gen.contact_sheet_enabled is False
    assert captured["cfg"].image_gen.prompt_guard_remote is False
    assert cfg.image_gen.contact_sheet_enabled is True
    assert cfg.image_gen.prompt_guard_remote is True
    assert json.loads(meta_path.read_text(encoding="utf-8"))["asset"]["name"] == "紫檀木"


def test_list_jobs_prunes_old_successful_outputs(client: TestClient) -> None:
    user, headers = _register_and_login(client, "retention@example.com")
    session_factory = client.app.state.SessionLocal
    settings = client.app.state.web_settings
    base_time = datetime.now(timezone.utc) - timedelta(days=1)

    with session_factory() as db:
        stale_run_dir: Path | None = None
        stale_job_id: int | None = None
        for index in range(11):
            created_at = base_time + timedelta(minutes=index)
            job = GenerationJob(
                user_id=user["id"],
                client_request_id=f"retention-{index}",
                job_type="text_to_image",
                status="succeeded",
                prompt=f"pixel gem {index}",
                price_credits=20,
                created_at=created_at,
                started_at=created_at,
                finished_at=created_at,
            )
            db.add(job)
            db.flush()
            run_dir = settings.storage_root / "runs" / f"retention-{index}"
            run_dir.mkdir(parents=True)
            source = run_dir / "01_source.png"
            pixel = run_dir / "03_pixelized.png"
            meta = run_dir / "meta.json"
            Image.new("RGBA", (4, 4), (index, 0, 0, 255)).save(source)
            Image.new("RGBA", (4, 4), (0, index, 0, 255)).save(pixel)
            meta.write_text("{}", encoding="utf-8")
            db.add(GenerationOutput(job_id=job.id, run_dir=str(run_dir), source_path=str(source), pixelized_path=str(pixel), meta_json_path=str(meta)))
            db.add(CreditTransaction(user_id=user["id"], type="consume", amount=-20, balance_after=0, job_id=job.id, note="consume"))
            if index == 0:
                stale_run_dir = run_dir
                stale_job_id = job.id
        db.commit()

    response = client.get("/jobs?limit=50", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len([job for job in body if job["status"] == "succeeded"]) == 10
    assert all(job["id"] != stale_job_id for job in body)
    assert stale_run_dir is not None
    assert not stale_run_dir.exists()

    with session_factory() as db:
        assert db.get(GenerationJob, stale_job_id) is None
        stale_tx = db.scalar(select(CreditTransaction).where(CreditTransaction.note == "consume").order_by(CreditTransaction.id.asc()))
        assert stale_tx is not None
        assert stale_tx.job_id is None


def test_worker_success_consumes_reserved_credits(client: TestClient, tmp_path, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    created = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "text_to_image", "prompt": "pixel cat"},
    ).json()

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source = run_dir / "01_source.png"
    pixel = run_dir / "03_pixelized.png"
    meta = run_dir / "meta.json"
    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir()
    candidate = candidates_dir / "candidate_05.png"
    candidate_outputs_dir = run_dir / "candidate_outputs"
    candidate_outputs_dir.mkdir()
    candidate_pixel = candidate_outputs_dir / "candidate_05_pixelized.png"
    candidate_preview = candidate_outputs_dir / "candidate_05_preview.png"
    sheet = run_dir / "01_contact_sheet.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(pixel)
    Image.new("RGBA", (4, 4), (0, 0, 255, 255)).save(candidate)
    Image.new("RGBA", (4, 4), (255, 0, 255, 255)).save(candidate_pixel)
    Image.new("RGBA", (8, 8), (255, 0, 255, 255)).save(candidate_preview)
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(sheet)
    meta.write_text(json.dumps({"image_gen": {"contact_sheet": {"sheet": "01_contact_sheet.png", "selected_index": 5, "candidates": [{"index": 5, "row": 1, "col": 1, "path": "candidates/candidate_05.png", "pixelized_path": "candidate_outputs/candidate_05_pixelized.png", "preview_path": "candidate_outputs/candidate_05_preview.png", "score": 94, "rank": 1, "reason": "最清晰", "selected": True}]}}}, ensure_ascii=False), encoding="utf-8")

    def fake_run(_job, _settings, *, cfg=None):
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=source,
            pixel_path=pixel,
            preview_path=None,
            analysis_path=None,
            meta_path=meta,
        )

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fake_run)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    assert processed is not None
    assert processed.id == created["id"]
    assert processed.status == "succeeded"
    assert processed.outputs[0].pixelized_path == str(pixel)

    fetched_job = client.get(f"/jobs/{created['id']}", headers=headers).json()
    assert fetched_job["outputs"][0]["pixelized_url"].startswith("/files?path=")
    assert fetched_job["outputs"][0]["source_url"].startswith("/files?path=")
    assert fetched_job["outputs"][0]["contact_sheet_url"].startswith("/files?path=")
    assert fetched_job["outputs"][0]["candidates"][0]["index"] == 5
    assert fetched_job["outputs"][0]["candidates"][0]["score"] == 94
    assert fetched_job["outputs"][0]["candidates"][0]["rank"] == 1
    assert fetched_job["outputs"][0]["candidates"][0]["selected"] is True
    assert fetched_job["outputs"][0]["candidates"][0]["pixelized_url"].startswith("/files?path=")
    assert fetched_job["outputs"][0]["candidates"][0]["preview_url"].startswith("/files?path=")

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 30
    assert balance["reserved_credits"] == 0
    assert balance["total_consumed"] == 20

    txs = client.get("/credits/transactions", headers=headers).json()
    assert [tx["type"] for tx in txs][:2] == ["consume", "reserve"]


def test_sprite_sheet_job_outputs_gif_and_frames(client: TestClient, tmp_path, monkeypatch) -> None:
    user, headers = _register_and_login(client, "sprite-user@example.com")
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    created = client.post(
        "/jobs",
        headers=headers,
        json={
            "job_type": "sprite_sheet",
            "prompt": "暗黑骑士挥剑动画",
            "pixelize": {"output_size": [16, 16], "colors": 6},
            "sprite": {
                "duration_ms": 80,
                "loop": 0,
                "rows": 3,
                "cols": 3,
                "key_mode": "soft",
                "key_tolerance": 24,
                "key_softness": 160,
                "key_alpha_floor": 4,
                "key_despill": True,
            },
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["params_json"]["sprite"]["key_mode"] == "soft"
    assert created.json()["params_json"]["sprite"]["key_despill"] is True

    run_dir = tmp_path / "sprite-run"
    run_dir.mkdir()
    source = run_dir / "01_sprite_grid.png"
    sheet = run_dir / "04_sprite_sheet.png"
    gif = run_dir / "05_sprite.gif"
    frames_dir = run_dir / "03_frames"
    frames_dir.mkdir()
    frames = []
    Image.new("RGBA", (48, 48), (0, 255, 0, 255)).save(source)
    Image.new("RGBA", (16 * 9, 16), (255, 0, 0, 255)).save(sheet)
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(gif)
    for i in range(1, 10):
        frame = frames_dir / f"frame_{i:02d}.png"
        Image.new("RGBA", (16, 16), (i * 20, 0, 0, 255)).save(frame)
        frames.append({"index": i, "row": (i - 1) // 3, "col": (i - 1) % 3, "path": f"03_frames/frame_{i:02d}.png"})
    meta = run_dir / "meta.json"
    meta.write_text(
        json.dumps({
            "sprite": {"horizontal_sheet": "04_sprite_sheet.png", "gif": "05_sprite.gif", "frames": frames},
            "outputs": {"sprite_sheet": "04_sprite_sheet.png", "sprite_gif": "05_sprite.gif"},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    def fake_run(_job, _settings, *, cfg=None):
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=source,
            pixel_path=sheet,
            preview_path=gif,
            analysis_path=None,
            meta_path=meta,
        )

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fake_run)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)
    assert processed is not None
    assert processed.status == "succeeded"

    fetched = client.get(f"/jobs/{created.json()['id']}", headers=headers).json()
    output = fetched["outputs"][0]
    assert output["sprite_sheet_url"].startswith("/files?path=")
    assert output["sprite_gif_url"].startswith("/files?path=")
    assert len(output["sprite_frames"]) == 9
    assert output["sprite_frames"][0]["url"].startswith("/files?path=")
    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 20
    assert balance["total_consumed"] == 30


def test_worker_failure_refunds_reserved_credits(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})

    def fail(_job, _settings, *, cfg=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    assert processed is not None
    assert processed.status == "failed"
    assert "boom" in processed.error_message

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 50
    assert balance["reserved_credits"] == 0
    assert balance["total_consumed"] == 0


def test_upload_image_requires_auth_and_stores_file(client: TestClient) -> None:
    image = Image.new("RGB", (4, 4), (20, 30, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()

    unauthorized = client.post(
        "/uploads/image",
        files={"file": ("icon.png", data, "image/png")},
    )
    assert unauthorized.status_code == 401

    _user, headers = _register_and_login(client)
    uploaded = client.post(
        "/uploads/image",
        headers=headers,
        files={"file": ("icon.png", data, "image/png")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["filename"] == "icon.png"
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(data)
    assert body["url"].startswith("/files?path=")
    assert client.app.state.web_settings.storage_root in Path(body["path"]).parents
    assert Path(body["path"]).exists()

    unauthorized_file = client.get(body["url"])
    assert unauthorized_file.status_code == 401
    fetched = client.get(body["url"], headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == data


def test_file_access_rejects_unsafe_paths(client: TestClient) -> None:
    _user, headers = _register_and_login(client)
    forbidden = client.get("/files", headers=headers, params={"path": ".env"})
    assert forbidden.status_code == 403


def test_uploaded_image_can_create_image_jobs(client: TestClient) -> None:
    image = Image.new("RGB", (4, 4), (40, 50, 60))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    uploaded = client.post(
        "/uploads/image",
        headers=headers,
        files={"file": ("batch.png", data, "image/png")},
    ).json()

    image_to_image = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "image_to_image", "prompt": "make it icy", "input_image_path": uploaded["path"]},
    )
    assert image_to_image.status_code == 200
    assert image_to_image.json()["price_credits"] == 20

    local = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "local_pixelize", "input_image_path": uploaded["path"]},
    )
    assert local.status_code == 200
    assert local.json()["price_credits"] == 0


def test_upload_daily_limit_blocks_extra_uploads(client: TestClient) -> None:
    image = Image.new("RGB", (4, 4), (20, 30, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    _user, headers = _register_and_login(client)
    client.put("/admin/settings/max_uploads_per_user_per_day", headers=headers, json={"value": "1"})

    first = client.post("/uploads/image", headers=headers, files={"file": ("one.png", data, "image/png")})
    second = client.post("/uploads/image", headers=headers, files={"file": ("two.png", data, "image/png")})

    assert first.status_code == 200
    assert second.status_code == 429


def test_failed_upload_does_not_count_toward_daily_limit(client: TestClient) -> None:
    image = Image.new("RGB", (4, 4), (20, 30, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    _user, headers = _register_and_login(client)
    client.put("/admin/settings/max_uploads_per_user_per_day", headers=headers, json={"value": "1"})

    failed = client.post("/uploads/image", headers=headers, files={"file": ("bad.txt", b"bad", "text/plain")})
    valid = client.post("/uploads/image", headers=headers, files={"file": ("ok.png", data, "image/png")})

    assert failed.status_code == 400
    assert valid.status_code == 200


def test_upload_rejects_non_image_extension(client: TestClient) -> None:
    _user, headers = _register_and_login(client)
    uploaded = client.post(
        "/uploads/image",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert uploaded.status_code == 400


def test_public_pricing_and_repixelize_are_free(client: TestClient, tmp_path) -> None:
    _user, headers = _register_and_login(client)

    pricing = client.get("/pricing")
    assert pricing.status_code == 200
    rules = {rule["key"]: rule for rule in pricing.json()}
    assert rules["text_to_image"]["price_credits"] == 20
    assert rules["repixelize"]["price_credits"] == 0

    image_path = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(image_path)
    created = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "repixelize", "input_image_path": str(image_path)},
    )
    assert created.status_code == 200
    assert created.json()["price_credits"] == 0
    assert created.json()["reserved_credits"] == 0


def test_local_pixelize_job_is_free_and_requires_image(client: TestClient, tmp_path) -> None:
    _user, headers = _register_and_login(client)
    image_path = tmp_path / "input.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(image_path)

    created = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "local_pixelize", "input_image_path": str(image_path)},
    )
    assert created.status_code == 200
    assert created.json()["price_credits"] == 0
    assert created.json()["reserved_credits"] == 0

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 0
    assert balance["reserved_credits"] == 0
