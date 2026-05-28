"""管理员可管理的系统设置与运行时配置合并。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timezone
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pix.api.prompt_guard import local_prompt_guard
from pix.config import AppConfig, load_config
from pix_web.config import WebSettings
from pix_web.models import GenerationJob, SystemSetting, UploadEvent, User

SettingType = Literal["string", "number", "boolean", "textarea", "select", "secret", "status"]
SettingSource = Literal["database", "environment_only"]


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    category: str
    type: SettingType
    default: str = ""
    help: str = ""
    options: tuple[str, ...] = ()
    secret: bool = False
    restart_required: bool = False
    editable: bool = True
    env_var: str = ""
    source: SettingSource = "database"


@dataclass(frozen=True)
class AdminSettingView:
    key: str
    value: str
    updated_at: datetime | None
    label: str
    category: str
    type: SettingType
    help: str
    options: tuple[str, ...]
    secret: bool
    masked: bool
    restart_required: bool
    editable: bool
    env_var: str
    source: SettingSource


@dataclass(frozen=True)
class OperationalSettings:
    generation_enabled: bool
    daily_job_limit_per_user: int
    blocked_prompt_terms: str
    max_uploads_per_user_per_day: int
    registration_bonus_credits: int


@dataclass(frozen=True)
class ReferralSettings:
    enabled: bool
    commission_rate_bps: int
    pending_days: int


@dataclass(frozen=True)
class PublicAnnouncement:
    enabled: bool
    title: str
    body: str
    updated_at: datetime | None


SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition("generation_enabled", "生成总开关", "运营保护", "boolean", "true", "关闭后普通用户不能创建新生成任务。"),
    SettingDefinition("max_pending_jobs_per_user", "每用户排队/运行上限（已停用）", "运营保护", "number", "0", "并发限制已取消；该字段仅兼容旧配置，不再限制任务提交。", editable=False),
    SettingDefinition("daily_job_limit_per_user", "每用户每日任务上限", "运营保护", "number", "50", "0 表示不限制。"),
    SettingDefinition("max_uploads_per_user_per_day", "每用户每日上传上限", "运营保护", "number", "50", "0 表示不限制。"),
    SettingDefinition("registration_bonus_credits", "注册赠送点数", "运营保护", "number", "30", "新用户注册时赠送的点数，0 表示不赠送。"),
    SettingDefinition("site.announcement.enabled", "系统公告启用", "系统公告", "boolean", "false", "启用后会在顶部公告按钮内展示给所有访客和登录用户。"),
    SettingDefinition("site.announcement.title", "系统公告标题", "系统公告", "string", "", "公告标题，建议 8-24 个字。"),
    SettingDefinition("site.announcement.body", "系统公告正文", "系统公告", "textarea", "", "公告正文，可用于维护通知、活动说明或版本提醒。"),
    SettingDefinition("referral.enabled", "邀请奖励开关", "邀请奖励", "boolean", "true", "关闭后不再绑定新邀请或生成新返佣。"),
    SettingDefinition("referral.commission_rate_bps", "返佣比例 bps", "邀请奖励", "number", "1000", "1000 = 10%；按好友实际支付金额计算。"),
    SettingDefinition("referral.pending_days", "待到账天数", "邀请奖励", "number", "30", "好友充值后返佣进入待到账，达到天数后转为可用收益。"),
    SettingDefinition("blocked_prompt_terms", "素材描述禁词", "运营保护", "textarea", "", "逗号、分号或换行分隔。"),
    SettingDefinition("web.email_provider", "邮件发送方式", "邮件验证码", "select", "", "console 适合开发；smtp 用于生产投递。", ("console", "smtp")),
    SettingDefinition("web.smtp_host", "SMTP Host", "邮件验证码", "string", "", "例如 smtp.example.com。", env_var="PIX_WEB_SMTP_HOST"),
    SettingDefinition("web.smtp_port", "SMTP Port", "邮件验证码", "number", "", "常用 587/465/25。", env_var="PIX_WEB_SMTP_PORT"),
    SettingDefinition("web.smtp_user", "SMTP 用户名", "邮件验证码", "string", "", env_var="PIX_WEB_SMTP_USER"),
    SettingDefinition("web.smtp_password", "SMTP 密码", "邮件验证码", "secret", "", "保存到数据库会被遮罩显示；生产建议用环境变量或密钥管理。", secret=True, env_var="PIX_WEB_SMTP_PASSWORD"),
    SettingDefinition("web.smtp_from", "发件人", "邮件验证码", "string", "", "例如 Pix <noreply@example.com>。", env_var="PIX_WEB_SMTP_FROM"),
    SettingDefinition("web.smtp_tls", "启用 STARTTLS", "邮件验证码", "boolean", "", env_var="PIX_WEB_SMTP_TLS"),
    SettingDefinition("web.smtp_ssl", "启用 SSL/465", "邮件验证码", "boolean", "", "用于 465 端口 implicit SSL；启用后不会再执行 STARTTLS。", env_var="PIX_WEB_SMTP_SSL"),
    SettingDefinition("web.email_code_ttl_seconds", "验证码有效期（秒）", "邮件验证码", "number", "", env_var="PIX_WEB_EMAIL_CODE_TTL_SECONDS"),
    SettingDefinition("web.email_code_resend_seconds", "重发间隔（秒）", "邮件验证码", "number", "", env_var="PIX_WEB_EMAIL_CODE_RESEND_SECONDS"),
    SettingDefinition("web.email_code_max_attempts", "最大错误次数", "邮件验证码", "number", "", env_var="PIX_WEB_EMAIL_CODE_MAX_ATTEMPTS"),
    SettingDefinition("web.email_debug_codes", "响应返回调试验证码", "邮件验证码", "boolean", "", "仅开发/内测建议启用。", env_var="PIX_WEB_EMAIL_DEBUG_CODES"),
    SettingDefinition("web.public_base_url", "后端公开 URL", "支付与站点", "string", "", "用于支付异步通知和后端返回入口，例如 https://api.example.com。", env_var="PIX_WEB_PUBLIC_BASE_URL"),
    SettingDefinition("web.frontend_base_url", "前端公开 URL", "支付与站点", "string", "", "支付完成后浏览器跳回的 Pix 前端地址，例如 https://www.example.com。留空时会优先使用当前请求来源/CORS 来源。", env_var="PIX_WEB_FRONTEND_BASE_URL"),
    SettingDefinition("pix.api.base_url", "Packy API Base URL", "模型与 API", "string", "", env_var="PACKY_BASE_URL"),
    SettingDefinition("pix.api.image_api_key", "Packy 生图 API Key", "模型与 API", "secret", "", "可覆盖 PACKY_API_KEY。生产建议使用环境变量。", secret=True, env_var="PACKY_API_KEY"),
    SettingDefinition("pix.api.vl_api_key", "Packy VL API Key", "模型与 API", "secret", "", "可覆盖 PACKY_VL_API_KEY。生产建议使用环境变量。", secret=True, env_var="PACKY_VL_API_KEY"),
    SettingDefinition("pix.image_gen.model", "生图模型", "模型与 API", "string", ""),
    SettingDefinition("pix.image_gen.size", "源图尺寸", "模型与 API", "select", "", options=("1024x1024", "1536x1024", "1024x1536")),
    SettingDefinition("pix.image_gen.quality", "生图质量", "模型与 API", "select", "", options=("low", "medium", "high", "auto")),
    SettingDefinition("pix.image_gen.output_format", "源图格式", "模型与 API", "select", "", options=("png", "jpeg", "webp")),
    SettingDefinition("pix.image_gen.edit_input_fidelity", "图生图保真", "模型与 API", "select", "", options=("low", "high")),
    SettingDefinition("pix.image_gen.contact_sheet_enabled", "默认九宫格候选", "模型与 API", "boolean", ""),
    SettingDefinition("pix.image_gen.contact_sheet_rows", "候选行数", "模型与 API", "number", ""),
    SettingDefinition("pix.image_gen.contact_sheet_cols", "候选列数", "模型与 API", "number", ""),
    SettingDefinition("pix.image_gen.green_screen_color", "抠色背景", "模型与 API", "string", ""),
    SettingDefinition("pix.image_gen.green_screen_tolerance", "抠色容差", "模型与 API", "number", ""),
    SettingDefinition("pix.image_gen.contact_sheet_prompt_template", "九宫格 Prompt 模板", "模型与 API", "textarea", ""),
    SettingDefinition("pix.image_gen.prompt_guard_enabled", "启用描述审核", "模型与 API", "boolean", ""),
    SettingDefinition("pix.image_gen.prompt_guard_remote", "启用模型描述审核", "模型与 API", "boolean", ""),
    SettingDefinition("pix.image_gen.prompt_guard_model", "描述审核模型", "模型与 API", "string", ""),
    SettingDefinition("pix.image_gen.prompt_guard_failure_policy", "审核失败策略", "模型与 API", "select", "", options=("local", "reject")),
    SettingDefinition("pix.image_gen.prompt_guard_max_chars", "描述最大字符数", "模型与 API", "number", ""),
    SettingDefinition("pix.image_gen.candidate_vl_ranking_enabled", "候选 VL 评分排序", "模型与 API", "boolean", ""),
    SettingDefinition("pix.image_gen.candidate_vl_ranking_model", "候选评分模型", "模型与 API", "string", "", "留空使用 VL 模型。"),
    SettingDefinition("pix.image_gen.candidate_vl_ranking_failure_policy", "候选评分失败策略", "模型与 API", "select", "", options=("first", "reject")),
    SettingDefinition("pix.image_gen.candidate_mode", "候选生成模式", "模型与 API", "select", "n_sample 直接调用 n=N 拿独立 full-res 图（推荐，质量更高）；contact_sheet 走旧 RxC 九宫格切图。", options=("n_sample", "contact_sheet")),
    SettingDefinition("pix.image_gen.n_sample_count", "n-sample 候选数", "模型与 API", "number", "n_sample 模式下生成的独立图片数；建议 4~6。"),
    SettingDefinition("pix.vision.model", "VL 模型", "模型与 API", "string", ""),
    SettingDefinition("pix.vision.temperature", "VL 温度", "模型与 API", "number", ""),
    SettingDefinition("pix.vision.max_tokens", "VL 最大输出 tokens", "模型与 API", "number", ""),
    SettingDefinition("pix.vision.retry_on_parse", "VL 解析失败重试", "模型与 API", "number", ""),
    SettingDefinition("pix.pixelize.generated_preprocess_method", "生成图预处理", "素材默认值", "select", "", "perfect_pixel=AI 生图/图生图源图先做网格对齐；legacy/none=旧流程。", options=("perfect_pixel", "legacy", "none")),
    SettingDefinition("pix.asset.pixel_size", "默认素材尺寸", "素材默认值", "string", "", "格式 16x16。"),
    SettingDefinition("pix.asset.colors", "默认颜色数", "素材默认值", "number", ""),
    SettingDefinition("pix.asset.image_quality", "素材源图质量", "素材默认值", "select", "", options=("low", "medium", "high", "auto")),
    SettingDefinition("pix.asset.skip_vl", "默认跳过普通 VL 分析", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.remove_bg", "默认移除背景", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.bg_tolerance", "背景容差", "素材默认值", "number", ""),
    SettingDefinition("pix.asset.bg_feather", "边缘强度", "素材默认值", "number", "feather=羽化半径；outline=描边宽度；hard=不额外处理。"),
    SettingDefinition("pix.asset.edge_style", "默认边缘处理", "素材默认值", "select", "hard=不需要；feather=羽化边缘；outline=描边。", options=("hard", "feather", "outline")),
    SettingDefinition("pix.asset.bg_removal_algorithm", "背景移除算法", "素材默认值", "select", "固定使用 Color-to-Alpha；保留旧选项仅为兼容历史配置。", options=("color_to_alpha", "auto", "flood_fill", "hybrid")),
    SettingDefinition("pix.asset.color_to_alpha_shape", "Color-to-Alpha 距离", "素材默认值", "select", "sphere=欧氏距离；cube=最大通道差。", options=("sphere", "cube")),
    SettingDefinition("pix.asset.color_to_alpha_transparency", "CTA 透明阈值", "素材默认值", "number", "小于等于该距离的 key 色转全透明。"),
    SettingDefinition("pix.asset.color_to_alpha_opacity", "CTA 不透明阈值", "素材默认值", "number", "大于等于该距离的颜色保持不透明。"),
    SettingDefinition("pix.asset.color_to_alpha_interpolation", "CTA 插值", "素材默认值", "select", "透明到不透明的过渡曲线。", options=("linear", "smooth", "power", "root", "inverse-sin")),
    SettingDefinition("pix.asset.auto_crop", "自动裁剪主体", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.crop_padding", "裁剪留白", "素材默认值", "number", ""),
    SettingDefinition("pix.asset.crop_square", "裁剪为正方形", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.palette_mode", "调色板模式", "素材默认值", "select", "auto=经典 K-means/旧效果；ramp=VL 按色相阶梯设计 + Lab 最近色量化。", options=("auto", "ramp", "kmeans")),
    SettingDefinition("pix.asset.grid_mode", "默认输出 Pixel Grid", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.grid_cleanup", "Grid 清理噪点", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.grid_outline", "Grid 轮廓后处理", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.grid_outline_strength", "轮廓强度", "素材默认值", "number", ""),
    SettingDefinition("pix.asset.fit_canvas", "贴合画布", "素材默认值", "boolean", ""),
    SettingDefinition("pix.asset.fit_mode", "贴合模式", "素材默认值", "select", "", options=("smart", "contain", "cover")),
    SettingDefinition("pix.asset.fit_padding", "贴合留白", "素材默认值", "number", ""),
    SettingDefinition("pix.asset.fit_min_axis_coverage", "主体最小覆盖率", "素材默认值", "number", ""),
    SettingDefinition("pix.asset.prompt_template", "素材 Prompt 模板", "素材默认值", "textarea", "", "可用占位符：{width}/{height}/{name}/{max_colors}/{colors}/{key_tolerance}，也兼容 {green}/{key_color}/{size_label}/{asset_kind_label}/{asset_usage_label}/{subject_kind_label}/{placement_context}/{forbidden_elements}/{canvas_shape}；物品图标与 UI 组件语义会按 asset_kind 分开，不要在同一模板写死 inventory/UI。"),
    SettingDefinition("pix.sprite.frame_count", "默认帧数", "序列帧", "number", "", "用户未指定时使用；提交时仍限制 1-12 帧。"),
    SettingDefinition("pix.sprite.max_frame_count", "最大帧数", "序列帧", "number", "", "序列帧上限，默认 12。前后端都会校验。"),
    SettingDefinition("pix.sprite.fps", "默认播放 FPS", "序列帧", "number", ""),
    SettingDefinition("pix.sprite.pixel_size", "单帧尺寸", "序列帧", "string", "", "格式 64x64。"),
    SettingDefinition("pix.sprite.colors", "单帧颜色数", "序列帧", "number", ""),
    SettingDefinition("pix.sprite.image_quality", "序列帧源图质量", "序列帧", "select", "", options=("low", "medium", "high", "auto")),
    SettingDefinition("pix.sprite.gif_export", "兼容 GIF 导出", "序列帧", "boolean", "默认关闭；作品库优先播放 sprite_sheet.png + sequence.json。"),
    SettingDefinition("pix.sprite.frame_size_step", "有效尺寸取整步长", "序列帧", "number", "默认 16 像素。"),
    SettingDefinition("pix.sprite.oversize_regenerate_threshold", "异常帧阈值", "序列帧", "number", "超过目标尺寸的倍数后重试，默认 1.5。"),
    SettingDefinition("pix.sprite.max_frame_retries", "单帧最大重试", "序列帧", "number", ""),
    SettingDefinition("pix.sprite.anchor", "帧锚点", "序列帧", "select", "默认 bottom_center。", options=("bottom_center", "center")),
    SettingDefinition("pix.sprite.green_screen_color", "序列帧抠色背景", "序列帧", "string", ""),
    SettingDefinition("pix.sprite.green_screen_tolerance", "序列帧抠色容差", "序列帧", "number", ""),
    SettingDefinition("pix.sprite.crop_padding", "裁剪留白（兼容）", "序列帧", "number", "保留给旧配置兼容；新流程按透明内容包围盒与有效单帧尺寸补齐。"),
    SettingDefinition("pix.sprite.shared_palette", "序列帧共享调色板", "序列帧", "boolean", "减少逐帧播放闪色。"),
    SettingDefinition("pix.sprite.prompt_template", "首帧 Prompt 模板", "序列帧", "textarea", ""),
    SettingDefinition("pix.sprite.next_frame_prompt_template", "后续帧 Prompt 模板", "序列帧", "textarea", ""),
    SettingDefinition("web.poll_interval_seconds", "Worker 轮询间隔", "存储 / 队列 / 安全", "number", "", "保存后需重启 worker 才能稳定生效。", restart_required=True, env_var="PIX_WEB_POLL_INTERVAL_SECONDS"),
    SettingDefinition("web.worker_concurrency", "Worker 并发上限", "存储 / 队列 / 安全", "number", "", "空闲槽位内任务会直接并发运行；超过该上限才保持排队。保存后需重启 worker。", restart_required=True, env_var="PIX_WEB_WORKER_CONCURRENCY"),
    SettingDefinition("web.access_token_minutes", "登录 token 有效分钟", "存储 / 队列 / 安全", "number", "", "新签发 token 生效；不影响已签发 token。", env_var="PIX_WEB_ACCESS_TOKEN_MINUTES"),
    SettingDefinition("env.database_url", "数据库连接", "存储 / 队列 / 安全", "status", "", "环境级配置，只显示状态，不在线修改。", editable=False, env_var="PIX_WEB_DATABASE_URL", source="environment_only"),
    SettingDefinition("env.jwt_secret", "JWT Secret", "存储 / 队列 / 安全", "status", "", "环境级配置；在线修改会导致现有 token 失效，第一阶段不提供。", secret=True, editable=False, env_var="PIX_WEB_JWT_SECRET", source="environment_only"),
    SettingDefinition("env.storage_root", "存储目录", "存储 / 队列 / 安全", "status", "", "环境级配置，只显示当前目录。", editable=False, env_var="PIX_WEB_STORAGE_ROOT", source="environment_only"),
    SettingDefinition("env.queue_backend", "队列后端", "存储 / 队列 / 安全", "status", "", "需重启服务/worker。", editable=False, restart_required=True, env_var="PIX_WEB_QUEUE_BACKEND", source="environment_only"),
    SettingDefinition("env.redis_url", "Redis URL", "存储 / 队列 / 安全", "status", "", "需重启服务/worker。", secret=True, editable=False, restart_required=True, env_var="PIX_WEB_REDIS_URL", source="environment_only"),
    SettingDefinition("env.alipay_mode", "支付宝模式", "支付与站点", "status", "", "auto 会在检测到证书配置时自动使用证书模式。", editable=False, env_var="ALIPAY_MODE", source="environment_only"),
    SettingDefinition("env.alipay_app_id", "支付宝 App ID", "支付与站点", "status", "", "环境级配置，只显示是否配置。", editable=False, env_var="ALIPAY_APP_ID", source="environment_only"),
    SettingDefinition("env.alipay_private_key", "支付宝私钥", "支付与站点", "status", "", "高风险密钥，仅显示是否配置。", secret=True, editable=False, env_var="ALIPAY_PRIVATE_KEY", source="environment_only"),
    SettingDefinition("env.alipay_public_key", "支付宝公钥", "支付与站点", "status", "", "公钥模式验签使用。", secret=True, editable=False, env_var="ALIPAY_PUBLIC_KEY", source="environment_only"),
    SettingDefinition("env.alipay_app_cert", "支付宝应用公钥证书", "支付与站点", "status", "", "证书模式下用于 app_cert_sn。", secret=True, editable=False, env_var="ALIPAY_APP_CERT", source="environment_only"),
    SettingDefinition("env.alipay_public_cert", "支付宝公钥证书", "支付与站点", "status", "", "证书模式下用于回调验签。", secret=True, editable=False, env_var="ALIPAY_PUBLIC_CERT", source="environment_only"),
    SettingDefinition("env.alipay_root_cert", "支付宝根证书", "支付与站点", "status", "", "证书模式下用于 alipay_root_cert_sn。", secret=True, editable=False, env_var="ALIPAY_ROOT_CERT", source="environment_only"),
    SettingDefinition("env.wechat_private_key", "微信支付私钥", "支付与站点", "status", "", "高风险密钥，第一阶段仅显示是否配置。", secret=True, editable=False, env_var="WECHATPAY_PRIVATE_KEY", source="environment_only"),
)

SETTING_DEFINITIONS_BY_KEY = {definition.key: definition for definition in SETTING_DEFINITIONS}
DEFAULT_SYSTEM_SETTINGS: dict[str, str] = {
    definition.key: definition.default
    for definition in SETTING_DEFINITIONS
    if definition.key in {
        "generation_enabled",
        "max_pending_jobs_per_user",
        "daily_job_limit_per_user",
        "blocked_prompt_terms",
        "max_uploads_per_user_per_day",
        "registration_bonus_credits",
        "site.announcement.enabled",
        "site.announcement.title",
        "site.announcement.body",
        "referral.enabled",
        "referral.commission_rate_bps",
        "referral.pending_days",
    }
}
ALLOWED_SETTING_KEYS = set(SETTING_DEFINITIONS_BY_KEY)


def ensure_default_system_settings(db: Session) -> None:
    changed = False
    for key, value in DEFAULT_SYSTEM_SETTINGS.items():
        exists = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if exists is None:
            db.add(SystemSetting(key=key, value=value))
            changed = True
    if changed:
        db.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _parse_positive_int(value: str, fallback: int) -> int:
    try:
        return max(0, int(value))
    except ValueError:
        return fallback


def _definition_for(key: str) -> SettingDefinition:
    definition = SETTING_DEFINITIONS_BY_KEY.get(key)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统设置不存在")
    return definition


def get_system_setting(db: Session, key: str) -> SystemSetting:
    definition = _definition_for(key)
    if not definition.editable or definition.source != "database":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该设置不可在线修改")
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        setting = SystemSetting(key=key, value=definition.default)
        db.add(setting)
        db.flush()
    return setting


def _rows_by_key(db: Session) -> dict[str, SystemSetting]:
    ensure_default_system_settings(db)
    return {setting.key: setting for setting in db.scalars(select(SystemSetting))}


def _pix_default_value(cfg: AppConfig, key: str) -> str:
    _, section, field = key.split(".", 2)
    section_obj = getattr(cfg, section, None)
    if section_obj is None:
        return ""
    value = getattr(section_obj, field, "")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return "x".join(str(part) for part in value)
    return "" if value is None else str(value)


def _web_default_value(settings: WebSettings, key: str) -> str:
    field = key.split(".", 1)[1]
    value = getattr(settings, field, "")
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def _env_status_value(settings: WebSettings, definition: SettingDefinition) -> str:
    mapping = {
        "env.database_url": settings.database_url,
        "env.jwt_secret": settings.jwt_secret,
        "env.storage_root": str(settings.storage_root),
        "env.queue_backend": settings.queue_backend,
        "env.redis_url": settings.redis_url,
        "env.alipay_mode": settings.alipay_mode,
        "env.alipay_app_id": settings.alipay_app_id,
        "env.alipay_private_key": settings.alipay_private_key,
        "env.alipay_public_key": settings.alipay_public_key,
        "env.alipay_app_cert": settings.alipay_app_cert,
        "env.alipay_public_cert": settings.alipay_public_cert,
        "env.alipay_root_cert": settings.alipay_root_cert,
        "env.wechat_private_key": settings.wechat_private_key,
    }
    raw = mapping.get(definition.key, "")
    if definition.secret:
        return "已配置" if raw else "未配置"
    return raw or "未配置"


def _default_value(definition: SettingDefinition, settings: WebSettings, cfg: AppConfig) -> str:
    if definition.key.startswith("web."):
        return _web_default_value(settings, definition.key)
    if definition.key.startswith("pix."):
        return _pix_default_value(cfg, definition.key)
    if definition.key.startswith("env."):
        return _env_status_value(settings, definition)
    return definition.default


def list_system_settings(db: Session) -> list[SystemSetting]:
    """兼容旧接口：仅返回已持久化的 SystemSetting。"""
    ensure_default_system_settings(db)
    return list(db.scalars(select(SystemSetting).order_by(SystemSetting.key.asc())))


def list_admin_settings(db: Session, settings: WebSettings) -> list[AdminSettingView]:
    rows = _rows_by_key(db)
    cfg = load_config(config_file=settings.pix_config_file)
    views: list[AdminSettingView] = []
    for definition in SETTING_DEFINITIONS:
        row = rows.get(definition.key)
        stored_value = row.value if row is not None else None
        effective_value = stored_value if stored_value is not None else _default_value(definition, settings, cfg)
        masked = bool(definition.secret and effective_value)
        views.append(
            AdminSettingView(
                key=definition.key,
                value="" if masked else effective_value,
                updated_at=row.updated_at if row is not None else None,
                label=definition.label,
                category=definition.category,
                type=definition.type,
                help=definition.help,
                options=definition.options,
                secret=definition.secret,
                masked=masked,
                restart_required=definition.restart_required,
                editable=definition.editable,
                env_var=definition.env_var,
                source=definition.source,
            )
        )
    return views


def _normalize_value(definition: SettingDefinition, value: str) -> str:
    clean = value.strip()
    if definition.type == "boolean":
        return "true" if _parse_bool(clean) else "false"
    if definition.type == "number":
        try:
            number = float(clean) if "." in clean else int(clean)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="数字格式不正确") from exc
        if isinstance(number, float):
            return str(number)
        return str(max(0, number))
    if definition.type == "select" and definition.options and clean not in definition.options:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="选项不合法")
    if definition.key in {"pix.asset.pixel_size", "pix.sprite.pixel_size"} and "x" not in clean.lower():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="尺寸格式应为 16x16")
    return clean


def update_system_setting(db: Session, key: str, value: str, *, clear: bool = False) -> SystemSetting:
    definition = _definition_for(key)
    if not definition.editable or definition.source != "database":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该设置不可在线修改")
    setting = get_system_setting(db, key)
    if definition.secret and value == "" and not clear:
        db.commit()
        db.refresh(setting)
        return setting
    setting.value = "" if clear else _normalize_value(definition, value)
    db.commit()
    db.refresh(setting)
    return setting


def _stored_values(db: Session) -> dict[str, str]:
    ensure_default_system_settings(db)
    return {setting.key: setting.value for setting in db.scalars(select(SystemSetting))}


def load_operational_settings(db: Session) -> OperationalSettings:
    values = _stored_values(db)
    return OperationalSettings(
        generation_enabled=_parse_bool(values.get("generation_enabled", DEFAULT_SYSTEM_SETTINGS["generation_enabled"])),
        daily_job_limit_per_user=_parse_positive_int(
            values.get("daily_job_limit_per_user", DEFAULT_SYSTEM_SETTINGS["daily_job_limit_per_user"]),
            int(DEFAULT_SYSTEM_SETTINGS["daily_job_limit_per_user"]),
        ),
        blocked_prompt_terms=values.get("blocked_prompt_terms", DEFAULT_SYSTEM_SETTINGS["blocked_prompt_terms"]),
        max_uploads_per_user_per_day=_parse_positive_int(
            values.get("max_uploads_per_user_per_day", DEFAULT_SYSTEM_SETTINGS["max_uploads_per_user_per_day"]),
            int(DEFAULT_SYSTEM_SETTINGS["max_uploads_per_user_per_day"]),
        ),
        registration_bonus_credits=_parse_positive_int(
            values.get("registration_bonus_credits", DEFAULT_SYSTEM_SETTINGS["registration_bonus_credits"]),
            int(DEFAULT_SYSTEM_SETTINGS["registration_bonus_credits"]),
        ),
    )


def load_public_announcement(db: Session) -> PublicAnnouncement:
    rows = _rows_by_key(db)
    enabled_row = rows.get("site.announcement.enabled")
    title_row = rows.get("site.announcement.title")
    body_row = rows.get("site.announcement.body")
    enabled = _parse_bool(enabled_row.value if enabled_row is not None else DEFAULT_SYSTEM_SETTINGS["site.announcement.enabled"])
    title = (title_row.value if title_row is not None else DEFAULT_SYSTEM_SETTINGS["site.announcement.title"]).strip()
    body = (body_row.value if body_row is not None else DEFAULT_SYSTEM_SETTINGS["site.announcement.body"]).strip()
    updated_candidates = [row.updated_at for row in (enabled_row, title_row, body_row) if row is not None and row.updated_at is not None]
    effective_enabled = enabled and bool(title or body)
    return PublicAnnouncement(enabled=effective_enabled, title=title, body=body, updated_at=max(updated_candidates) if updated_candidates else None)


def load_referral_settings(db: Session) -> ReferralSettings:
    values = _stored_values(db)
    return ReferralSettings(
        enabled=_parse_bool(values.get("referral.enabled", DEFAULT_SYSTEM_SETTINGS["referral.enabled"])),
        commission_rate_bps=min(
            10000,
            _parse_positive_int(
                values.get("referral.commission_rate_bps", DEFAULT_SYSTEM_SETTINGS["referral.commission_rate_bps"]),
                int(DEFAULT_SYSTEM_SETTINGS["referral.commission_rate_bps"]),
            ),
        ),
        pending_days=_parse_positive_int(
            values.get("referral.pending_days", DEFAULT_SYSTEM_SETTINGS["referral.pending_days"]),
            int(DEFAULT_SYSTEM_SETTINGS["referral.pending_days"]),
        ),
    )


def _coerce_to_current_type(raw: str, current: Any) -> Any:
    if isinstance(current, bool):
        return _parse_bool(raw)
    if isinstance(current, int) and not isinstance(current, bool):
        return int(float(raw))
    if isinstance(current, float):
        return float(raw)
    return raw


def load_effective_web_settings(db: Session, base_settings: WebSettings) -> WebSettings:
    values = _stored_values(db)
    changes: dict[str, Any] = {}
    for key, raw in values.items():
        if not key.startswith("web."):
            continue
        definition = SETTING_DEFINITIONS_BY_KEY.get(key)
        if definition is None or not definition.editable:
            continue
        field = key.split(".", 1)[1]
        if not hasattr(base_settings, field):
            continue
        if definition.secret and raw == "":
            continue
        current = getattr(base_settings, field)
        try:
            changes[field] = _coerce_to_current_type(raw, current)
        except (TypeError, ValueError):
            continue
    return replace(base_settings, **changes) if changes else base_settings


def _native_pix_value(key: str, raw: str) -> Any:
    if key in {"pix.asset.pixel_size", "pix.sprite.pixel_size"}:
        left, right = raw.lower().split("x", 1)
        return [int(left), int(right)]
    default_cfg = load_config(env_file=None)
    _, section, field = key.split(".", 2)
    current = getattr(getattr(default_cfg, section), field)
    return _coerce_to_current_type(raw, current)


def managed_pix_overrides_from_db(db: Session) -> dict[str, dict[str, Any]]:
    values = _stored_values(db)
    overrides: dict[str, dict[str, Any]] = {}
    for key, raw in values.items():
        if not key.startswith("pix."):
            continue
        definition = SETTING_DEFINITIONS_BY_KEY.get(key)
        if definition is None or not definition.editable:
            continue
        if definition.secret and raw == "":
            continue
        try:
            _, section, field = key.split(".", 2)
            overrides.setdefault(section, {})[field] = _native_pix_value(key, raw)
        except (TypeError, ValueError):
            continue
    return overrides


def load_managed_pix_config(db: Session, settings: WebSettings) -> AppConfig:
    return load_config(config_file=settings.pix_config_file, overrides=managed_pix_overrides_from_db(db))


def _utc_day_start() -> datetime:
    now = _now()
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def _blocked_terms(raw: str) -> list[str]:
    normalized = raw.replace("，", ",").replace(";", ",").replace("；", ",").replace("\n", ",")
    return [part.strip().lower() for part in normalized.split(",") if part.strip()]


def enforce_prompt_policy(
    db: Session,
    prompt: str | None,
    *,
    allow_template_break: bool = False,
    max_chars: int | None = None,
) -> None:
    if not prompt:
        return
    prompt_guard_kwargs = {"max_chars": max_chars} if max_chars is not None else {}
    local = local_prompt_guard(
        prompt,
        allow_template_break=allow_template_break,
        **prompt_guard_kwargs,
    )
    if not local.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=local.reason or "prompt 包含不允许的内容")
    settings = load_operational_settings(db)
    text = prompt.lower()
    for term in _blocked_terms(settings.blocked_prompt_terms):
        if term in text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="prompt 包含不允许的内容")


def enforce_upload_limit(db: Session, user: User) -> None:
    settings = load_operational_settings(db)
    limit = settings.max_uploads_per_user_per_day
    if limit <= 0:
        return
    today_count = db.scalar(
        select(func.count()).select_from(UploadEvent).where(
            UploadEvent.user_id == user.id,
            UploadEvent.created_at >= _utc_day_start(),
        )
    ) or 0
    if today_count >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="今日上传次数已达上限")


def record_upload_event(db: Session, user: User, *, filename: str, content_type: str, size_bytes: int) -> UploadEvent:
    event = UploadEvent(user_id=user.id, filename=filename, content_type=content_type, size_bytes=size_bytes)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def enforce_generation_limits(db: Session, user: User, *, new_jobs: int) -> None:
    settings = load_operational_settings(db)
    if not settings.generation_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前生成服务已暂停")
    if new_jobs <= 0:
        return

    today_count = db.scalar(
        select(func.count()).select_from(GenerationJob).where(
            GenerationJob.user_id == user.id,
            GenerationJob.created_at >= _utc_day_start(),
        )
    ) or 0
    if settings.daily_job_limit_per_user > 0 and today_count + new_jobs > settings.daily_job_limit_per_user:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="今日生成次数已达上限")
