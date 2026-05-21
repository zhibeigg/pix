"""邮箱验证码发送。"""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
import logging
import smtplib

from pix_web.config import WebSettings

logger = logging.getLogger(__name__)


def _verification_subject() -> str:
    return "Pix 注册验证码"


def _verification_body(code: str) -> str:
    return (
        "你的 Pix 注册验证码是：\n\n"
        f"{code}\n\n"
        "验证码 10 分钟内有效。若不是你本人操作，请忽略这封邮件。"
    )


class EmailDeliveryError(RuntimeError):
    """验证码邮件发送失败。"""


def _send_smtp(settings: WebSettings, email: str, code: str) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryError("SMTP 配置不完整：需要 PIX_WEB_SMTP_HOST 和 PIX_WEB_SMTP_FROM")
    message = EmailMessage()
    message["Subject"] = _verification_subject()
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(_verification_body(code))

    if settings.smtp_ssl:
        client_context = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
    else:
        client_context = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)

    with client_context as client:
        if settings.smtp_tls and not settings.smtp_ssl:
            client.starttls()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)


def send_verification_email(settings: WebSettings, email: str, code: str) -> None:
    """发送注册验证码；失败时抛出 EmailDeliveryError。"""
    if settings.email_provider == "console":
        logger.warning("Pix 注册验证码 email=%s code=%s", email, code)
        return
    if settings.email_provider != "smtp":
        raise EmailDeliveryError(f"未知邮件发送方式: {settings.email_provider}")
    try:
        _send_smtp(settings, email, code)
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(f"SMTP 邮件发送失败: {exc}") from exc


async def send_verification_email_task(settings: WebSettings, email: str, code: str) -> None:
    """发送注册验证码；SMTP 阻塞 I/O 在线程中执行。"""
    await asyncio.to_thread(send_verification_email, settings, email, code)
