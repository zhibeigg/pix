"""运营保护系统设置。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix_web.models import GenerationJob, SystemSetting, User

DEFAULT_SYSTEM_SETTINGS: dict[str, str] = {
    "generation_enabled": "true",
    "max_pending_jobs_per_user": "5",
    "daily_job_limit_per_user": "50",
}

ALLOWED_SETTING_KEYS = set(DEFAULT_SYSTEM_SETTINGS)
ACTIVE_JOB_STATUSES = {"pending", "running"}


@dataclass(frozen=True)
class OperationalSettings:
    generation_enabled: bool
    max_pending_jobs_per_user: int
    daily_job_limit_per_user: int


def ensure_default_system_settings(db: Session) -> None:
    changed = False
    for key, value in DEFAULT_SYSTEM_SETTINGS.items():
        exists = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if exists is None:
            db.add(SystemSetting(key=key, value=value))
            changed = True
    if changed:
        db.commit()


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _parse_positive_int(value: str, fallback: int) -> int:
    try:
        return max(0, int(value))
    except ValueError:
        return fallback


def get_system_setting(db: Session, key: str) -> SystemSetting:
    if key not in ALLOWED_SETTING_KEYS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统设置不存在")
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        setting = SystemSetting(key=key, value=DEFAULT_SYSTEM_SETTINGS[key])
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def list_system_settings(db: Session) -> list[SystemSetting]:
    ensure_default_system_settings(db)
    return list(db.scalars(select(SystemSetting).order_by(SystemSetting.key.asc())))


def update_system_setting(db: Session, key: str, value: str) -> SystemSetting:
    setting = get_system_setting(db, key)
    clean = value.strip()
    if key == "generation_enabled":
        clean = "true" if _parse_bool(clean) else "false"
    else:
        clean = str(_parse_positive_int(clean, int(DEFAULT_SYSTEM_SETTINGS[key])))
    setting.value = clean
    db.commit()
    db.refresh(setting)
    return setting


def load_operational_settings(db: Session) -> OperationalSettings:
    ensure_default_system_settings(db)
    values = {setting.key: setting.value for setting in db.scalars(select(SystemSetting))}
    return OperationalSettings(
        generation_enabled=_parse_bool(values.get("generation_enabled", DEFAULT_SYSTEM_SETTINGS["generation_enabled"])),
        max_pending_jobs_per_user=_parse_positive_int(
            values.get("max_pending_jobs_per_user", DEFAULT_SYSTEM_SETTINGS["max_pending_jobs_per_user"]),
            int(DEFAULT_SYSTEM_SETTINGS["max_pending_jobs_per_user"]),
        ),
        daily_job_limit_per_user=_parse_positive_int(
            values.get("daily_job_limit_per_user", DEFAULT_SYSTEM_SETTINGS["daily_job_limit_per_user"]),
            int(DEFAULT_SYSTEM_SETTINGS["daily_job_limit_per_user"]),
        ),
    )


def _utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def enforce_generation_limits(db: Session, user: User, *, new_jobs: int) -> None:
    settings = load_operational_settings(db)
    if not settings.generation_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前生成服务已暂停")
    if new_jobs <= 0:
        return

    active_count = db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.user_id == user.id,
            GenerationJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    ) or 0

    if settings.max_pending_jobs_per_user > 0 and active_count + new_jobs > settings.max_pending_jobs_per_user:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="当前排队任务过多，请等待部分任务完成")

    today_count = db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.user_id == user.id,
            GenerationJob.created_at >= _utc_day_start(),
        )
    ) or 0
    if settings.daily_job_limit_per_user > 0 and today_count + new_jobs > settings.daily_job_limit_per_user:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="今日生成次数已达上限")
