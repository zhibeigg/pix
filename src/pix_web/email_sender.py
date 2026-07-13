"""邮件发送。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
import logging
import smtplib
import socket
import ssl
from typing import Callable, Sequence

from pix_web.config import WebSettings
from pix_web.referrals import frontend_invite_base_url

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """可安全返回给客户端的邮件发送错误。"""

    def __init__(
        self,
        code: str,
        user_message: str,
        *,
        admin_message: str | None = None,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.admin_message = admin_message or user_message


_EMAIL_DELIVERY_MESSAGES: dict[str, tuple[str, str]] = {
    "recipient_unavailable": (
        "这个邮箱地址可能不存在或无法接收邮件，请检查拼写后重试，或更换邮箱。",
        "收件邮箱可能不存在或无法接收邮件，请检查邮箱地址后重试。",
    ),
    "mailbox_full": (
        "这个邮箱的收件箱可能已满，暂时无法接收邮件。请清理空间后重试，或更换邮箱。",
        "收件邮箱可能已满，请清理邮箱空间后重试，或更换测试邮箱。",
    ),
    "recipient_rejected": (
        "收件方暂时拒收了这封邮件，请稍后重试，或更换常用邮箱。",
        "收件方拒收了邮件，请检查收件地址、反垃圾策略或更换测试邮箱。",
    ),
    "smtp_busy": (
        "邮件服务当前繁忙，请稍后再试。",
        "SMTP 服务暂时繁忙或触发限流，请稍后重试。",
    ),
    "smtp_connection": (
        "暂时无法连接邮件服务，请稍后再试。",
        "无法连接 SMTP 服务器，请检查主机、端口、DNS 和网络。",
    ),
    "smtp_authentication": (
        "邮件服务暂时无法使用，请稍后再试；如持续失败，请联系管理员。",
        "SMTP 登录失败，请检查用户名、密码或邮箱授权码。",
    ),
    "smtp_sender_rejected": (
        "邮件服务暂时无法使用，请稍后再试；如持续失败，请联系管理员。",
        "SMTP 发件人被拒绝，请检查发件人地址与账号授权。",
    ),
    "smtp_security": (
        "邮件服务暂时无法使用，请稍后再试；如持续失败，请联系管理员。",
        "SMTP 安全连接失败，请检查端口与 SSL/STARTTLS 配置。",
    ),
    "smtp_not_configured": (
        "邮件服务暂时无法使用，请稍后再试；如持续失败，请联系管理员。",
        "SMTP 配置不完整，请先填写服务器地址和发件人。",
    ),
    "email_provider_invalid": (
        "邮件服务暂时无法使用，请稍后再试；如持续失败，请联系管理员。",
        "邮件发送方式配置无效，请选择 console 或 smtp。",
    ),
    "smtp_unknown": (
        "邮件暂时无法发送，请稍后再试；如持续失败，请联系管理员。",
        "SMTP 发送失败，请检查邮件服务配置或稍后重试。",
    ),
}

_RECIPIENT_UNAVAILABLE_MARKERS = (
    "mailbox not found",
    "mailbox unavailable",
    "user unknown",
    "unknown user",
    "no such user",
    "no such mailbox",
    "account does not exist",
    "invalid recipient",
    "recipient address rejected",
    "recipient not found",
    "用户不存在",
    "邮箱不存在",
    "收件人不存在",
    "地址不存在",
)
_MAILBOX_FULL_MARKERS = (
    "mailbox full",
    "mailbox is full",
    "quota exceeded",
    "over quota",
    "storage allocation",
    "insufficient storage",
    "邮箱已满",
    "邮箱空间不足",
    "超出容量",
)
_RECIPIENT_REJECTED_MARKERS = (
    "access denied",
    "message rejected",
    "recipient rejected",
    "policy",
    "spam",
    "blacklist",
    "blocked",
    "not allowed",
    "relay denied",
    "拒收",
    "黑名单",
    "策略限制",
)
_AUTHENTICATION_MARKERS = (
    "authentication failed",
    "authentication unsuccessful",
    "invalid credentials",
    "bad credentials",
    "authorization failed",
    "登录失败",
    "认证失败",
    "授权失败",
)
_SECURITY_MARKERS = (
    "starttls",
    "tls",
    "ssl",
    "certificate",
    "安全连接",
    "证书",
)


def _delivery_error(code: str) -> EmailDeliveryError:
    user_message, admin_message = _EMAIL_DELIVERY_MESSAGES.get(
        code, _EMAIL_DELIVERY_MESSAGES["smtp_unknown"]
    )
    return EmailDeliveryError(code, user_message, admin_message=admin_message)


def _smtp_response_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _smtp_exception_details(exc: Exception) -> tuple[int | None, str]:
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes: list[int] = []
        responses: list[str] = []
        for value in exc.recipients.values():
            if isinstance(value, tuple) and len(value) >= 2:
                raw_code, raw_response = value[0], value[1]
                if isinstance(raw_code, int):
                    codes.append(raw_code)
                text = _smtp_response_text(raw_response).strip()
                if text:
                    responses.append(text)
        return (codes[0] if codes else None, " | ".join(responses))
    if isinstance(exc, smtplib.SMTPResponseException):
        code = exc.smtp_code if isinstance(exc.smtp_code, int) else None
        return code, _smtp_response_text(exc.smtp_error).strip()
    return None, str(exc).strip()


def _contains_marker(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _classify_smtp_error(exc: Exception) -> tuple[str, int | None, str]:
    smtp_code, response = _smtp_exception_details(exc)
    normalized = " ".join(response.casefold().split())

    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "smtp_authentication", smtp_code, response
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "smtp_sender_rejected", smtp_code, response
    if isinstance(exc, (smtplib.SMTPNotSupportedError, ssl.SSLError)):
        return "smtp_security", smtp_code, response

    if _contains_marker(normalized, _MAILBOX_FULL_MARKERS):
        return "mailbox_full", smtp_code, response

    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        if _contains_marker(normalized, _RECIPIENT_UNAVAILABLE_MARKERS) or smtp_code in {
            550,
            551,
            553,
        }:
            return "recipient_unavailable", smtp_code, response
        if smtp_code == 552:
            return "mailbox_full", smtp_code, response
        if smtp_code is not None and 400 <= smtp_code < 500:
            return "smtp_busy", smtp_code, response
        return "recipient_rejected", smtp_code, response

    if _contains_marker(normalized, _RECIPIENT_UNAVAILABLE_MARKERS):
        return "recipient_unavailable", smtp_code, response
    if smtp_code in {530, 534, 535} or _contains_marker(
        normalized, _AUTHENTICATION_MARKERS
    ):
        return "smtp_authentication", smtp_code, response
    if _contains_marker(normalized, _SECURITY_MARKERS):
        return "smtp_security", smtp_code, response
    if smtp_code in {421, 450, 451, 452} or (
        smtp_code is not None and 400 <= smtp_code < 500
    ):
        return "smtp_busy", smtp_code, response
    if _contains_marker(normalized, _RECIPIENT_REJECTED_MARKERS):
        return "recipient_rejected", smtp_code, response
    if isinstance(
        exc,
        (
            smtplib.SMTPServerDisconnected,
            socket.timeout,
            socket.gaierror,
            TimeoutError,
            ConnectionError,
        ),
    ):
        return "smtp_connection", smtp_code, response
    if isinstance(exc, OSError):
        return "smtp_connection", smtp_code, response
    return "smtp_unknown", smtp_code, response


def _masked_email(email: str) -> str:
    local, separator, domain = email.strip().partition("@")
    if not separator or not domain:
        return "***"
    prefix = local[:1] if local else "*"
    return f"{prefix}***@{domain}"


def _safe_log_text(value: str, *, limit: int = 500) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())[:limit]


def _smtp_delivery_error(exc: Exception, *, purpose: str, email: str) -> EmailDeliveryError:
    code, smtp_code, response = _classify_smtp_error(exc)
    logger.warning(
        "Pix SMTP 投递失败 purpose=%s recipient=%s category=%s smtp_code=%s "
        "response=%s exception=%s",
        purpose,
        _masked_email(email),
        code,
        smtp_code if smtp_code is not None else "-",
        _safe_log_text(response) or "-",
        type(exc).__name__,
    )
    return _delivery_error(code)


def _verification_subject() -> str:
    return "Pix 注册验证码"


def _verification_body(code: str, site_url: str) -> str:
    return (
        "你的 Pix 注册验证码是：\n\n"
        f"{code}\n\n"
        "验证码 10 分钟内有效。请不要把验证码转发给他人。\n"
        f"访问 Pix：{site_url}\n\n"
        "若不是你本人操作，请忽略这封邮件。"
    )



def _reset_subject() -> str:
    return "Pix 密码重置验证码"



def _reset_body(code: str, site_url: str) -> str:
    return (
        "你的 Pix 密码重置验证码是：\n\n"
        f"{code}\n\n"
        "验证码 10 分钟内有效。请不要把验证码转发给他人。\n"
        f"访问 Pix：{site_url}\n\n"
        "若不是你本人操作，请忽略这封邮件。"
    )



def _clean_header(value: str) -> str:

    return " ".join(value.strip().split())


def _site_url_from_settings(settings: WebSettings) -> str:
    return frontend_invite_base_url(settings.frontend_base_url, settings.public_base_url)


def _require_smtp_config(settings: WebSettings) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise _delivery_error("smtp_not_configured")


def _new_smtp_client(settings: WebSettings) -> smtplib.SMTP:
    if settings.smtp_ssl:
        return smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
    return smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)


def _prepare_smtp_client(settings: WebSettings, client: smtplib.SMTP) -> None:
    if settings.smtp_tls and not settings.smtp_ssl:
        client.starttls()
    if settings.smtp_user:
        client.login(settings.smtp_user, settings.smtp_password)


def _send_smtp_message(settings: WebSettings, message: EmailMessage) -> None:
    _require_smtp_config(settings)
    with _new_smtp_client(settings) as client:
        _prepare_smtp_client(settings, client)
        client.send_message(message)


def _deliver_smtp_message(
    settings: WebSettings,
    message_factory: Callable[[], EmailMessage],
    *,
    purpose: str,
    email: str,
) -> None:
    try:
        _send_smtp_message(settings, message_factory())
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise _smtp_delivery_error(exc, purpose=purpose, email=email) from exc


def _base_message(settings: WebSettings, email: str, subject: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = _clean_header(subject)
    message["From"] = settings.smtp_from
    message["To"] = email
    return message


_PIX_LOGO_BASE64 = (
    "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"
)


def _pix_logo_html() -> str:
    """返回邮件顶部居中 Pix logo 的 HTML 片段。"""
    return (
        '<img src="data:image/png;base64,' + _PIX_LOGO_BASE64 + '" '
        'alt="Pix" width="48" height="48" '
        'style="display:block;margin:0 auto 24px;border-radius:12px;">'
    )


def _code_display_html(code: str) -> str:
    """返回验证码展示区块的 HTML。"""
    return (
        '<div style="margin:24px 0;background:#f0faf4;border-radius:16px;'
        'padding:28px 20px;text-align:center;">'
        f'<p style="margin:0;font-size:36px;font-weight:800;letter-spacing:0.25em;'
        f'color:#1a1a1a;line-height:1;">{escape(code.strip())}</p>'
        "</div>"
    )


def _verification_html_body(code: str, site_url: str) -> str:
    safe_code = escape(code.strip())
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Pix 注册验证码</title>
  </head>
  <body style="margin:0;background:#f5f5f5;padding:40px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','Microsoft YaHei UI',sans-serif;color:#1a1a1a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">你的 Pix 注册验证码是 {safe_code}，10 分钟内有效。</div>
    <div style="max-width:480px;margin:0 auto;">
      <div style="background:#ffffff;border:1px solid #e5e5e5;border-radius:16px;padding:40px 32px;text-align:center;">
        {_pix_logo_html()}
        <h1 style="margin:0 0 12px;font-size:24px;font-weight:700;color:#1a1a1a;line-height:1.3;">验证你的邮箱</h1>
        <p style="margin:0;font-size:15px;color:#666;line-height:1.6;">使用以下验证码完成 Pix 注册，验证码在 10 分钟内有效。</p>
        {_code_display_html(code)}
        <p style="margin:0;font-size:13px;color:#999;line-height:1.6;">如果你没有请求此验证码，可以安全地忽略这封邮件。</p>
      </div>
    </div>
  </body>
</html>"""


def _reset_html_body(code: str, site_url: str) -> str:
    safe_code = escape(code.strip())
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Pix 密码重置验证码</title>
  </head>
  <body style="margin:0;background:#f5f5f5;padding:40px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','Microsoft YaHei UI',sans-serif;color:#1a1a1a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">你的 Pix 密码重置验证码是 {safe_code}，10 分钟内有效。</div>
    <div style="max-width:480px;margin:0 auto;">
      <div style="background:#ffffff;border:1px solid #e5e5e5;border-radius:16px;padding:40px 32px;text-align:center;">
        {_pix_logo_html()}
        <h1 style="margin:0 0 12px;font-size:24px;font-weight:700;color:#1a1a1a;line-height:1.3;">重置你的密码</h1>
        <p style="margin:0;font-size:15px;color:#666;line-height:1.6;">使用以下验证码重置你的 Pix 密码，验证码在 10 分钟内有效。</p>
        {_code_display_html(code)}
        <p style="margin:0;font-size:13px;color:#999;line-height:1.6;">如果你没有请求重置密码，可以安全地忽略这封邮件。</p>
      </div>
    </div>
  </body>
</html>"""


def _verification_message(settings: WebSettings, email: str, code: str) -> EmailMessage:
    site_url = _site_url_from_settings(settings)
    message = _base_message(settings, email, _verification_subject())
    message.set_content(_verification_body(code, site_url))
    message.add_alternative(_verification_html_body(code, site_url), subtype="html")
    return message



def _reset_message(settings: WebSettings, email: str, code: str) -> EmailMessage:
    site_url = _site_url_from_settings(settings)
    message = _base_message(settings, email, _reset_subject())
    message.set_content(_reset_body(code, site_url))
    message.add_alternative(_reset_html_body(code, site_url), subtype="html")
    return message



def send_verification_email(settings: WebSettings, email: str, code: str) -> None:
    """发送注册验证码；失败时抛出可安全返回给客户端的 EmailDeliveryError。"""
    if settings.email_provider == "console":
        logger.warning("Pix 注册验证码 email=%s code=%s", email, code)
        return
    if settings.email_provider != "smtp":
        raise _delivery_error("email_provider_invalid")
    _deliver_smtp_message(
        settings,
        lambda: _verification_message(settings, email, code),
        purpose="register_code",
        email=email,
    )



def send_password_reset_email(settings: WebSettings, email: str, code: str) -> None:

    """发送密码重置验证码；失败时抛出可安全返回给客户端的 EmailDeliveryError。"""
    if settings.email_provider == "console":
        logger.warning("Pix 密码重置验证码 email=%s code=%s", email, code)
        return
    if settings.email_provider != "smtp":
        raise _delivery_error("email_provider_invalid")
    _deliver_smtp_message(
        settings,
        lambda: _reset_message(settings, email, code),
        purpose="password_reset_code",
        email=email,
    )


async def send_password_reset_email_task(settings: WebSettings, email: str, code: str) -> None:
    """发送密码重置验证码；SMTP 阻塞 I/O 在线程中执行。"""
    await asyncio.to_thread(send_password_reset_email, settings, email, code)


def _format_announcement_time(updated_at: datetime | None) -> str:
    if updated_at is None:
        return ""
    value = updated_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _announcement_subject(title: str) -> str:
    clean_title = _clean_header(title)[:60]
    return f"Pix 系统公告：{clean_title}" if clean_title else "Pix 发布了新的系统公告"


def _announcement_plain_body(title: str, body: str, site_url: str, updated_at: datetime | None) -> str:
    published_at = _format_announcement_time(updated_at)
    lines = ["Pix 发布了新的系统公告。", ""]
    if title.strip():
        lines.extend([title.strip(), ""])
    if body.strip():
        lines.extend([body.strip(), ""])
    if published_at:
        lines.append(f"发布时间：{published_at}")
    lines.append(f"访问网站：{site_url}")
    lines.append("")
    lines.append("你收到这封邮件，是因为你注册了 Pix 账号。")
    return "\n".join(lines)


def _announcement_html_body(title: str, body: str, site_url: str, updated_at: datetime | None) -> str:
    safe_title = escape(title.strip() or "新的系统公告")
    safe_body = "<br>".join(escape(body.strip() or "请登录 Pix 查看公告详情。").splitlines())
    safe_url = escape(site_url)
    published_at = _format_announcement_time(updated_at)
    published_html = (
        f'<p style="margin:20px 0 0;color:#999;font-size:13px;line-height:1.6;">'
        f'发布时间：{escape(published_at)}</p>'
        if published_at
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{safe_title}</title>
  </head>
  <body style="margin:0;background:#f5f5f5;padding:40px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','Microsoft YaHei UI',sans-serif;color:#1a1a1a;">
    <div style="max-width:480px;margin:0 auto;">
      <div style="background:#ffffff;border:1px solid #e5e5e5;border-radius:16px;padding:40px 32px;text-align:center;">
        {_pix_logo_html()}
        <h1 style="margin:0 0 12px;font-size:24px;font-weight:700;color:#1a1a1a;line-height:1.3;">{safe_title}</h1>
        <div style="margin:24px 0;background:#f8f8f8;border-radius:16px;padding:20px;color:#333;font-size:15px;line-height:1.85;text-align:left;">
          {safe_body}
        </div>
        {published_html}
        <a href="{safe_url}" style="display:inline-block;margin-top:8px;border-radius:999px;background:#1a1a1a;color:#fff;text-decoration:none;padding:12px 28px;font-size:14px;font-weight:600;">打开 Pix</a>
        <p style="margin:20px 0 0;font-size:13px;color:#999;line-height:1.6;">你收到这封邮件，是因为你注册了 Pix 账号。</p>
      </div>
    </div>
  </body>
</html>"""


def _announcement_message(
    settings: WebSettings,
    email: str,
    title: str,
    body: str,
    site_url: str,
    updated_at: datetime | None,
) -> EmailMessage:
    message = _base_message(settings, email, _announcement_subject(title))
    message.set_content(_announcement_plain_body(title, body, site_url, updated_at))
    message.add_alternative(_announcement_html_body(title, body, site_url, updated_at), subtype="html")
    return message


def send_announcement_email(
    settings: WebSettings,
    email: str,
    *,
    title: str,
    body: str,
    site_url: str,
    updated_at: datetime | None = None,
) -> None:
    """发送单封系统公告邮件；失败时抛出可安全返回给客户端的 EmailDeliveryError。"""
    if settings.email_provider == "console":
        logger.warning("Pix 系统公告邮件 email=%s title=%s link=%s", email, title.strip() or "新的系统公告", site_url)
        return
    if settings.email_provider != "smtp":
        raise _delivery_error("email_provider_invalid")
    _deliver_smtp_message(
        settings,
        lambda: _announcement_message(settings, email, title, body, site_url, updated_at),
        purpose="announcement_test",
        email=email,
    )


def send_announcement_email_batch(
    settings: WebSettings,
    emails: Sequence[str],
    *,
    title: str,
    body: str,
    site_url: str,
    updated_at: datetime | None = None,
) -> None:
    """批量发送系统公告邮件；单个收件人失败不会中断后续投递，断连后自动重连。"""
    recipients = tuple(email.strip() for email in emails if email.strip())
    if not recipients:
        logger.info("Pix 系统公告邮件没有可投递的收件人")
        return
    if settings.email_provider == "console":
        for email in recipients:
            logger.warning("Pix 系统公告邮件 email=%s title=%s link=%s", email, title.strip() or "新的系统公告", site_url)
        return
    if settings.email_provider != "smtp":
        raise _delivery_error("email_provider_invalid")

    _require_smtp_config(settings)
    delivered = 0
    failed = 0
    client: smtplib.SMTP | None = None
    try:
        for email in recipients:
            try:
                if client is None:
                    client = _new_smtp_client(settings)
                    _prepare_smtp_client(settings, client)
                client.send_message(_announcement_message(settings, email, title, body, site_url, updated_at))
                delivered += 1
            except smtplib.SMTPServerDisconnected:
                logger.warning("Pix 公告邮件 SMTP 断连，尝试重连 email=%s", email)
                client = None
                try:
                    client = _new_smtp_client(settings)
                    _prepare_smtp_client(settings, client)
                    client.send_message(_announcement_message(settings, email, title, body, site_url, updated_at))
                    delivered += 1
                except Exception as retry_exc:
                    failed += 1
                    logger.warning("Pix 公告邮件重连发送失败 email=%s error=%s", email, retry_exc)
                    client = None
            except Exception as exc:
                failed += 1
                logger.warning("Pix 公告邮件发送失败 email=%s error=%s", email, exc)
    finally:
        if client is not None:
            try:
                client.quit()
            except Exception:
                pass
    logger.info("Pix 公告邮件群发完成 recipients=%s delivered=%s failed=%s", len(recipients), delivered, failed)


async def send_announcement_email_batch_task(
    settings: WebSettings,
    emails: Sequence[str],
    *,
    title: str,
    body: str,
    site_url: str,
    updated_at: datetime | None = None,
) -> None:
    """在线程中批量发送系统公告邮件，避免阻塞请求处理。"""
    try:
        await asyncio.to_thread(
            send_announcement_email_batch,
            settings,
            emails,
            title=title,
            body=body,
            site_url=site_url,
            updated_at=updated_at,
        )
    except EmailDeliveryError:
        logger.exception("Pix 公告邮件群发启动失败")
    except Exception:
        logger.exception("Pix 公告邮件群发执行失败")
