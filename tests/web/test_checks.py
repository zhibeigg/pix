from __future__ import annotations

from pix_web.checks import (
    check_database,
    check_email_delivery,
    check_jwt_secret,
    check_payment_providers,
    check_queue,
    check_storage,
)
from pix_web.config import WebSettings, load_web_settings
from pix_web.email_sender import send_verification_email


def test_jwt_secret_check_rejects_default() -> None:
    result = check_jwt_secret(WebSettings())

    assert result.ok is False


def test_jwt_secret_check_accepts_long_secret() -> None:
    result = check_jwt_secret(WebSettings(jwt_secret="x" * 40))

    assert result.ok is True


def test_storage_check_accepts_writable_directory(tmp_path) -> None:
    result = check_storage(WebSettings(storage_root=tmp_path / "storage"))

    assert result.ok is True


def test_database_check_accepts_sqlite(tmp_path) -> None:
    db_path = tmp_path / "check.db"
    settings = WebSettings(database_url=f"sqlite:///{db_path}")

    result = check_database(settings)

    assert result.ok is True


def test_queue_database_backend_does_not_require_redis() -> None:
    result = check_queue(WebSettings(queue_backend="database"))

    assert result.ok is True


def test_email_check_allows_console_with_warning() -> None:
    result = check_email_delivery(WebSettings(email_provider="console"))

    assert result.ok is True
    assert "开发" in result.message


def test_email_check_rejects_incomplete_smtp() -> None:
    result = check_email_delivery(WebSettings(email_provider="smtp", smtp_host="smtp.example.com"))

    assert result.ok is False


def test_email_check_accepts_smtp_host_and_from() -> None:
    result = check_email_delivery(
        WebSettings(
            email_provider="smtp",
            smtp_host="smtp.example.com",
            smtp_from="Pix <noreply@example.com>",
        )
    )

    assert result.ok is True


def test_load_web_settings_enables_smtp_ssl_for_465(monkeypatch) -> None:
    monkeypatch.setenv("PIX_WEB_SMTP_PORT", "465")
    monkeypatch.delenv("PIX_WEB_SMTP_SSL", raising=False)

    settings = load_web_settings()

    assert settings.smtp_port == 465
    assert settings.smtp_ssl is True


def test_load_web_settings_allows_explicitly_disabling_smtp_ssl(monkeypatch) -> None:
    monkeypatch.setenv("PIX_WEB_SMTP_PORT", "465")
    monkeypatch.setenv("PIX_WEB_SMTP_SSL", "false")

    settings = load_web_settings()

    assert settings.smtp_port == 465
    assert settings.smtp_ssl is False


def test_smtp_ssl_uses_implicit_ssl_without_starttls(monkeypatch) -> None:
    calls = {"smtp": 0, "smtp_ssl": 0, "starttls": 0, "sent": 0}

    class FakeSMTPSSL:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            calls["smtp_ssl"] += 1
            assert host == "smtp.example.com"
            assert port == 465
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            calls["starttls"] += 1

        def login(self, user: str, password: str) -> None:
            assert user == "noreply@example.com"
            assert password == "secret"

        def send_message(self, _message) -> None:
            calls["sent"] += 1

    def fake_smtp(*_args, **_kwargs):
        calls["smtp"] += 1
        raise AssertionError("SMTP_SSL should be used for smtp_ssl=True")

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTPSSL)
    monkeypatch.setattr("smtplib.SMTP", fake_smtp)

    settings = WebSettings(
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_user="noreply@example.com",
        smtp_password="secret",
        smtp_from="Pix <noreply@example.com>",
        smtp_tls=True,
        smtp_ssl=True,
    )

    send_verification_email(settings, "target@example.com", "123456")

    assert calls == {"smtp": 0, "smtp_ssl": 1, "starttls": 0, "sent": 1}


def test_payment_check_accepts_alipay_certificate_mode() -> None:
    result = check_payment_providers(
        WebSettings(
            alipay_mode="certificate",
            alipay_app_id="app-id",
            alipay_private_key="private-key",
            alipay_app_cert="app-cert",
            alipay_public_cert="public-cert",
            alipay_root_cert="root-cert",
        )
    )

    assert result.ok is True


def test_payment_check_rejects_incomplete_alipay_certificate_mode() -> None:
    result = check_payment_providers(
        WebSettings(
            alipay_mode="certificate",
            alipay_app_id="app-id",
            alipay_private_key="private-key",
            alipay_app_cert="app-cert",
        )
    )

    assert result.ok is False
    assert "证书模式" in result.message


def test_database_check_reports_invalid_path(tmp_path) -> None:
    bad_dir = tmp_path / "missing" / "nested"
    result = check_database(WebSettings(database_url=f"sqlite:///{bad_dir / 'bad.db'}"))

    assert result.ok is False
