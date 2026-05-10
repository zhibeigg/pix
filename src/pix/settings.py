"""Settings 读写：提供 GUI 侧友好的"保存到 .env + config.toml"入口。

- API key 只写 `.env`，永远不会写进 config.toml
- 模型/基础地址等非敏感项写进 `config.toml`，使之在 CLI 下也一致生效
- 对已有文件做**字段级** partial merge，保留用户的注释与额外配置
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import tomli_w
except ImportError:  # pragma: no cover
    tomli_w = None  # type: ignore[assignment]


_ENV_KEYS = ("PACKY_API_KEY", "PACKY_VL_API_KEY", "PACKY_BASE_URL")


# ---------- 预设的提供商 ----------


@dataclass
class Provider:
    key: str
    label: str
    base_url: str
    default_image_model: str
    default_vision_model: str
    description: str = ""


PROVIDERS: list[Provider] = [
    Provider(
        key="packy",
        label="Packy API（推荐，国内可用）",
        base_url="https://www.packyapi.com",
        default_image_model="gpt-image-2",
        default_vision_model="claude-sonnet-4-5",
        description="gpt-image-2 需要 sora 分组令牌；视觉模型用 default 分组令牌。",
    ),
    Provider(
        key="openai",
        label="OpenAI 官方",
        base_url="https://api.openai.com",
        default_image_model="gpt-image-1",
        default_vision_model="gpt-4o",
        description="官方端点；模型名称视账号可用情况调整。",
    ),
    Provider(
        key="custom",
        label="自定义端点",
        base_url="",
        default_image_model="",
        default_vision_model="",
        description="适用于代理或自建 OpenAI 兼容端点。",
    ),
]


def get_provider(key: str) -> Provider:
    for p in PROVIDERS:
        if p.key == key:
            return p
    return PROVIDERS[-1]  # custom


def detect_provider(base_url: str) -> Provider:
    """根据 base_url 猜提供商。"""
    u = (base_url or "").rstrip("/")
    for p in PROVIDERS:
        if p.base_url and p.base_url.rstrip("/") == u:
            return p
    return get_provider("custom")


# ---------- UI 使用的数据对象 ----------


@dataclass
class UserSettings:
    provider_key: str = "packy"
    base_url: str = "https://www.packyapi.com"
    image_api_key: str = ""
    vl_api_key: str = ""
    image_model: str = "gpt-image-2"
    image_size: str = "1024x1024"
    image_quality: str = "high"
    vision_model: str = "claude-sonnet-4-5"
    language: str = "zh-CN"

    def to_config_overrides(self) -> dict[str, Any]:
        """导出为 load_config 可用的 overrides（不含 key，key 走环境变量）。"""
        return {
            "api": {"base_url": self.base_url},
            "image_gen": {
                "model": self.image_model,
                "size": self.image_size,
                "quality": self.image_quality,
            },
            "vision": {"model": self.vision_model},
            "ui": {"language": self.language},
        }


# ---------- .env 读写（行级保留） ----------


_ENV_LINE_RE = re.compile(r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=")


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if (len(v) >= 2) and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        result[k] = v
    return result


def write_env_file(path: Path, updates: Mapping[str, str]) -> None:
    """保留原有行与注释，只覆盖 updates 里提到的键；新键追加到末尾。

    传入空字符串表示"删除该行"。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    updates = dict(updates)
    lines: list[str] = []
    seen: set[str] = set()

    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _ENV_LINE_RE.match(raw)
            if not m:
                lines.append(raw)
                continue
            key = m.group("key")
            if key in updates:
                seen.add(key)
                new_val = updates[key]
                if new_val == "":
                    # 注释掉原值，避免无意泄漏
                    lines.append(f"# {raw}")
                else:
                    lines.append(f"{key}={_quote_env_value(new_val)}")
            else:
                lines.append(raw)

    # 追加新增键
    appended_header = False
    for key, val in updates.items():
        if key in seen or not val:
            continue
        if not appended_header:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.append("# Added by pix settings")
            appended_header = True
        lines.append(f"{key}={_quote_env_value(val)}")

    content = "\n".join(lines)
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


def _quote_env_value(v: str) -> str:
    """简单规则：含空格或 `#` 时用双引号包起来。"""
    if any(c in v for c in (" ", "\t", "#")):
        escaped = v.replace('"', '\\"')
        return f'"{escaped}"'
    return v


# ---------- config.toml 读写 ----------


def read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fp:
        return tomllib.load(fp)


def write_toml_merged(path: Path, updates: Mapping[str, Mapping[str, Any]]) -> None:
    """把 updates 深度合并进已有 TOML，保存。

    注：TOML 注释无法无损保留（tomllib/tomli_w 不支持），但我们在每节顶部加一行简要说明。
    """
    if tomli_w is None:  # pragma: no cover
        raise RuntimeError("需要 tomli_w 依赖来写入 config.toml")
    existing = read_toml(path)
    merged = _deep_merge(existing, updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fp:
        tomli_w.dump(merged, fp)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {k: v for k, v in base.items()}
    for k, v in override.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ---------- 统一入口 ----------


@dataclass
class SaveResult:
    env_path: Path
    config_path: Path
    updated_env_keys: list[str]
    updated_config_sections: list[str]


def load_settings(
    env_path: Path = Path(".env"),
    config_path: Path = Path("config.toml"),
) -> UserSettings:
    """把 .env + config.toml 读进 UserSettings 供对话框展示。"""
    env_map = read_env_file(env_path)
    # 环境变量覆盖（进程内已设置时，优先展示实际生效值）
    for k in _ENV_KEYS:
        if os.getenv(k):
            env_map.setdefault(k, os.getenv(k, ""))

    toml_data = read_toml(config_path)
    api = (toml_data.get("api") or {}) if isinstance(toml_data, dict) else {}
    image_gen = toml_data.get("image_gen") or {}
    vision = toml_data.get("vision") or {}
    ui = toml_data.get("ui") or {}

    base_url = env_map.get("PACKY_BASE_URL") or api.get("base_url") or "https://www.packyapi.com"
    provider = detect_provider(base_url)

    return UserSettings(
        provider_key=provider.key,
        base_url=base_url,
        image_api_key=env_map.get("PACKY_API_KEY", ""),
        vl_api_key=env_map.get("PACKY_VL_API_KEY", ""),
        image_model=image_gen.get("model") or provider.default_image_model,
        image_size=image_gen.get("size") or "1024x1024",
        image_quality=image_gen.get("quality") or "high",
        vision_model=vision.get("model") or provider.default_vision_model,
        language=ui.get("language") or "zh-CN",
    )


def save_settings(
    settings: UserSettings,
    env_path: Path = Path(".env"),
    config_path: Path = Path("config.toml"),
) -> SaveResult:
    """把用户设置写入 `.env`（key、base_url）和 `config.toml`（模型等）。"""
    env_updates = {
        "PACKY_API_KEY": settings.image_api_key.strip(),
        "PACKY_VL_API_KEY": settings.vl_api_key.strip(),
        "PACKY_BASE_URL": settings.base_url.strip(),
    }
    write_env_file(env_path, env_updates)

    config_updates = {
        "api": {"base_url": settings.base_url.strip()},
        "image_gen": {
            "model": settings.image_model.strip(),
            "size": settings.image_size.strip(),
            "quality": settings.image_quality.strip(),
        },
        "vision": {"model": settings.vision_model.strip()},
        "ui": {"language": settings.language.strip() or "zh-CN"},
    }
    write_toml_merged(config_path, config_updates)

    # 当前进程里的环境变量也同步更新，避免用户保存后还要重启
    for k, v in env_updates.items():
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)

    return SaveResult(
        env_path=env_path,
        config_path=config_path,
        updated_env_keys=[k for k, v in env_updates.items() if v],
        updated_config_sections=list(config_updates.keys()),
    )
