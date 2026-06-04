"""邮件发送。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
import logging
import smtplib
from typing import Sequence

from pix_web.config import WebSettings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """邮件发送失败。"""


def _verification_subject() -> str:
    return "Pix 注册验证码"


def _verification_body(code: str) -> str:
    return (
        "你的 Pix 注册验证码是：\n\n"
        f"{code}\n\n"
        "验证码 10 分钟内有效。若不是你本人操作，请忽略这封邮件。"
    )


def _clean_header(value: str) -> str:
    return " ".join(value.strip().split())


def _require_smtp_config(settings: WebSettings) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryError("SMTP 配置不完整：需要 PIX_WEB_SMTP_HOST 和 PIX_WEB_SMTP_FROM")


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


def _base_message(settings: WebSettings, email: str, subject: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = _clean_header(subject)
    message["From"] = settings.smtp_from
    message["To"] = email
    return message


def _verification_message(settings: WebSettings, email: str, code: str) -> EmailMessage:
    message = _base_message(settings, email, _verification_subject())
    message.set_content(_verification_body(code))
    return message


def send_verification_email(settings: WebSettings, email: str, code: str) -> None:
    """发送注册验证码；失败时抛出 EmailDeliveryError。"""
    if settings.email_provider == "console":
        logger.warning("Pix 注册验证码 email=%s code=%s", email, code)
        return
    if settings.email_provider != "smtp":
        raise EmailDeliveryError(f"未知邮件发送方式: {settings.email_provider}")
    try:
        _send_smtp_message(settings, _verification_message(settings, email, code))
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(f"SMTP 邮件发送失败: {exc}") from exc


async def send_verification_email_task(settings: WebSettings, email: str, code: str) -> None:
    """发送注册验证码；SMTP 阻塞 I/O 在线程中执行。"""
    await asyncio.to_thread(send_verification_email, settings, email, code)


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
        f'<p style="margin:16px 0 0;color:#64748b;font-size:13px;line-height:1.6;">发布时间：{escape(published_at)}</p>'
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
  <body style="margin:0;background:#f8fafc;padding:32px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#0f172a;">
    <div style="max-width:640px;margin:0 auto;">
      <div style="border:1px solid #e2e8f0;border-radius:24px;background:#ffffff;box-shadow:0 24px 70px rgba(15,23,42,0.12);overflow:hidden;">
        <div style="background:linear-gradient(135deg,#111827,#334155);padding:28px 32px;color:#ffffff;">
          <p style="margin:0 0 10px;font-size:12px;letter-spacing:0.16em;text-transform:uppercase;color:#cbd5e1;">Pix Announcement</p>
          <h1 style="margin:0;font-size:28px;line-height:1.25;font-weight:800;letter-spacing:-0.03em;">{safe_title}</h1>
        </div>
        <div style="padding:30px 32px 34px;">
          <div style="border-left:4px solid #0f172a;background:#f8fafc;border-radius:16px;padding:20px 22px;color:#334155;font-size:15px;line-height:1.85;">
            {safe_body}
          </div>
          {published_html}
          <a href="{safe_url}" style="display:inline-block;margin-top:24px;border-radius:999px;background:#0f172a;color:#ffffff;text-decoration:none;padding:13px 22px;font-size:14px;font-weight:700;">打开 Pix 网站</a>
          <p style="margin:18px 0 0;color:#94a3b8;font-size:12px;line-height:1.6;">如果按钮无法打开，请复制链接访问：<br><span style="word-break:break-all;color:#64748b;">{safe_url}</span></p>
        </div>
      </div>
      <p style="margin:18px 4px 0;color:#94a3b8;font-size:12px;line-height:1.6;text-align:center;">你收到这封邮件，是因为你注册了 Pix 账号。</p>
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
    """发送单封系统公告邮件；失败时抛出 EmailDeliveryError。"""
    if settings.email_provider == "console":
        logger.warning("Pix 系统公告邮件 email=%s title=%s link=%s", email, title.strip() or "新的系统公告", site_url)
        return
    if settings.email_provider != "smtp":
        raise EmailDeliveryError(f"未知邮件发送方式: {settings.email_provider}")
    try:
        _send_smtp_message(settings, _announcement_message(settings, email, title, body, site_url, updated_at))
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(f"SMTP 公告邮件发送失败: {exc}") from exc


def send_announcement_email_batch(
    settings: WebSettings,
    emails: Sequence[str],
    *,
    title: str,
    body: str,
    site_url: str,
    updated_at: datetime | None = None,
) -> None:
    """批量发送系统公告邮件；单个收件人失败不会中断后续投递。"""
    recipients = tuple(email.strip() for email in emails if email.strip())
    if not recipients:
        logger.info("Pix 系统公告邮件没有可投递的收件人")
        return
    if settings.email_provider == "console":
        for email in recipients:
            logger.warning("Pix 系统公告邮件 email=%s title=%s link=%s", email, title.strip() or "新的系统公告", site_url)
        return
    if settings.email_provider != "smtp":
        raise EmailDeliveryError(f"未知邮件发送方式: {settings.email_provider}")

    _require_smtp_config(settings)
    delivered = 0
    failed = 0
    with _new_smtp_client(settings) as client:
        _prepare_smtp_client(settings, client)
        for email in recipients:
            try:
                client.send_message(_announcement_message(settings, email, title, body, site_url, updated_at))
                delivered += 1
            except Exception as exc:
                failed += 1
                logger.warning("Pix 公告邮件发送失败 email=%s error=%s", email, exc)
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
