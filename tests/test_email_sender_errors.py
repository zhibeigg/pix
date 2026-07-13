from __future__ import annotations

import smtplib
import socket
import ssl
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from pix_web.config import WebSettings
from pix_web.email_sender import (
    EmailDeliveryError,
    send_announcement_email,
    send_password_reset_email,
    send_verification_email,
)
from pix_web.models import Base, EmailVerificationCode, User
from pix_web.routers.admin import test_email_setting as admin_test_email_setting
from pix_web.routers.auth import request_register_code
from pix_web.schemas import EmailCodeRequest, EmailTestRequest


def smtp_settings(**changes: object) -> WebSettings:
    values: dict[str, object] = {
        "jwt_secret": "test-secret-at-least-32-bytes-long",
        "email_provider": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "noreply@example.com",
        "smtp_password": "secret",
        "smtp_from": "Pix <noreply@example.com>",
        "smtp_tls": True,
        "smtp_ssl": False,
        "email_code_resend_seconds": 0,
        "turnstile_enabled": False,
    }
    values.update(changes)
    return WebSettings(**values)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def request_from(ip: str = "203.0.113.20") -> Request:
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


def test_mailbox_not_found_response_is_friendly_and_raw_detail_stays_in_log() -> None:
    smtp_error = smtplib.SMTPRecipientsRefused(
        {"casd@mcwar.cn": (550, b"Mailbox not found or access denied")}
    )

    with patch("pix_web.email_sender.logger.warning") as warning:
        with patch("pix_web.email_sender._send_smtp_message", side_effect=smtp_error):
            with pytest.raises(EmailDeliveryError) as exc_info:
                send_verification_email(smtp_settings(), "casd@mcwar.cn", "123456")

    error = exc_info.value
    assert error.code == "recipient_unavailable"
    assert error.user_message == "这个邮箱地址可能不存在或无法接收邮件，请检查拼写后重试，或更换邮箱。"
    assert "550" not in error.user_message
    assert "Mailbox not found" not in error.user_message
    assert "casd@mcwar.cn" not in error.user_message
    warning.assert_called_once()
    log_args = warning.call_args.args
    assert log_args[1:] == (
        "register_code",
        "c***@mcwar.cn",
        "recipient_unavailable",
        550,
        "Mailbox not found or access denied",
        "SMTPRecipientsRefused",
    )
    assert "casd@mcwar.cn" not in " ".join(str(value) for value in log_args)


@pytest.mark.parametrize(
    ("smtp_error", "expected_code", "user_fragment", "admin_fragment"),
    [
        (
            smtplib.SMTPRecipientsRefused(
                {"full@example.com": (552, b"Mailbox full: quota exceeded")}
            ),
            "mailbox_full",
            "收件箱可能已满",
            "收件邮箱可能已满",
        ),
        (
            smtplib.SMTPDataError(554, b"Message rejected by policy"),
            "recipient_rejected",
            "收件方暂时拒收",
            "反垃圾策略",
        ),
        (
            smtplib.SMTPAuthenticationError(535, b"Authentication failed"),
            "smtp_authentication",
            "邮件服务暂时无法使用",
            "SMTP 登录失败",
        ),
        (
            smtplib.SMTPSenderRefused(
                553, b"Sender address rejected", "noreply@example.com"
            ),
            "smtp_sender_rejected",
            "邮件服务暂时无法使用",
            "SMTP 发件人被拒绝",
        ),
        (
            smtplib.SMTPConnectError(421, b"Too many connections"),
            "smtp_busy",
            "邮件服务当前繁忙",
            "触发限流",
        ),
        (
            smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
            "smtp_connection",
            "暂时无法连接邮件服务",
            "无法连接 SMTP 服务器",
        ),
        (
            socket.gaierror(-2, "Name or service not known"),
            "smtp_connection",
            "暂时无法连接邮件服务",
            "DNS",
        ),
        (
            ssl.SSLError("certificate verify failed"),
            "smtp_security",
            "邮件服务暂时无法使用",
            "SSL/STARTTLS",
        ),
        (
            RuntimeError("internal transport detail"),
            "smtp_unknown",
            "邮件暂时无法发送",
            "SMTP 发送失败",
        ),
    ],
)
def test_common_smtp_failures_map_to_actionable_messages(
    smtp_error: Exception,
    expected_code: str,
    user_fragment: str,
    admin_fragment: str,
) -> None:
    with patch("pix_web.email_sender._send_smtp_message", side_effect=smtp_error):
        with pytest.raises(EmailDeliveryError) as exc_info:
            send_verification_email(smtp_settings(), "user@example.com", "123456")

    error = exc_info.value
    assert error.code == expected_code
    assert user_fragment in error.user_message
    assert admin_fragment in error.admin_message
    assert str(smtp_error) not in error.user_message
    assert str(smtp_error) not in error.admin_message


def test_password_reset_and_announcement_email_share_the_safe_error_mapping() -> None:
    smtp_error = smtplib.SMTPRecipientsRefused(
        {"missing@example.com": (550, b"No such user")}
    )

    with patch("pix_web.email_sender._send_smtp_message", side_effect=smtp_error):
        with pytest.raises(EmailDeliveryError) as reset_error:
            send_password_reset_email(
                smtp_settings(),
                "missing@example.com",
                "123456",
            )
        with pytest.raises(EmailDeliveryError) as announcement_error:
            send_announcement_email(
                smtp_settings(),
                "missing@example.com",
                title="测试公告",
                body="测试正文",
                site_url="https://www.mcwar.cn",
            )

    assert reset_error.value.code == "recipient_unavailable"
    assert announcement_error.value.code == "recipient_unavailable"
    assert "No such user" not in reset_error.value.user_message
    assert "No such user" not in announcement_error.value.admin_message


def test_message_construction_failure_is_also_sanitized() -> None:
    with pytest.raises(EmailDeliveryError) as exc_info:
        send_verification_email(
            smtp_settings(smtp_from="Pix\nInjected: value"),
            "user@example.com",
            "123456",
        )

    error = exc_info.value
    assert error.code == "smtp_unknown"
    assert "Injected" not in error.user_message
    assert "Injected" not in error.admin_message


def test_missing_smtp_configuration_uses_safe_user_and_actionable_admin_messages() -> None:
    with pytest.raises(EmailDeliveryError) as exc_info:
        send_verification_email(
            smtp_settings(smtp_host="", smtp_from=""),
            "user@example.com",
            "123456",
        )

    error = exc_info.value
    assert error.code == "smtp_not_configured"
    assert "联系管理员" in error.user_message
    assert error.admin_message == "SMTP 配置不完整，请先填写服务器地址和发件人。"
    assert "PIX_WEB_" not in error.user_message
    assert "PIX_WEB_" not in error.admin_message


def test_register_code_route_returns_user_message_and_rolls_back_code(db_session) -> None:
    smtp_error = smtplib.SMTPRecipientsRefused(
        {"new@example.com": (550, b"Mailbox not found or access denied")}
    )

    with patch("pix_web.email_sender._send_smtp_message", side_effect=smtp_error):
        with pytest.raises(HTTPException) as exc_info:
            request_register_code(
                EmailCodeRequest(email="new@example.com"),
                request_from(),
                db_session,
                smtp_settings(),
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "这个邮箱地址可能不存在或无法接收邮件，请检查拼写后重试，或更换邮箱。"
    assert "550" not in exc_info.value.detail
    assert "Mailbox not found" not in exc_info.value.detail
    assert "new@example.com" not in exc_info.value.detail
    assert db_session.scalar(select(func.count()).select_from(EmailVerificationCode)) == 0


def test_admin_email_test_route_returns_admin_message(db_session) -> None:
    smtp_error = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    admin = User(
        email="admin@example.com",
        password_hash="x",
        role="admin",
        status="active",
    )

    with patch("pix_web.email_sender._send_smtp_message", side_effect=smtp_error):
        with pytest.raises(HTTPException) as exc_info:
            admin_test_email_setting(
                EmailTestRequest(email="test@example.com"),
                admin,
                db_session,
                smtp_settings(),
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "SMTP 登录失败，请检查用户名、密码或邮箱授权码。"
    assert "535" not in exc_info.value.detail
    assert "Authentication failed" not in exc_info.value.detail
