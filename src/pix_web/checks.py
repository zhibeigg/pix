"""部署前环境检查。"""

from __future__ import annotations

from dataclasses import dataclass
import os

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from pix_web.config import WebSettings, load_web_settings


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def _result(name: str, ok: bool, message: str) -> CheckResult:
    return CheckResult(name=name, ok=ok, message=message)


def check_jwt_secret(settings: WebSettings) -> CheckResult:
    default_secret = WebSettings.jwt_secret
    if settings.jwt_secret == default_secret:
        return _result("jwt_secret", False, "仍在使用默认 JWT secret")
    if len(settings.jwt_secret) < 32:
        return _result("jwt_secret", False, "JWT secret 长度建议至少 32 字符")
    return _result("jwt_secret", True, "已配置")


def check_packy_key() -> CheckResult:
    key = os.getenv("PACKY_API_KEY", "").strip()
    if not key or key.startswith("sk-xxxx"):
        return _result("packy_api_key", False, "PACKY_API_KEY 未配置")
    return _result("packy_api_key", True, "已配置")


def check_database(settings: WebSettings) -> CheckResult:
    try:
        engine = create_engine(settings.database_url, future=True)
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:
        return _result("database", False, f"连接失败: {exc}")
    return _result("database", True, "可连接")


def check_alembic_head(settings: WebSettings) -> CheckResult:
    try:
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        engine = create_engine(settings.database_url, future=True)
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except Exception as exc:
        return _result("alembic", False, f"检查失败: {exc}")
    if current != head:
        return _result("alembic", False, f"当前 revision={current or 'none'}，head={head}")
    return _result("alembic", True, f"已在 head {head}")


def check_storage(settings: WebSettings) -> CheckResult:
    try:
        settings.storage_root.mkdir(parents=True, exist_ok=True)
        marker = settings.storage_root / ".pix_write_test"
        marker.write_text("ok", encoding="utf-8")
        marker.unlink(missing_ok=True)
    except Exception as exc:
        return _result("storage", False, f"不可写: {exc}")
    return _result("storage", True, f"可写: {settings.storage_root}")


def check_payment_providers(settings: WebSettings) -> CheckResult:
    alipay_values = [settings.alipay_app_id, settings.alipay_private_key, settings.alipay_public_key]
    wechat_values = [
        settings.wechat_app_id,
        settings.wechat_mch_id,
        settings.wechat_private_key,
        settings.wechat_merchant_serial_no,
        settings.wechat_api_v3_key,
        settings.wechat_platform_cert,
    ]
    alipay_any = any(alipay_values)
    wechat_any = any(wechat_values)
    alipay_ok = (not alipay_any) or all(alipay_values)
    wechat_ok = (not wechat_any) or all(wechat_values)
    if not alipay_ok:
        return _result("payments", False, "支付宝配置不完整")
    if not wechat_ok:
        return _result("payments", False, "微信支付配置不完整")
    if alipay_any or wechat_any:
        return _result("payments", True, "支付渠道配置完整")
    return _result("payments", True, "未启用真实支付渠道，可使用 mock pay")


def check_email_delivery(settings: WebSettings) -> CheckResult:
    if settings.email_provider == "console":
        return _result("email", True, "console 邮件验证码仅适合开发/内测，生产建议配置 SMTP")
    if settings.email_provider != "smtp":
        return _result("email", False, f"未知邮件发送方式: {settings.email_provider}")
    required = [settings.smtp_host, settings.smtp_from]
    if not all(required):
        return _result("email", False, "SMTP 配置不完整：至少需要 PIX_WEB_SMTP_HOST 和 PIX_WEB_SMTP_FROM")
    if settings.smtp_port <= 0:
        return _result("email", False, "SMTP 端口无效")
    return _result("email", True, "SMTP 邮件验证码已配置")


def check_queue(settings: WebSettings) -> CheckResult:
    if settings.queue_backend == "database":
        return _result("queue", True, "database 后端，无需 Redis")
    if settings.queue_backend != "rq":
        return _result("queue", False, f"未知队列后端: {settings.queue_backend}")
    try:
        from redis import Redis

        client = Redis.from_url(settings.redis_url)
        client.ping()
    except Exception as exc:
        return _result("queue", False, f"Redis/RQ 不可用: {exc}")
    return _result("queue", True, "Redis 可连接")


def run_checks(settings: WebSettings | None = None) -> list[CheckResult]:
    loaded = settings or load_web_settings()
    return [
        check_jwt_secret(loaded),
        check_packy_key(),
        check_database(loaded),
        check_alembic_head(loaded),
        check_storage(loaded),
        check_payment_providers(loaded),
        check_email_delivery(loaded),
        check_queue(loaded),
    ]


def main() -> None:
    results = run_checks()
    for item in results:
        prefix = "OK" if item.ok else "FAIL"
        print(f"[{prefix}] {item.name}: {item.message}")
    if not all(item.ok for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
