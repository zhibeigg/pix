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


def _send_smtp(settings: WebSettings, email: str, code: str) -> None:
    message = EmailMessage()
    message["Subject"] = _verification_subject()
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(_verification_body(code))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_tls:
            client.starttls()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)


async def send_verification_email_task(settings: WebSettings, email: str, code: str) -> None:
    """发送注册验证码；SMTP 阻塞 I/O 在线程中执行。"""
    if settings.email_provider == "smtp":
        try:
            await asyncio.to_thread(_send_smtp, settings, email, code)
        except Exception:
            logger.exception("发送注册验证码邮件失败: %s", email)
        return

    logger.info("Pix 注册验证码 email=%s code=%s", email, code)
