"""使用真实 Pix 流水线生成网站首页范例图。

流程：
1. 从 apps/web/src/homepageExamples.ts 读取 76 套题材 prompt；
2. 调用 pix.pipeline.run_pipeline：prompt guard → Packy 生图 → VL 分析 → pixelize；
3. 将最终 PNG 复制到 apps/web/public/homepage-examples；
4. 写入 provenance.json 记录每张图对应的 Pix 运行目录、源图、分析和 meta。

注意：这是真实 API 流水线，会消耗 Packy 生图/VL 点数。默认不跳过 VL。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageChops

from pix.config import load_config
from pix.contact_sheet import resolve_key_color
from pix.pipeline import PipelineInput, run_pipeline
from pix.pixelize.bg_removal import (
    key_color_edge_speckle_mask,
    key_color_edge_spill_mask,
    key_color_mask,
    remove_detached_dark_edges,
    remove_key_color,
    remove_tiny_alpha_islands,
)
from pix.pixelize.core import PixelizeParams

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TS = ROOT / "apps" / "web" / "src" / "homepageExamples.ts"
PUBLIC_DIR = ROOT / "apps" / "web" / "public" / "homepage-examples"
ITEM_DIR = PUBLIC_DIR / "items"
UI_DIR = PUBLIC_DIR / "ui"
PROVENANCE_PATH = PUBLIC_DIR / "provenance.json"
DEFAULT_RUN_ROOT = ROOT / "outputs" / "homepage-examples-full-flow"
PROVENANCE_LOCK = Lock()
ITEM_SHEET_SIZE = (512, 256)
ITEM_SHEET_COLS = 4
ITEM_SHEET_ROWS = 2
ITEM_SLOT_SIZE = 128
ITEM_MIN_SUBJECT_PIXELS = 32
UI_PIXEL_SIZE = (960, 540)
UI_EXPORT_SIZE = (1920, 1080)

Kind = Literal["item", "ui"]


@dataclass(frozen=True)
class HomepageExample:
    id: str
    number: str
    category: str
    theme: str
    item_src: str
    ui_src: str
    item_file: str
    ui_file: str
    item_prompt: str
    ui_prompt: str


def _extract_array(text: str) -> list[dict[str, Any]]:
    match = re.search(
        r"export const homepageExamples: HomepageExample\[\] = (\[[\s\S]*?\])\n\nexport const homepageExampleCategories",
        text,
    )
    if not match:
        raise RuntimeError(f"无法从 {MANIFEST_TS} 解析 homepageExamples 数组")
    data = json.loads(match.group(1))
    if not isinstance(data, list):
        raise RuntimeError("homepageExamples 不是数组")
    return data


def load_examples() -> list[HomepageExample]:
    raw_items = _extract_array(MANIFEST_TS.read_text(encoding="utf-8"))
    examples: list[HomepageExample] = []
    for item in raw_items:
        examples.append(
            HomepageExample(
                id=str(item["id"]),
                number=str(item["number"]),
                category=str(item["category"]),
                theme=str(item["theme"]),
                item_src=str(item["itemSrc"]),
                ui_src=str(item["uiSrc"]),
                item_file=str(item["itemFile"]),
                ui_file=str(item["uiFile"]),
                item_prompt=str(item["itemPrompt"]),
                ui_prompt=str(item["uiPrompt"]),
            )
        )
    if len(examples) != 76:
        raise RuntimeError(f"期望 76 条范例，实际解析到 {len(examples)} 条")
    return examples


def configure_pix(config_path: Path | None, *, remote_guard: bool, contact_sheet: bool, api_timeout: float, api_retries: int):
    cfg = load_config(config_file=config_path)
    # 首页范例需要生成“一张物品精灵表 / 一张 UI 展示图”，不是 Pix 默认 3x3 候选图。
    # 仍然走同一个 run_pipeline，只关闭 contact sheet 包装，避免输出结构被九宫格候选改写。
    cfg.image_gen.contact_sheet_enabled = contact_sheet
    cfg.image_gen.prompt_guard_max_chars = 2400
    cfg.image_gen.prompt_guard_remote = remote_guard
    cfg.api.timeout = max(float(cfg.api.timeout), float(api_timeout))
    cfg.api.max_retries = max(int(cfg.api.max_retries), int(api_retries))
    return cfg


def item_params() -> PixelizeParams:
    return PixelizeParams(
        output_size=ITEM_SHEET_SIZE,  # 4×2 sprite sheet；每格 128×128，单个物品保留 32/64px 级可读空间
        colors=64,
        dither="none",
        preset="auto",
        preview_scale=0,
        edge_enhance=0.08,
        saturation=1.08,
        resample="smart",
        snap_to_grid=True,
        remove_bg=True,
        bg_tolerance=34,
        bg_feather=1,
        edge_style="outline",
        auto_crop=False,
        crop_square=False,
    )


def ui_params() -> PixelizeParams:
    return PixelizeParams(
        output_size=UI_PIXEL_SIZE,
        colors=64,
        dither="none",
        preset="auto",
        preview_scale=0,
        edge_enhance=0.08,
        saturation=1.05,
        resample="smart",
        snap_to_grid=True,
        remove_bg=False,
        auto_crop=False,
        crop_square=False,
    )


def target_for(example: HomepageExample, kind: Kind) -> Path:
    return (ITEM_DIR / example.item_file) if kind == "item" else (UI_DIR / example.ui_file)


def prompt_for(example: HomepageExample, kind: Kind, *, key_hex: str | None = None) -> str:
    if kind == "item":
        background = key_hex or "a pure solid key color"
        return (
            f"{example.item_prompt}. IMPORTANT for clarity: create exactly 8 LARGE item icons in a strict 4 columns by 2 rows sprite sheet. "
            "Each square slot must contain ONE centered item only. Each item must fill 75-90% of its slot and remain readable when the slot is exported as a 64x64 game icon. "
            "Do not make a dense catalog. Do not add tiny miniatures, duplicate sub-icons, labels, UI frames, text, shadows outside items, or decorative clutter. "
            "Use simple readable silhouettes, thick dark outlines, high contrast, and clear spacing between slots. "
            f"Use a pure solid chroma-key background {background} outside the items for reliable background removal; do not use that color inside any item."
        )
    return (
        f"{example.ui_prompt}. IMPORTANT for clarity: compose a large 16:9 UI showcase for a website homepage. "
        "Use large readable panels, HUD bars, buttons, inventory or menu modules, strong pixel borders, clear spacing, and iconic symbols. "
        "No tiny unreadable text, no dense noisy micro details, no thumbnail collage. It should still look good after pixelization at about 960x540 and export to 1920x1080."
    )


def clean_item_sheet_background(image: Image.Image, *, key_rgb: tuple[int, int, int]) -> Image.Image:
    """只清理动态 key color，避免猜测性抠掉物品内容。

    重要：这里不能再对任意四角/浅灰背景做 flood-fill 强抠。若模型没有遵守
    key color 背景，后续验收会失败并重试；不能为了救图误扣主体内容。
    """
    cleaned = image
    # 两轮保守清理：第一轮抠掉 key color 和直接暴露的边缘碎点；第二轮只处理第一轮后
    # 才贴近透明背景的次级碎点。不扩大容差，避免误扣主体内容。
    for _ in range(2):
        cleaned = remove_key_color(
            cleaned,
            key_rgb=key_rgb,
            tolerance=8,
            spill_tolerance=20,
            edge_speckle=True,
            edge_speckle_max_area=18,
            edge_speckle_max_thickness=3,
            edge_speckle_radius=2,
            edge_speckle_passes=2,
            edge_spill=True,
            edge_spill_radius=3,
            edge_spill_passes=4,
            edge_spill_outline=True,
        )
    cleaned = remove_detached_dark_edges(cleaned)
    return remove_tiny_alpha_islands(cleaned)


def validate_item_sheet(image: Image.Image, *, key_rgb: tuple[int, int, int]) -> None:
    rgba = image.convert("RGBA")
    if rgba.size != ITEM_SHEET_SIZE:
        raise ValueError(f"物品图尺寸应为 {ITEM_SHEET_SIZE[0]}x{ITEM_SHEET_SIZE[1]}，实际为 {rgba.size[0]}x{rgba.size[1]}")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] >= 255:
        raise ValueError("物品图没有透明背景")
    corner_points = [(0, 0), (rgba.width - 1, 0), (0, rgba.height - 1), (rgba.width - 1, rgba.height - 1)]
    opaque_corners = [point for point in corner_points if rgba.getpixel(point)[3] > 16]
    if opaque_corners:
        raise ValueError(f"物品图外部背景未透明，非透明角点：{opaque_corners}")
    rgba_arr = np.asarray(rgba)
    residue = int(key_color_mask(rgba_arr, key_rgb, tolerance=8, visible_only=True).sum())
    if residue:
        raise ValueError(f"物品图仍有可见 key color 背景残留像素：{residue}")
    hidden_residue = int(key_color_mask(rgba_arr, key_rgb, tolerance=2, visible_only=False).sum())
    if hidden_residue:
        raise ValueError(f"透明像素 RGB 中仍残留 key color：{hidden_residue}")
    edge_residue = int(key_color_edge_speckle_mask(rgba_arr, key_rgb, max_area=18, max_thickness=3, radius=2).sum())
    if edge_residue:
        raise ValueError(f"物品图仍有 key color 边缘碎点/细条：{edge_residue}")
    edge_spill = int(key_color_edge_spill_mask(rgba_arr, key_rgb, radius=3).sum())
    if edge_spill:
        raise ValueError(f"物品图仍有 key color 边缘量化溢色：{edge_spill}")
    problems: list[str] = []
    for row in range(ITEM_SHEET_ROWS):
        for col in range(ITEM_SHEET_COLS):
            left = col * ITEM_SLOT_SIZE
            top = row * ITEM_SLOT_SIZE
            slot = alpha.crop((left, top, left + ITEM_SLOT_SIZE, top + ITEM_SLOT_SIZE))
            slot_arr = np.asarray(slot)
            edge = np.concatenate([slot_arr[0, :], slot_arr[-1, :], slot_arr[:, 0], slot_arr[:, -1]])
            label = f"r{row + 1}c{col + 1}"
            if float((edge > 16).mean()) > 0.10:
                problems.append(f"{label}=edge-background-not-transparent")
            bbox = slot.point(lambda value: 255 if value > 16 else 0).getbbox()
            if bbox is None:
                problems.append(f"{label}=empty")
                continue
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width < ITEM_MIN_SUBJECT_PIXELS or height < ITEM_MIN_SUBJECT_PIXELS:
                problems.append(f"{label}={width}x{height}")
    if problems:
        raise ValueError("物品格主体小于 32x32 或为空：" + ", ".join(problems))


def validate_ui_showcase(image: Image.Image) -> None:
    if image.size != UI_EXPORT_SIZE:
        raise ValueError(f"UI 图尺寸应为 {UI_EXPORT_SIZE[0]}x{UI_EXPORT_SIZE[1]}，实际为 {image.size[0]}x{image.size[1]}")
    # 过于接近空白/纯色的 UI 图没有展示价值。
    probe = image.convert("RGB").resize((160, 90), Image.Resampling.BOX)
    diff = ImageChops.difference(probe, Image.new("RGB", probe.size, probe.getpixel((0, 0))))
    if diff.getbbox() is None:
        raise ValueError("UI 图几乎是纯色，缺少可展示内容")


def render_final(kind: Kind, pixel_path: Path, target: Path, *, key_rgb: tuple[int, int, int] | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(pixel_path) as opened:
        image = opened.convert("RGBA") if kind == "item" else opened.convert("RGB")
        if kind == "ui":
            image = image.resize(UI_EXPORT_SIZE, Image.Resampling.NEAREST)
            validate_ui_showcase(image)
        else:
            if key_rgb is None:
                raise ValueError("物品图导出必须提供 key_rgb")
            image = clean_item_sheet_background(image, key_rgb=key_rgb)
            validate_item_sheet(image, key_rgb=key_rgb)
            # 覆盖 run 目录里的 03_pixelized.png，确保用户查看 Pix 全流程产物时也是清理后的结果。
            image.save(pixel_path)
        image.save(target)


def load_provenance() -> dict[str, Any]:
    if not PROVENANCE_PATH.exists():
        return {"generator": "scripts/generate_homepage_examples.py", "mode": "pix-full-flow", "entries": []}
    try:
        data = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except Exception:
        pass
    return {"generator": "scripts/generate_homepage_examples.py", "mode": "pix-full-flow", "entries": []}


def upsert_provenance(record: dict[str, Any]) -> None:
    with PROVENANCE_LOCK:
        data = load_provenance()
        entries = [
            item for item in data.get("entries", [])
            if not (item.get("id") == record.get("id") and item.get("kind") == record.get("kind"))
        ]
        entries.append(record)
        entries.sort(key=lambda item: (str(item.get("number", "")), str(item.get("kind", ""))))
        data.update(
            {
                "generator": "scripts/generate_homepage_examples.py",
                "mode": "pix-full-flow",
                "updated_at_epoch": int(time.time()),
                "entries": entries,
            }
        )
        PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROVENANCE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_one(
    example: HomepageExample,
    kind: Kind,
    *,
    cfg,
    run_root: Path,
    refresh: bool,
    skip_vl: bool,
    quality: str,
) -> None:
    key_hex: str | None = None
    key_rgb: tuple[int, int, int] | None = None
    if kind == "item":
        key_hex, key_rgb = resolve_key_color("auto", example.item_prompt)
    prompt = prompt_for(example, kind, key_hex=key_hex)
    target = target_for(example, kind)
    params = item_params() if kind == "item" else ui_params()
    image_size = "2048x1024" if kind == "item" else "2048x1152"

    print(f"[{example.number} {kind}] Pix 全流程开始：{example.theme} → {target.relative_to(ROOT)}")
    result = run_pipeline(
        cfg,
        PipelineInput(
            prompt=prompt,
            image_size=image_size,
            image_quality=quality,
            skip_vl=skip_vl,
            pixelize_params=params,
            out_root=run_root,
            use_cache=True,
            refresh_cache=refresh,
        ),
        progress=lambda step, payload: print(f"  - {step}: {payload}"),
    )
    render_final(kind, result.pixel_path, target, key_rgb=key_rgb)
    upsert_provenance(
        {
            "id": example.id,
            "number": example.number,
            "category": example.category,
            "theme": example.theme,
            "kind": kind,
            "target": str(target.relative_to(ROOT)),
            "prompt": prompt,
            "image_size": image_size,
            "image_quality": quality,
            "skip_vl": skip_vl,
            "background_key_color": key_hex,
            "pixel_output_size": list(ITEM_SHEET_SIZE if kind == "item" else UI_PIXEL_SIZE),
            "export_size": list(ITEM_SHEET_SIZE if kind == "item" else UI_EXPORT_SIZE),
            "slot_size": ITEM_SLOT_SIZE if kind == "item" else None,
            "min_subject_pixels": ITEM_MIN_SUBJECT_PIXELS if kind == "item" else None,
            "run_dir": str(result.run_dir.relative_to(ROOT) if result.run_dir.is_relative_to(ROOT) else result.run_dir),
            "source": str(result.source_path.relative_to(ROOT) if result.source_path.is_relative_to(ROOT) else result.source_path),
            "analysis": str(result.analysis_path.relative_to(ROOT) if result.analysis_path and result.analysis_path.is_relative_to(ROOT) else result.analysis_path),
            "pixel": str(result.pixel_path.relative_to(ROOT) if result.pixel_path.is_relative_to(ROOT) else result.pixel_path),
            "meta": str(result.meta_path.relative_to(ROOT) if result.meta_path.is_relative_to(ROOT) else result.meta_path),
        }
    )
    print(f"[{example.number} {kind}] 完成：{target.relative_to(ROOT)}")


def selected_work(examples: list[HomepageExample], *, only: set[str], kind: str, limit: int | None) -> list[tuple[HomepageExample, Kind]]:
    pairs: list[tuple[HomepageExample, Kind]] = []
    wanted_kinds: tuple[Kind, ...]
    if kind == "both":
        wanted_kinds = ("item", "ui")
    elif kind in {"item", "ui"}:
        wanted_kinds = (kind,)  # type: ignore[assignment]
    else:
        raise ValueError("kind 必须是 item、ui 或 both")
    for example in examples:
        if only and example.number not in only and example.id not in only and example.theme not in only:
            continue
        for current_kind in wanted_kinds:
            pairs.append((example, current_kind))
    if limit is not None:
        return pairs[: max(0, limit)]
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="真实调用 Pix 全流程生成首页范例图")
    parser.add_argument("--config", type=Path, default=None, help="可选 Pix TOML 配置")
    parser.add_argument("--kind", choices=("item", "ui", "both"), default="both")
    parser.add_argument("--only", action="append", default=[], help="只生成指定编号/id/主题；可重复传入")
    parser.add_argument("--limit", type=int, default=None, help="最多生成多少个目标，用于冒烟测试")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--refresh", action="store_true", help="忽略 Pix 缓存，强制重新调用 API")
    parser.add_argument("--skip-vl", action="store_true", help="跳过 VL 分析；默认不跳过，保持 Pix 全流程")
    parser.add_argument("--quality", default="medium", choices=("low", "medium", "high", "auto"))
    parser.add_argument("--remote-guard", action="store_true", help="启用远程 prompt guard；默认只做本地 prompt guard")
    parser.add_argument("--contact-sheet", action="store_true", help="保留默认 3x3 contact sheet 包装；首页范例默认关闭")
    parser.add_argument("--workers", type=int, default=1, help="并发生成数量；真实 API 调用建议 1-4")
    parser.add_argument("--attempts", type=int, default=2, help="单个目标失败后的最多尝试次数；重试会强制刷新 Pix 缓存")
    parser.add_argument("--api-timeout", type=float, default=600.0, help="Packy API 单次请求超时秒数")
    parser.add_argument("--api-retries", type=int, default=3, help="Packy API 最大重试次数")
    parser.add_argument("--reset-output", action="store_true", help="生成前清空 public 范例图片和 provenance，避免混入旧假图")
    args = parser.parse_args()

    examples = load_examples()
    work = selected_work(examples, only=set(args.only), kind=args.kind, limit=args.limit)
    if not work:
        raise SystemExit("没有匹配的范例任务")

    cfg = configure_pix(
        args.config,
        remote_guard=args.remote_guard,
        contact_sheet=args.contact_sheet,
        api_timeout=args.api_timeout,
        api_retries=args.api_retries,
    )
    args.run_root.mkdir(parents=True, exist_ok=True)
    if args.reset_output:
        for directory in (ITEM_DIR, UI_DIR):
            if directory.exists():
                for old_file in directory.glob("*.png"):
                    old_file.unlink()
        if PROVENANCE_PATH.exists():
            PROVENANCE_PATH.unlink()
    ITEM_DIR.mkdir(parents=True, exist_ok=True)
    UI_DIR.mkdir(parents=True, exist_ok=True)

    def _run_pair(pair: tuple[HomepageExample, Kind]) -> tuple[str, Kind, str | None]:
        example, kind = pair
        last_error = ""
        attempts = max(1, int(args.attempts))
        for attempt in range(1, attempts + 1):
            try:
                generate_one(
                    example,
                    kind,
                    cfg=cfg,
                    run_root=args.run_root,
                    refresh=bool(args.refresh or attempt > 1),
                    skip_vl=args.skip_vl,
                    quality=args.quality,
                )
                return example.number, kind, None
            except Exception as exc:  # noqa: BLE001 - 生成批处理需要继续收集失败项
                last_error = str(exc)
                print(f"[{example.number} {kind}] 第 {attempt}/{attempts} 次失败：{exc}", file=sys.stderr)
        return example.number, kind, last_error

    failures: list[tuple[str, str, str]] = []
    workers = max(1, int(args.workers))
    if workers == 1:
        for pair in work:
            number, kind, error = _run_pair(pair)
            if error:
                failures.append((number, kind, error))
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_run_pair, pair) for pair in work]
            done = 0
            for future in as_completed(futures):
                done += 1
                number, kind, error = future.result()
                print(f"进度：{done}/{len(futures)}（刚结束 {number} {kind}）")
                if error:
                    failures.append((number, kind, error))

    if failures:
        print("失败任务：", file=sys.stderr)
        for number, kind, error in failures:
            print(f"  - {number} {kind}: {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"全部完成：{len(work)} 个目标，provenance={PROVENANCE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
