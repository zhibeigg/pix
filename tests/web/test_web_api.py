from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import base64
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.models import GenerationBatch
from pix_web.payment_providers import _alipay_sign_content, _rsa_sign
from pix_web.worker import process_next_job


@pytest.fixture()
def client(tmp_path):
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'pix_web_test.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
        email_debug_codes=True,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


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
    checkout = client.post("/billing/checkout", headers=headers, json={"package_key": "starter", "provider": "alipay"})

    assert checkout.status_code == 200
    body = checkout.json()
    assert body["provider"] == "alipay"
    assert "alipay.trade.page.pay" in body["payment_url"]
    assert "sign=" in body["payment_url"]

    order = body["order"]
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
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == order["credits"]


def test_wechat_checkout_and_webhook_are_idempotent(client: TestClient, monkeypatch) -> None:
    merchant_private, _merchant_public = _rsa_key_pair()
    platform_private, platform_public = _rsa_key_pair()
    api_v3_key = "a" * 32
    client.app.state.web_settings = replace(
        client.app.state.web_settings,
        public_base_url="https://pix.example.com/api",
        wechat_app_id="wx-app",
        wechat_mch_id="mch-id",
        wechat_private_key=merchant_private,
        wechat_merchant_serial_no="serial-no",
        wechat_api_v3_key=api_v3_key,
        wechat_platform_cert=platform_public,
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"code_url": "weixin://wxpay/test"}

    monkeypatch.setattr("pix_web.payment_providers.httpx.post", lambda *args, **kwargs: FakeResponse())
    _user, headers = _register_and_login(client)
    checkout = client.post("/billing/checkout", headers=headers, json={"package_key": "starter", "provider": "wechat"})

    assert checkout.status_code == 200
    body = checkout.json()
    assert body["code_url"] == "weixin://wxpay/test"
    order = body["order"]

    resource = {
        "trade_state": "SUCCESS",
        "out_trade_no": order["provider_order_id"],
        "transaction_id": "wx-trade-1",
        "amount": {"total": order["amount_cents"], "currency": "CNY"},
    }
    nonce = "nonce-123456"
    aad = "transaction"
    ciphertext = AESGCM(api_v3_key.encode("utf-8")).encrypt(
        nonce.encode("utf-8"),
        json.dumps(resource, separators=(",", ":")).encode("utf-8"),
        aad.encode("utf-8"),
    )
    payload = {
        "id": "notify-1",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "nonce": nonce,
            "associated_data": aad,
        },
    }
    raw = json.dumps(payload, separators=(",", ":"))
    timestamp = "1700000000"
    notify_nonce = "notify-nonce"
    signature = _rsa_sign(platform_private, f"{timestamp}\n{notify_nonce}\n{raw}\n")
    notify_headers = {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": notify_nonce,
        "Wechatpay-Signature": signature,
    }
    paid = client.post("/billing/webhook/wechat", content=raw, headers=notify_headers)
    again = client.post("/billing/webhook/wechat", content=raw, headers=notify_headers)

    assert paid.status_code == 200
    assert paid.json()["code"] == "SUCCESS"
    assert again.status_code == 200
    assert client.get("/credits/balance", headers=headers).json()["available_credits"] == order["credits"]


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
    assert {item["key"] for item in settings.json()} >= {
        "generation_enabled",
        "max_pending_jobs_per_user",
        "daily_job_limit_per_user",
    }

    updated = client.put("/admin/settings/max_pending_jobs_per_user", headers=headers, json={"value": "2"})
    assert updated.status_code == 200
    assert updated.json()["value"] == "2"


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


def test_pending_limit_blocks_extra_jobs(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 100})
    client.put("/admin/settings/max_pending_jobs_per_user", headers=headers, json={"value": "1"})

    first = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})
    second = client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel dog"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_batch_respects_pending_limit_atomically(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 100})
    client.put("/admin/settings/max_pending_jobs_per_user", headers=headers, json={"value": "1"})

    response = client.post(
        "/jobs/batch",
        headers=headers,
        json={"jobs": [{"job_type": "text_to_image", "prompt": "cat"}, {"job_type": "text_to_image", "prompt": "dog"}]},
    )

    assert response.status_code == 429
    assert client.get("/jobs", headers=headers).json() == []


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

    def fake_run(_job, _settings):
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
    assert any(name.endswith("01_source.png") for name in names)
    assert any(name.endswith("03_pixelized.png") for name in names)
    assert any(name.endswith("04_preview.png") for name in names)
    assert any(name.endswith("02_analysis.json") for name in names)
    assert any(name.endswith("meta.json") for name in names)

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


def test_retry_failed_batch_jobs_requeues_into_same_batch(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    created = client.post(
        "/jobs/batch",
        headers=headers,
        json={"batch_name": "Retry Pack", "jobs": [{"job_type": "text_to_image", "prompt": "pixel cat"}]},
    ).json()

    def fail(_job, _settings):
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
    assert balance["available_credits"] == 30
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

    def fail(_job, _settings):
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

    def fail(_job, _settings):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    _other, other_headers = _register_and_login(client, "retry-other@example.com")
    retry = client.post(f"/batches/{created['batch_id']}/retry-failed", headers=other_headers)
    assert retry.status_code == 404


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
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(pixel)
    meta.write_text("{}", encoding="utf-8")

    def fake_run(_job, _settings):
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

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 30
    assert balance["reserved_credits"] == 0
    assert balance["total_consumed"] == 20

    txs = client.get("/credits/transactions", headers=headers).json()
    assert [tx["type"] for tx in txs][:2] == ["consume", "reserve"]


def test_worker_failure_refunds_reserved_credits(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})

    def fail(_job, _settings):
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
