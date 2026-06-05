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
from pix_web.referrals import frontend_invite_base_url

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """邮件发送失败。"""


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


def _clean_header(value: str) -> str:
    return " ".join(value.strip().split())


def _site_url_from_settings(settings: WebSettings) -> str:
    return frontend_invite_base_url(settings.frontend_base_url, settings.public_base_url)


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


def _verification_code_cells(code: str) -> str:
    cells = []
    for char in code.strip():
        cells.append(
            '<td style="padding:0 4px;">'
            '<span style="display:inline-block;min-width:38px;border:1px solid #d9cdbb;border-radius:12px;'
            'background:#fffdf7;padding:11px 0;text-align:center;font-size:26px;line-height:1;'
            'font-weight:800;letter-spacing:0;color:#161616;box-shadow:0 6px 16px rgba(31,27,21,0.08);">'
            f"{escape(char)}"
            "</span>"
            "</td>"
        )
    return "".join(cells)


def _verification_html_body(code: str, site_url: str) -> str:
    safe_code = escape(code.strip())
    safe_url = escape(site_url)
    code_cells = _verification_code_cells(code)
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Pix 注册验证码</title>
  </head>
  <body style="margin:0;background:#f5efe3;padding:32px 16px;font-family:'Notion Sans',-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','Microsoft YaHei UI',sans-serif;color:#161616;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">你的 Pix 注册验证码是 {safe_code}，10 分钟内有效。</div>
    <div style="max-width:640px;margin:0 auto;">
      <div style="border:1px solid #d8ccba;border-radius:30px;background:#fffaf1;box-shadow:0 28px 80px rgba(31,27,21,0.16);overflow:hidden;">
        <div style="background:#121826;padding:28px 30px 24px;color:#fff;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
            <tr>
              <td style="vertical-align:top;">
                <p style="margin:0 0 12px;font-size:11px;line-height:1;letter-spacing:0.18em;text-transform:uppercase;color:#c8c0ff;font-weight:800;">Pix Forge</p>
                <h1 style="margin:0;font-size:30px;line-height:1.15;font-weight:850;letter-spacing:-0.03em;color:#fff;">你的注册通行名片</h1>
                <p style="margin:12px 0 0;font-size:14px;line-height:1.65;color:#dbe4ff;">这组验证码会帮你完成 Pix 账号注册。</p>
              </td>
              <td width="112" align="right" style="vertical-align:top;">
                <div style="display:inline-block;border:1px solid rgba(255,255,255,0.18);border-radius:18px;background:rgba(255,255,255,0.08);padding:12px;">
                  <table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:4px;">
                    <tr><td style="width:10px;height:10px;border-radius:3px;background:#a78bfa;"></td><td style="width:10px;height:10px;border-radius:3px;background:#facc15;"></td><td style="width:10px;height:10px;border-radius:3px;background:#67e8f9;"></td></tr>
                    <tr><td style="width:10px;height:10px;border-radius:3px;background:#86efac;"></td><td style="width:10px;height:10px;border-radius:3px;background:#fb7185;"></td><td style="width:10px;height:10px;border-radius:3px;background:#f97316;"></td></tr>
                    <tr><td style="width:10px;height:10px;border-radius:3px;background:#fde68a;"></td><td style="width:10px;height:10px;border-radius:3px;background:#c4b5fd;"></td><td style="width:10px;height:10px;border-radius:3px;background:#99f6e4;"></td></tr>
                  </table>
                </div>
              </td>
            </tr>
          </table>
        </div>
        <div style="padding:30px;">
          <div style="border:1px solid #e5dac8;border-radius:24px;background:#ffffff;padding:24px;box-shadow:0 18px 46px rgba(31,27,21,0.08);">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
              <tr>
                <td style="vertical-align:top;">
                  <p style="margin:0;color:#6f675b;font-size:12px;line-height:1.4;letter-spacing:0.1em;text-transform:uppercase;font-weight:800;">Verification Code</p>
                  <h2 style="margin:8px 0 0;font-size:20px;line-height:1.35;color:#161616;font-weight:800;">输入这组验证码完成注册</h2>
                </td>
                <td align="right" style="vertical-align:top;">
                  <span style="display:inline-block;border-radius:999px;background:#e8f8ed;color:#166534;padding:8px 12px;font-size:12px;line-height:1;font-weight:800;">10 分钟有效</span>
                </td>
              </tr>
            </table>
            <div style="margin-top:24px;border-radius:22px;background:#f7f0e4;padding:18px 12px;text-align:center;">
              <table role="presentation" align="center" cellspacing="0" cellpadding="0" style="margin:0 auto;border-collapse:collapse;">
                <tr>{code_cells}</tr>
              </table>
              <p style="margin:14px 0 0;color:#7a7165;font-size:12px;line-height:1.6;">验证码：<strong style="color:#161616;letter-spacing:0.16em;">{safe_code}</strong></p>
            </div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:22px;border-collapse:collapse;">
              <tr>
                <td style="padding:0 6px 8px 0;"><span style="display:block;border:1px solid #d9ecff;border-radius:14px;background:#eef7ff;color:#1f4f75;padding:10px 12px;font-size:12px;line-height:1.35;font-weight:700;">仅用于注册</span></td>
                <td style="padding:0 6px 8px;"><span style="display:block;border:1px solid #eee0b4;border-radius:14px;background:#fff7d6;color:#6f4a00;padding:10px 12px;font-size:12px;line-height:1.35;font-weight:700;">不要转发</span></td>
                <td style="padding:0 0 8px 6px;"><span style="display:block;border:1px solid #ead7f8;border-radius:14px;background:#f6edff;color:#5b2482;padding:10px 12px;font-size:12px;line-height:1.35;font-weight:700;">一次验证</span></td>
              </tr>
            </table>
            <a href="{safe_url}" style="display:inline-block;margin-top:12px;border-radius:999px;background:#161616;color:#fff;text-decoration:none;padding:13px 20px;font-size:14px;line-height:1;font-weight:800;">回到 Pix</a>
          </div>
          <p style="margin:18px 2px 0;color:#756d61;font-size:13px;line-height:1.75;">如果不是你本人正在注册 Pix，请忽略这封邮件。我们不会通过邮件索要密码或付款信息。</p>
          <p style="margin:10px 2px 0;color:#9b9183;font-size:12px;line-height:1.65;word-break:break-all;">按钮无法打开时，请复制链接访问：{safe_url}</p>
        </div>
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
        raise EmailDeliveryError(f"未知邮件发送方式: {settings.email_provider}")

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
