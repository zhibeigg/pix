"""历史记录扫描与查询。

历史记录直接来自输出目录中的 `meta.json`，不维护额外数据库。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HistoryRecord:
    run_dir: Path
    created_at: datetime
    prompt: str | None
    image_path: str | None
    source_path: Path | None
    analysis_path: Path | None
    pixel_path: Path | None
    preview_path: Path | None
    meta_path: Path
    image_model: str | None
    vision_model: str | None
    pixel_size: tuple[int, int] | None
    colors: int | None
    dither: str | None
    preset: str | None
    remove_bg: bool | None
    bg_tolerance: int | None
    bg_feather: int | None
    edge_style: str | None
    duration_seconds: float | None
    ok: bool
    version: str | None

    @property
    def prompt_summary(self) -> str:
        value = (self.prompt or self.image_path or "").strip()
        if len(value) <= 96:
            return value
        return value[:93] + "..."

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("run_dir", "source_path", "analysis_path", "pixel_path", "preview_path", "meta_path"):
            value = data.get(key)
            data[key] = str(value) if value is not None else None
        data["created_at"] = self.created_at.isoformat()
        data["pixel_size"] = list(self.pixel_size) if self.pixel_size else None
        return data


def scan_history(root: str | Path, query: str = "", limit: int = 100) -> list[HistoryRecord]:
    """扫描输出目录并按时间倒序返回历史记录。"""
    root_path = Path(root)
    if not root_path.exists():
        return []
    records: list[HistoryRecord] = []
    run_dirs = [p for p in root_path.iterdir() if p.is_dir() and (p / "meta.json").exists()]
    run_dirs.sort(key=lambda p: (p / "meta.json").stat().st_mtime, reverse=True)
    for run_dir in run_dirs:
        try:
            record = load_history_record(run_dir)
        except Exception:
            continue
        if _matches(record, query):
            records.append(record)
            if limit > 0 and len(records) >= limit:
                break
    return records


def load_history_record(run_dir: str | Path) -> HistoryRecord:
    """从单个运行目录读取历史记录。"""
    run_path = Path(run_dir)
    meta_path = run_path / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stat = meta_path.stat()
    created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone()

    outputs = meta.get("outputs") or {}
    pixelize = meta.get("pixelize") or {}
    eff = pixelize.get("effective_params") or {}
    image_gen = meta.get("image_gen") or {}
    vision = meta.get("vision") or {}
    inputs = meta.get("input") or {}

    pixel_size = _parse_pixel_size(eff.get("output_size"))
    source_path = _resolve_output(run_path, outputs.get("source"))
    analysis_path = _resolve_output(run_path, outputs.get("analysis"))
    pixel_path = _resolve_output(run_path, outputs.get("pixelized"))
    preview_path = _resolve_output(run_path, outputs.get("preview"))

    ok = bool(pixel_path and pixel_path.exists())
    return HistoryRecord(
        run_dir=run_path,
        created_at=created_at,
        prompt=_str_or_none(inputs.get("prompt")),
        image_path=_str_or_none(inputs.get("image_path")),
        source_path=source_path,
        analysis_path=analysis_path,
        pixel_path=pixel_path,
        preview_path=preview_path,
        meta_path=meta_path,
        image_model=_str_or_none(image_gen.get("model")),
        vision_model=_str_or_none(vision.get("model")),
        pixel_size=pixel_size,
        colors=_int_or_none(eff.get("colors")),
        dither=_str_or_none(eff.get("dither")),
        preset=_str_or_none(eff.get("preset")),
        remove_bg=_bool_or_none(eff.get("remove_bg")),
        bg_tolerance=_int_or_none(eff.get("bg_tolerance")),
        bg_feather=_int_or_none(eff.get("bg_feather")),
        edge_style=_str_or_none(eff.get("edge_style")) or "hard",
        duration_seconds=_float_or_none(meta.get("duration_seconds")),
        ok=ok,
        version=_str_or_none(meta.get("version")),
    )


def _resolve_output(run_dir: Path, value: Any) -> Path | None:
    if not value:
        return None
    p = Path(str(value))
    if not p.is_absolute():
        p = run_dir / p
    return p


def _matches(record: HistoryRecord, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    haystack = "\n".join(
        str(v or "")
        for v in (
            record.run_dir.name,
            record.prompt,
            record.image_path,
            record.image_model,
            record.vision_model,
            record.dither,
            record.preset,
            record.version,
        )
    ).lower()
    return q in haystack


def _parse_pixel_size(value: Any) -> tuple[int, int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None
    return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)
