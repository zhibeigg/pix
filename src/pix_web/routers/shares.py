"""公开分享作品接口。"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from pix_web.config import WebSettings
from pix_web.models import (
    CreditTransaction,
    GenerationJob,
    GenerationOutput,
    SharedWork,
    SharedWorkLike,
    User,
    utcnow,
)
from pix_web.schemas import (
    JobOutputResponse,
    SharedDownloadOptionResponse,
    SharedWorkListResponse,
    SharedWorkResponse,
)
from pix_web.security import decode_file_ticket, get_current_user, get_db, get_settings
from pix_web.storage import resolve_web_file
from pix_web.system_settings import load_share_settings, resolve_site_timezone

router = APIRouter(prefix="/shares", tags=["shares"])

SHARE_STATUS_ACTIVE = "active"
SHARE_STATUS_HIDDEN = "hidden"
SHARE_STATUS_PENDING = "pending"
SHARE_STATUS_REJECTED = "rejected"
SHARE_STATUS_DELETED = "deleted"
SHARE_REWARD_TRANSACTION_TYPE = "share_reward"
# 作者可自行撤回（回到 hidden）的状态；active 只能管理员下架。
SHARE_STATUS_AUTHOR_WITHDRAWABLE = {SHARE_STATUS_PENDING, SHARE_STATUS_REJECTED}


def _file_ticket_user(
    request: Request,
    token: str | None,
    db: Session,
    settings: WebSettings,
) -> User:
    """预览/下载鉴权：优先短时效文件票据（query token），回退 Bearer 登录 token。

    <img> / 下载链接无法携带 Authorization 头，因此复用与 /files 一致的票据机制；
    票据只证明"已登录用户"，与公开池"任意登录用户可见"的级别一致。
    """
    bearer = request.headers.get("authorization", "")
    raw_token = token or (
        bearer.removeprefix("Bearer ").strip() if bearer.lower().startswith("bearer ") else ""
    )
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录"
        )
    user_id = decode_file_ticket(raw_token, settings)
    if user_id is None:
        try:
            payload = jwt.decode(
                raw_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            user_id = int(payload.get("sub", "0"))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录"
            ) from exc
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效，请重新登录"
        )
    return user


def _safe_file_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (value or "").strip())
    return cleaned.strip("._")[:80]


def _file_name(path: str, fallback: str) -> str:
    name = Path(path or fallback).name or fallback
    return _safe_file_part(name) or fallback


def _job_file_prefix(job: GenerationJob) -> str:
    params = job.params_json if isinstance(job.params_json, dict) else {}
    asset = params.get("asset") if isinstance(params, dict) else None
    asset_name = asset.get("name") if isinstance(asset, dict) else None
    prompt = (job.prompt or "").replace("\n", " ").strip()
    base = asset_name if isinstance(asset_name, str) and asset_name.strip() else prompt
    return _safe_file_part(base or f"pix-job-{job.id}") or f"pix-job-{job.id}"


def _asset_kind(job: GenerationJob) -> str:
    if job.job_type == "sprite_sheet":
        return "sprite_sheet"
    params = job.params_json if isinstance(job.params_json, dict) else {}
    asset = params.get("asset") if isinstance(params, dict) else None
    if isinstance(asset, dict) and isinstance(asset.get("asset_kind"), str):
        return str(asset["asset_kind"])
    return str(job.job_type or "")


def _job_title(job: GenerationJob) -> str:
    params = job.params_json if isinstance(job.params_json, dict) else {}
    asset = params.get("asset") if isinstance(params, dict) else None
    if isinstance(asset, dict) and isinstance(asset.get("name"), str) and asset["name"].strip():
        return asset["name"].strip()[:160]
    prompt = (job.prompt or "").replace("\n", " ").strip()
    return prompt[:160] if prompt else f"作品 #{job.id}"


def _as_record(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _normalized_filter_value(value: str) -> str:
    return " ".join(str(value or "").strip().split())[:128]


def _size_key(value: object) -> str:
    if isinstance(value, str):
        cleaned = value.strip().lower().replace("×", "x").replace(" ", "")
        parts = cleaned.split("x")
        if len(parts) == 2:
            try:
                width, height = int(parts[0]), int(parts[1])
            except ValueError:
                return ""
            if width > 0 and height > 0:
                return f"{width}x{height}"
        return ""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return ""
    try:
        width, height = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return ""
    if width <= 0 or height <= 0:
        return ""
    return f"{width}x{height}"


def _share_output_size_key(share: SharedWork) -> str:
    actual_size = _share_actual_size(share)
    if actual_size:
        return f"{actual_size[0]}x{actual_size[1]}"
    snapshot = _as_record(share.parameter_snapshot_json)
    pixel = _as_record(snapshot.get("pixel"))
    key = _size_key(pixel.get("output_size"))
    if key:
        return key
    job = getattr(share, "job", None)
    params = _as_record(getattr(job, "params_json", None))
    pixelize = _as_record(params.get("pixelize"))
    return _size_key(pixelize.get("output_size"))


def _share_image_model(share: SharedWork) -> str:
    snapshot = _as_record(share.parameter_snapshot_json)
    generation = _as_record(snapshot.get("generation"))
    raw_image = _as_record(snapshot.get("raw_image"))
    value = generation.get("model") or raw_image.get("model")
    if value:
        return str(value)
    job = getattr(share, "job", None)
    params = _as_record(getattr(job, "params_json", None))
    return str(params.get("image_model") or "")


def _share_asset_kind(share: SharedWork) -> str:
    """返回展示/筛选用的分享类型，兼容早期把序列帧误存为素材类型的记录。"""
    job = getattr(share, "job", None)
    if getattr(job, "job_type", None) == "sprite_sheet":
        return "sprite_sheet"
    snapshot = _as_record(share.parameter_snapshot_json)
    if str(snapshot.get("mode") or "") == "sprite_sheet" or _as_record(snapshot.get("sequence")):
        return "sprite_sheet"
    return str(share.asset_kind or "")


def _sort_size_value(value: str) -> tuple[int, int, str]:
    parts = value.split("x")
    try:
        width, height = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return (10**9, 10**9, value)
    return (width * height, width, value)


def _filter_options(shares: list[SharedWork]) -> dict[str, list[dict[str, object]]]:
    asset_kinds: dict[str, int] = {}
    output_sizes: dict[str, int] = {}
    image_models: dict[str, int] = {}
    for share in shares:
        asset_kind = _share_asset_kind(share)
        if asset_kind:
            asset_kinds[asset_kind] = asset_kinds.get(asset_kind, 0) + 1
        size = _share_output_size_key(share)
        if size:
            output_sizes[size] = output_sizes.get(size, 0) + 1
        model = _share_image_model(share)
        if model:
            image_models[model] = image_models.get(model, 0) + 1
    return {
        "asset_kinds": [{"value": key, "count": asset_kinds[key]} for key in sorted(asset_kinds)],
        "output_sizes": [
            {"value": key, "count": output_sizes[key]}
            for key in sorted(output_sizes, key=_sort_size_value)
        ],
        "image_models": [
            {"value": key, "count": image_models[key]} for key in sorted(image_models)
        ],
    }


def _share_matches_filters(
    share: SharedWork, *, asset_kind: str, output_size: str, image_model: str
) -> bool:
    if asset_kind and _share_asset_kind(share) != asset_kind:
        return False
    if output_size and _share_output_size_key(share) != output_size:
        return False
    if image_model and _share_image_model(share) != image_model:
        return False
    return True


def _strip_empty(value: object) -> object:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            cleaned = _strip_empty(item)
            if cleaned in (None, "", [], {}):
                continue
            result[key] = cleaned
        return result
    if isinstance(value, list):
        return [
            _strip_empty(item) for item in value if _strip_empty(item) not in (None, "", [], {})
        ]
    return value


def _parameter_snapshot(job: GenerationJob) -> dict[str, object]:
    params = _as_record(job.params_json)
    pixelize = _as_record(params.get("pixelize"))
    sprite = _as_record(params.get("sprite"))
    asset = _as_record(params.get("asset"))
    is_raw_image = job.job_type == "text_to_image" and params.get("source_only") is True
    return _strip_empty(
        {
            "mode": job.job_type,
            "prompt": (job.prompt or "").strip() or None,
            "input_image": "uploaded" if job.input_image_path else None,
            "generation": {
                "model": params.get("image_model"),
                "image_size": params.get("image_size"),
                "quality": params.get("image_quality"),
            },
            "raw_image": {
                "model": params.get("image_model"),
                "image_size": params.get("image_size"),
                "quality": params.get("image_quality"),
            }
            if is_raw_image
            else None,
            "pixel": {
                "output_size": pixelize.get("output_size"),
                "colors": pixelize.get("colors"),
                "remove_bg": None if job.job_type == "sprite_sheet" else pixelize.get("remove_bg"),
                "edge_style": None
                if job.job_type in {"sprite_sheet", "local_bg_remove"}
                else pixelize.get("edge_style"),
                "bg_removal_algorithm": None
                if job.job_type == "sprite_sheet"
                else pixelize.get("bg_removal_algorithm"),
            }
            if not is_raw_image
            else None,
            "asset": {
                "name": asset.get("name"),
                "extra_prompt": asset.get("extra_prompt"),
                "asset_kind": asset.get("asset_kind"),
                "subject_kind": asset.get("subject_kind"),
                "texture_kind": asset.get("texture_kind"),
                "material_a": asset.get("material_a"),
                "material_b": asset.get("material_b"),
                "material_a_texture_kind": asset.get("material_a_texture_kind"),
                "material_b_texture_kind": asset.get("material_b_texture_kind"),
                "transition_style": asset.get("transition_style"),
            }
            if job.job_type == "asset"
            else None,
            "sequence": {
                "frame_count": sprite.get("frame_count"),
                "fps": sprite.get("fps"),
                "rows": sprite.get("rows"),
                "cols": sprite.get("cols"),
                "row_prompts": sprite.get("row_prompts"),
            }
            if job.job_type == "sprite_sheet"
            else None,
        }
    )  # type: ignore[return-value]


def _manifest_entry(
    kind: str, label: str, path: str | None, fallback: str, *, description: str = ""
) -> dict[str, object] | None:
    if not path:
        return None
    return {
        "kind": kind,
        "label": label,
        "description": description,
        "path": path,
        "filename": _file_name(path, fallback),
    }


def _build_download_manifest(
    job: GenerationJob, output: GenerationOutput
) -> list[dict[str, object]]:
    data = JobOutputResponse.model_validate(output).model_dump(mode="python")
    entries: list[dict[str, object]] = []

    is_sprite = job.job_type == "sprite_sheet" or bool(
        data.get("sprite_frames")
        or data.get("sprite_sheet_path")
        or data.get("sprite_mosaic_path")
        or data.get("sequence_json_path")
    )
    is_dual_grid = bool(data.get("dual_grid_atlas_path") or data.get("dual_grid_preview_path"))

    if is_sprite:
        specs = [
            (
                "sprite_gif",
                "动画 GIF",
                data.get("sprite_gif_path"),
                "sprite.gif",
                "可播放的序列帧 GIF。",
            ),
            (
                "sprite_sheet",
                "横向精灵表",
                data.get("sprite_sheet_path") or data.get("pixelized_path"),
                "sprite-sheet.png",
                "横向排列的序列帧精灵图。",
            ),
            (
                "sprite_mosaic",
                "原版网格精灵表",
                data.get("sprite_mosaic_path") or data.get("source_path"),
                "sprite-mosaic.png",
                "保留原始 rows×cols 排版的单图序列帧。",
            ),
            (
                "sequence_json",
                "序列帧清单",
                data.get("sequence_json_path"),
                "sequence.json",
                "记录帧率、帧坐标和播放顺序的 JSON。",
            ),
        ]
    elif is_dual_grid:
        specs = [
            (
                "dual_grid_atlas",
                "双瓦片 4×4 图集",
                data.get("dual_grid_atlas_path") or data.get("pixelized_path"),
                "dual_grid_atlas.png",
                "包含 16 张过渡瓦片的最终 atlas。",
            ),
            (
                "dual_grid_preview",
                "双瓦片应用预览",
                data.get("dual_grid_preview_path") or data.get("preview_path"),
                "dual_grid_preview.png",
                "按确定性种子拼出的地图预览图。",
            ),
            ("source", "源图", data.get("source_path"), "01_source.png", "AI 原始输出或上传源图。"),
        ]
    else:
        specs = [
            ("source", "源图", data.get("source_path"), "01_source.png", "AI 原始输出或上传源图。"),
            (
                "pixelized",
                "像素尺寸图",
                data.get("pixelized_path"),
                "03_pixelized.png",
                "按当前像素尺寸生成的最终 PNG。",
            ),
            (
                "contact_sheet",
                "候选总览图",
                data.get("contact_sheet_path"),
                "contact-sheet.png",
                "候选生成结果总览图。",
            ),
        ]

    seen: set[str] = set()
    for kind, label, path, fallback, description in specs:
        entry = _manifest_entry(
            kind, label, str(path) if path else None, fallback, description=description
        )
        if entry is None:
            continue
        dedupe_key = str(entry["path"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        entries.append(entry)

    rows_outputs = data.get("sprite_rows_outputs")
    if isinstance(rows_outputs, list) and len(rows_outputs) > 1:
        prefix = _job_file_prefix(job)
        items = []
        for row in rows_outputs:
            if not isinstance(row, dict) or not row.get("sheet_path"):
                continue
            row_index = int(row.get("row_index") or len(items))
            phase = _safe_file_part(str(row.get("action_phase") or ""))
            number = row_index + 1
            filename = (
                f"{prefix}_action{number:02d}_{phase}.png"
                if phase
                else f"{prefix}_action{number:02d}.png"
            )
            items.append({"path": str(row["sheet_path"]), "filename": filename})
        if items:
            entries.append(
                {
                    "kind": "sprite_actions_zip",
                    "label": "所有动作打包",
                    "description": "把每个动作各一张横向图打包成 zip 下载。",
                    "filename": f"{prefix}_sprite_actions.zip",
                    "items": items,
                }
            )

    return entries


def _preview_path(output: GenerationOutput, manifest: list[dict[str, object]]) -> str:
    data = JobOutputResponse.model_validate(output).model_dump(mode="python")
    for value in (
        data.get("sprite_gif_path"),
        data.get("dual_grid_preview_path"),
        data.get("preview_path"),
        data.get("pixelized_path"),
        data.get("sprite_sheet_path"),
        data.get("source_path"),
    ):
        if value:
            return str(value)
    for entry in manifest:
        path = entry.get("path")
        if isinstance(path, str) and path:
            return path
    return output.pixelized_path or output.source_path


def _manifest_path_for_kind(share: SharedWork, kind: str) -> str | None:
    manifest = (
        share.download_manifest_json if isinstance(share.download_manifest_json, list) else []
    )
    for raw in manifest:
        if not isinstance(raw, dict) or raw.get("kind") != kind:
            continue
        path = raw.get("path")
        return str(path) if path else None
    return None


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _size_pair(value: object) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    width = _positive_int(value[0])
    height = _positive_int(value[1])
    return (width, height) if width and height else None


def _sheet_rect_size(frame: object) -> tuple[int, int] | None:
    if not isinstance(frame, dict):
        return None
    rect = frame.get("sheet_rect")
    if not isinstance(rect, dict):
        return None
    width = _positive_int(rect.get("w"))
    height = _positive_int(rect.get("h"))
    return (width, height) if width and height else None


def _share_actual_size(share: SharedWork) -> tuple[int, int] | None:
    job = getattr(share, "job", None)
    outputs = getattr(job, "outputs", None)
    output = outputs[0] if outputs else None
    if output is None:
        return None
    data = JobOutputResponse.model_validate(output).model_dump(mode="python")
    if _share_asset_kind(share) == "sprite_sheet":
        frames = data.get("sprite_frames")
        if isinstance(frames, list):
            for frame in frames:
                size = _sheet_rect_size(frame)
                if size:
                    return size
    return _size_pair(data.get("pixelized_size"))


def _share_sprite_preview(
    share: SharedWork, parameter_snapshot: dict[str, object]
) -> tuple[str | None, list[dict[str, object]], int | None]:
    if _share_asset_kind(share) != "sprite_sheet":
        return None, [], None
    sequence = _as_record(parameter_snapshot.get("sequence"))
    fps = _positive_int(sequence.get("fps"))
    job = getattr(share, "job", None)
    outputs = getattr(job, "outputs", None)
    output = outputs[0] if outputs else None
    if output is None:
        return None, [], fps
    data = JobOutputResponse.model_validate(output).model_dump(mode="python")
    frames = data.get("sprite_frames")
    sheet_path = data.get("sprite_sheet_path") or _manifest_path_for_kind(share, "sprite_sheet")
    if not isinstance(frames, list) or not sheet_path:
        return None, [], fps
    return f"/shares/{share.id}/sprite-sheet", frames, fps


def _share_download_options(share: SharedWork) -> list[SharedDownloadOptionResponse]:
    manifest = (
        share.download_manifest_json if isinstance(share.download_manifest_json, list) else []
    )
    options: list[SharedDownloadOptionResponse] = []
    for raw in manifest:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "")
        if not kind:
            continue
        options.append(
            SharedDownloadOptionResponse(
                kind=kind,
                label=str(raw.get("label") or kind),
                description=str(raw.get("description") or ""),
                url=f"/shares/{share.id}/download/{quote(kind, safe='')}",
                filename=str(raw.get("filename") or f"pix-share-{share.id}"),
            )
        )
    return options


def _share_parameter_snapshot(share: SharedWork) -> dict[str, object]:
    snapshot = dict(_as_record(share.parameter_snapshot_json))
    generation = dict(_as_record(snapshot.get("generation")))
    job = getattr(share, "job", None)
    params = _as_record(getattr(job, "params_json", None))
    if not generation.get("model") and params.get("image_model"):
        generation["model"] = params.get("image_model")
    if not generation.get("image_size") and params.get("image_size"):
        generation["image_size"] = params.get("image_size")
    if not generation.get("quality") and params.get("image_quality"):
        generation["quality"] = params.get("image_quality")
    cleaned = _strip_empty(generation)
    if isinstance(cleaned, dict) and cleaned:
        snapshot["generation"] = cleaned
    return snapshot


def _share_response(
    share: SharedWork,
    *,
    current_user: User | None = None,
    liked_ids: set[int] | None = None,
) -> SharedWorkResponse:
    parameter_snapshot = _share_parameter_snapshot(share)
    sprite_sheet_url, sprite_frames, sprite_fps = _share_sprite_preview(share, parameter_snapshot)
    return SharedWorkResponse(
        id=share.id,
        job_id=share.job_id,
        user_id=share.user_id,
        status=share.status,
        title=share.title,
        asset_kind=_share_asset_kind(share),
        preview_url=f"/shares/{share.id}/preview",
        actual_size=_share_actual_size(share),
        sprite_sheet_url=sprite_sheet_url,
        sprite_frames=sprite_frames,
        sprite_fps=sprite_fps,
        parameter_snapshot=parameter_snapshot,
        download_options=_share_download_options(share),
        like_count=share.like_count,
        download_count=share.download_count,
        reward_credits=share.reward_credits,
        liked_by_me=share.id in (liked_ids or set()),
        owned_by_me=bool(current_user and current_user.id == share.user_id),
        review_note=share.review_note or "",
        reviewed_at=share.reviewed_at,
        published_at=share.published_at,
        created_at=share.created_at,
        updated_at=share.updated_at,
    )


def _current_local_day_bounds(db: Session) -> tuple[datetime, datetime]:
    tz = resolve_site_timezone(db)
    now_local = datetime.now(tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _daily_reward_count(db: Session, user_id: int) -> int:
    start_utc, end_utc = _current_local_day_bounds(db)
    return int(
        db.scalar(
            select(func.count())
            .select_from(CreditTransaction)
            .where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.type == SHARE_REWARD_TRANSACTION_TYPE,
                CreditTransaction.amount > 0,
                CreditTransaction.created_at >= start_utc,
                CreditTransaction.created_at < end_utc,
            )
        )
        or 0
    )


def _reward_amount_for_publish(db: Session, user: User) -> int:
    settings = load_share_settings(db)
    if not settings.reward_enabled or settings.reward_credits <= 0:
        return 0
    if (
        settings.daily_reward_limit > 0
        and _daily_reward_count(db, user.id) >= settings.daily_reward_limit
    ):
        return 0
    return settings.reward_credits


@router.get("", response_model=SharedWorkListResponse)
def list_shares(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=48, ge=1, le=120),
    offset: int = Query(default=0, ge=0),
    asset_kind: str = Query(default=""),
    output_size: str = Query(default=""),
    image_model: str = Query(default=""),
) -> SharedWorkListResponse:
    # 需登录才能浏览社区公开池；只返回审核通过（active）的作品。
    normalized_asset_kind = _normalized_filter_value(asset_kind)
    normalized_output_size = _size_key(output_size)
    normalized_image_model = _normalized_filter_value(image_model)
    all_active_shares = list(
        db.scalars(
            select(SharedWork)
            .options(selectinload(SharedWork.job).selectinload(GenerationJob.outputs))
            .where(SharedWork.status == SHARE_STATUS_ACTIVE)
            .order_by(
                SharedWork.like_count.desc(), SharedWork.published_at.desc(), SharedWork.id.desc()
            )
        )
    )
    filters = _filter_options(all_active_shares)
    filtered_shares = [
        share
        for share in all_active_shares
        if _share_matches_filters(
            share,
            asset_kind=normalized_asset_kind,
            output_size=normalized_output_size,
            image_model=normalized_image_model,
        )
    ]
    total = len(filtered_shares)
    shares = filtered_shares[offset : offset + limit]
    liked_ids: set[int] = set()
    if current_user is not None and shares:
        liked_ids = set(
            db.scalars(
                select(SharedWorkLike.shared_work_id).where(
                    SharedWorkLike.user_id == current_user.id,
                    SharedWorkLike.shared_work_id.in_([share.id for share in shares]),
                )
            )
        )
    return SharedWorkListResponse(
        items=[
            _share_response(share, current_user=current_user, liked_ids=liked_ids)
            for share in shares
        ],
        total=total,
        limit=limit,
        offset=offset,
        filters=filters,
    )


@router.post("/jobs/{job_id}/publish", response_model=SharedWorkResponse)
def publish_job_share(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedWorkResponse:
    job = db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs), selectinload(GenerationJob.shared_work))
        .where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if job.status != "succeeded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="只有已完成作品可以公开分享"
        )
    output = job.outputs[0] if job.outputs else None
    if output is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="作品没有可分享的输出"
        )

    now = utcnow()
    manifest = _build_download_manifest(job, output)
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="作品没有可下载产物"
        )

    share = job.shared_work
    # 已在展示或已在审核队列中，直接返回当前状态，避免重复提交。
    if share is not None and share.status in {SHARE_STATUS_ACTIVE, SHARE_STATUS_PENDING}:
        return _share_response(share, current_user=user)
    if share is None:
        share = SharedWork(job_id=job.id, user_id=user.id, status=SHARE_STATUS_PENDING)
        db.add(share)
        db.flush()

    # 首次提交或从 hidden/rejected 重新提交：进入待审核队列，等待管理员审核。
    # 奖励改到审核通过时发放（见 admin approve），提交时不发。
    share.status = SHARE_STATUS_PENDING
    share.title = _job_title(job)
    share.asset_kind = _asset_kind(job)
    share.parameter_snapshot_json = _parameter_snapshot(job)
    share.download_manifest_json = manifest
    share.preview_path = _preview_path(output, manifest)
    share.review_note = ""
    share.reviewed_at = None
    share.reviewed_by_user_id = None
    share.published_at = None
    share.updated_at = now

    db.commit()
    db.refresh(share)
    return _share_response(share, current_user=user)


@router.post("/{share_id}/unpublish", response_model=SharedWorkResponse)
def unpublish_share(
    share_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedWorkResponse:
    share = db.get(SharedWork, share_id)
    if share is None or share.status == SHARE_STATUS_DELETED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    is_admin = user.role == "admin"
    is_owner = share.user_id == user.id
    if not is_owner and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权下架该分享作品")
    # 已通过审核（active）的作品只能管理员下架；作者只能撤回自己尚在审核 / 已驳回的提交。
    if not is_admin and share.status not in SHARE_STATUS_AUTHOR_WITHDRAWABLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="作品已通过审核并公开展示，如需下架请联系管理员",
        )
    share.status = SHARE_STATUS_HIDDEN
    share.updated_at = utcnow()
    db.commit()
    db.refresh(share)
    return _share_response(share, current_user=user)


@router.post("/{share_id}/like", response_model=SharedWorkResponse)
def like_share(
    share_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedWorkResponse:
    share = db.scalar(
        select(SharedWork)
        .options(selectinload(SharedWork.job).selectinload(GenerationJob.outputs))
        .where(SharedWork.id == share_id, SharedWork.status == SHARE_STATUS_ACTIVE)
    )
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    existing = db.scalar(
        select(SharedWorkLike).where(
            SharedWorkLike.shared_work_id == share.id, SharedWorkLike.user_id == user.id
        )
    )
    if existing is not None:
        return _share_response(share, current_user=user, liked_ids={share.id})
    db.add(SharedWorkLike(shared_work_id=share.id, user_id=user.id))
    share.like_count += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    refreshed = db.get(SharedWork, share.id) or share
    return _share_response(refreshed, current_user=user, liked_ids={share.id})


@router.delete("/{share_id}/like", response_model=SharedWorkResponse)
def unlike_share(
    share_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedWorkResponse:
    share = db.scalar(
        select(SharedWork)
        .options(selectinload(SharedWork.job).selectinload(GenerationJob.outputs))
        .where(SharedWork.id == share_id, SharedWork.status == SHARE_STATUS_ACTIVE)
    )
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    existing = db.scalar(
        select(SharedWorkLike).where(
            SharedWorkLike.shared_work_id == share.id, SharedWorkLike.user_id == user.id
        )
    )
    if existing is not None:
        db.delete(existing)
        share.like_count = max(0, share.like_count - 1)
        db.commit()
        db.refresh(share)
    return _share_response(share, current_user=user, liked_ids=set())


@router.get("/{share_id}/preview")
def shared_preview(
    share_id: int,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> FileResponse:
    _file_ticket_user(request, token, db, settings)  # 需登录（票据或 Bearer）
    share = db.scalar(
        select(SharedWork).where(
            SharedWork.id == share_id, SharedWork.status == SHARE_STATUS_ACTIVE
        )
    )
    if share is None or not share.preview_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    resolved = resolve_web_file(share.preview_path, settings)
    return FileResponse(resolved, filename=resolved.name, content_disposition_type="inline")


@router.get("/{share_id}/sprite-sheet")
def shared_sprite_sheet(
    share_id: int,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> FileResponse:
    _file_ticket_user(request, token, db, settings)  # 需登录（票据或 Bearer）
    share = db.scalar(
        select(SharedWork)
        .options(selectinload(SharedWork.job).selectinload(GenerationJob.outputs))
        .where(SharedWork.id == share_id, SharedWork.status == SHARE_STATUS_ACTIVE)
    )
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    path = _manifest_path_for_kind(share, "sprite_sheet")
    if not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="分享作品没有可播放序列帧"
        )
    resolved = resolve_web_file(path, settings)
    return FileResponse(resolved, filename=resolved.name, content_disposition_type="inline")


def _manifest_item(share: SharedWork, kind: str) -> dict[str, object]:
    manifest = (
        share.download_manifest_json if isinstance(share.download_manifest_json, list) else []
    )
    for item in manifest:
        if isinstance(item, dict) and item.get("kind") == kind:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品没有该下载项")


@router.get("/{share_id}/download/{kind}")
def download_shared_work(
    share_id: int,
    kind: str,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: WebSettings = Depends(get_settings),
) -> Response:
    _file_ticket_user(request, token, db, settings)  # 需登录（票据或 Bearer）
    share = db.scalar(
        select(SharedWork)
        .options(selectinload(SharedWork.job).selectinload(GenerationJob.outputs))
        .where(SharedWork.id == share_id, SharedWork.status == SHARE_STATUS_ACTIVE)
    )
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品不存在")
    item = _manifest_item(share, kind)
    filename = str(item.get("filename") or f"pix-share-{share.id}")

    if kind == "sprite_actions_zip":
        raw_items = item.get("items")
        if not isinstance(raw_items, list):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="分享作品没有可打包动作图"
            )
        buffer = BytesIO()
        added = 0
        with ZipFile(buffer, "w", ZIP_DEFLATED) as zip_file:
            for raw in raw_items:
                if not isinstance(raw, dict) or not raw.get("path"):
                    continue
                resolved = resolve_web_file(str(raw["path"]), settings)
                zip_file.write(resolved, str(raw.get("filename") or resolved.name))
                added += 1
        if added == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="分享作品没有可打包动作图"
            )
        share.download_count += 1
        db.commit()
        ascii_name = filename.encode("ascii", "ignore").decode().strip("_") or "shared_work.zip"
        disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": disposition},
        )

    path = item.get("path")
    if not isinstance(path, str) or not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分享作品没有该下载文件")
    resolved = resolve_web_file(path, settings)
    share.download_count += 1
    db.commit()
    return FileResponse(resolved, filename=filename, content_disposition_type="attachment")
