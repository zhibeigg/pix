from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from pix_web.config import WebSettings
from pix_web.email_verification import create_email_code
from pix_web.models import Base
from pix_web.routers.auth import request_register_code
from pix_web.schemas import EmailCodeRequest
from pix_web.system_settings import ensure_default_system_settings, update_system_setting


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_system_settings(db)
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def settings() -> WebSettings:
    return WebSettings(
        jwt_secret="test-secret",
        email_provider="console",
        email_code_resend_seconds=0,
        turnstile_enabled=True,
        turnstile_site_key="site-key",
        turnstile_secret_key="secret-key",
        turnstile_email_window_seconds=3600,
        turnstile_email_max_without_challenge=2,
        turnstile_ip_window_seconds=3600,
        turnstile_ip_max_without_challenge=2,
    )


def configure_turnstile(db, *, enabled: bool = True) -> None:
    update_system_setting(db, "web.email_provider", "console")
    update_system_setting(db, "web.email_debug_codes", "true")
    update_system_setting(db, "web.turnstile_enabled", "true" if enabled else "false")
    update_system_setting(db, "web.turnstile_site_key", "site-key")
    update_system_setting(db, "web.turnstile_secret_key", "secret-key")
    update_system_setting(db, "web.turnstile_email_window_seconds", "3600")
    update_system_setting(db, "web.turnstile_email_max_without_challenge", "2")
    update_system_setting(db, "web.turnstile_ip_window_seconds", "3600")
    update_system_setting(db, "web.turnstile_ip_max_without_challenge", "2")


def request_from(ip: str = "203.0.113.10") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/register-code",
            "headers": [(b"x-forwarded-for", ip.encode("ascii"))],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def send_register_code(db, email: str, *, ip: str = "203.0.113.10", token: str = ""):
    return request_register_code(
        EmailCodeRequest(email=email, turnstile_token=token),
        request_from(ip),
        db,
        settings(),
    )


def test_first_register_code_does_not_require_turnstile(db_session) -> None:
    configure_turnstile(db_session)

    response = send_register_code(db_session, "new@example.com")

    assert response.ok is True
    assert response.debug_code is not None


def test_same_email_requires_turnstile_after_threshold(db_session) -> None:
    configure_turnstile(db_session)
    send_register_code(db_session, "repeat@example.com")
    send_register_code(db_session, "repeat@example.com")

    with pytest.raises(HTTPException) as exc_info:
        send_register_code(db_session, "repeat@example.com")

    assert exc_info.value.status_code == 428
    assert "人机校验" in str(exc_info.value.detail)


def test_same_ip_requires_turnstile_after_threshold(db_session) -> None:
    configure_turnstile(db_session)
    send_register_code(db_session, "first@example.com", ip="203.0.113.30")
    send_register_code(db_session, "second@example.com", ip="203.0.113.30")

    with pytest.raises(HTTPException) as exc_info:
        send_register_code(db_session, "third@example.com", ip="203.0.113.30")

    assert exc_info.value.status_code == 428
    assert "人机校验" in str(exc_info.value.detail)


def test_turnstile_token_allows_frequent_request(db_session) -> None:
    configure_turnstile(db_session)
    send_register_code(db_session, "token@example.com")
    send_register_code(db_session, "token@example.com")

    with patch("pix_web.routers.auth.verify_turnstile_token") as verify_token:
        response = send_register_code(db_session, "token@example.com", token="valid-token")

    assert response.ok is True
    assert response.debug_code is not None
    verify_token.assert_called_once()


def test_disabled_turnstile_never_requires_challenge(db_session) -> None:
    configure_turnstile(db_session, enabled=False)
    base_settings = settings()
    for index in range(3):
        create_email_code(
            db_session,
            base_settings,
            f"seed-{index}@example.com",
            request_ip="203.0.113.40",
        )
    db_session.commit()

    response = send_register_code(db_session, "no-challenge@example.com", ip="203.0.113.40")

    assert response.ok is True
    assert response.debug_code is not None
