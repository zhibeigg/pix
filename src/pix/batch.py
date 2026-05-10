"""批量像素化：给一个目录的图片批量跑像素化流水线。

设计目标：
- 输入一个目录里的 PNG/JPG/WebP 等，输出到另一个目录，文件名对应。
- 支持并发（线程池）—— 像素化本身以 CPU 为主但 Pillow/NumPy 释放 GIL；
  如果启用了 VL 分析，多线程能让 HTTP 等待重叠。
- 失败不阻塞其它任务；最终汇总成功/失败数。
- 可选：每张图生成独立的 analysis.json 和 meta.json（开关控制）。
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image

from pix.analysis.schema import PixAnalysis
from pix.api.vision import VisionParseError, analyze_image
from pix.config import AppConfig
from pix.pixelize.core import PixelizeParams, pixelize


# 常见的位图扩展名
DEFAULT_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")


@dataclass
class BatchItem:
    src: Path
    dest: Path
    status: str = "pending"      # pending | ok | skipped | failed
    error: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class BatchResult:
    items: list[BatchItem]

    @property
    def ok(self) -> list[BatchItem]:
        return [x for x in self.items if x.status == "ok"]

    @property
    def skipped(self) -> list[BatchItem]:
        return [x for x in self.items if x.status == "skipped"]

    @property
    def failed(self) -> list[BatchItem]:
        return [x for x in self.items if x.status == "failed"]

    def summary(self) -> str:
        return (
            f"total={len(self.items)} "
            f"ok={len(self.ok)} skipped={len(self.skipped)} failed={len(self.failed)}"
        )


def iter_inputs(input_dir: Path, patterns: Iterable[str] = DEFAULT_EXTS) -> list[Path]:
    """递归列出所有位图文件，按路径排序保证稳定顺序。"""
    input_dir = Path(input_dir)
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in patterns:
        for p in input_dir.rglob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    # 不区分大小写的扩展名（.PNG 等）
    for pat in patterns:
        upper = pat.upper()
        if upper == pat:
            continue
        for p in input_dir.rglob(upper):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    out.sort()
    return out


def _process_one(
    src: Path,
    dest: Path,
    cfg: AppConfig,
    params: PixelizeParams,
    *,
    do_vl: bool,
    vl_model: str | None,
    write_sidecars: bool,
    overwrite: bool,
) -> BatchItem:
    item = BatchItem(src=src, dest=dest)
    try:
        if dest.exists() and not overwrite:
            item.status = "skipped"
            return item

        analysis: PixAnalysis | None = None
        if do_vl:
            try:
                analysis = analyze_image(cfg, src, model=vl_model)
            except (VisionParseError, Exception) as exc:  # noqa: BLE001
                # VL 失败不拖累像素化；把错误作为 meta 记录
                item.meta["vl_error"] = str(exc)

        img = Image.open(src)
        pixel_img, preview_img, pix_meta = pixelize(img, params, analysis=analysis)

        dest.parent.mkdir(parents=True, exist_ok=True)
        pixel_img.save(dest)

        if write_sidecars:
            if analysis is not None:
                sidecar = dest.with_suffix(".analysis.json")
                sidecar.write_text(
                    analysis.model_dump_json(indent=2), encoding="utf-8"
                )
            meta_sidecar = dest.with_suffix(".meta.json")
            meta_sidecar.write_text(
                json.dumps(
                    {
                        "source": str(src),
                        "pixelize": pix_meta,
                        "used_vl": analysis is not None,
                        **item.meta,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        item.meta.update(pix_meta)
        item.status = "ok"
        return item
    except Exception as exc:  # noqa: BLE001
        item.status = "failed"
        item.error = str(exc)
        return item


def run_batch(
    cfg: AppConfig,
    input_dir: Path | str,
    output_dir: Path | str,
    *,
    pixelize_params: PixelizeParams | None = None,
    use_vl: bool = False,
    vl_model: str | None = None,
    workers: int = 4,
    write_sidecars: bool = True,
    overwrite: bool = False,
    patterns: Iterable[str] = DEFAULT_EXTS,
    output_suffix: str = ".png",
    on_item_done: Callable[[BatchItem, int, int], None] | None = None,
) -> BatchResult:
    """对 input_dir 下所有匹配 patterns 的图片做像素化，写到 output_dir。

    Args:
        pixelize_params: 像素化参数；None 时用默认 PixelizeParams。
        use_vl: 是否启用 VL 分析（每张图都会调一次 VL，开销较大）。
        workers: 并发线程数。仅影响 I/O 与 VL 等待重叠，不绕过 GIL。
        write_sidecars: 为每张输出图生成 .analysis.json / .meta.json。
        overwrite: 已存在时是否覆盖；False 时跳过。
        output_suffix: 输出文件扩展名，默认 .png。
        on_item_done: 回调 (item, done_count, total) —— 用于 CLI/GUI 进度展示。
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"input dir not found: {input_path}")
    output_path.mkdir(parents=True, exist_ok=True)

    params = pixelize_params or PixelizeParams()

    srcs = iter_inputs(input_path, patterns)
    total = len(srcs)
    if total == 0:
        return BatchResult(items=[])

    tasks: list[BatchItem] = []
    for src in srcs:
        rel = src.relative_to(input_path)
        dest = output_path / rel.with_suffix(output_suffix)
        tasks.append(BatchItem(src=src, dest=dest))

    results: list[BatchItem] = [None] * total  # type: ignore[list-item]
    workers = max(1, int(workers))

    start = time.time()
    if workers == 1:
        for i, task in enumerate(tasks):
            item = _process_one(
                task.src, task.dest, cfg, params,
                do_vl=use_vl, vl_model=vl_model,
                write_sidecars=write_sidecars, overwrite=overwrite,
            )
            results[i] = item
            if on_item_done:
                on_item_done(item, i + 1, total)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(
                    _process_one, task.src, task.dest, cfg, params,
                    do_vl=use_vl, vl_model=vl_model,
                    write_sidecars=write_sidecars, overwrite=overwrite,
                ): i
                for i, task in enumerate(tasks)
            }
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    item = fut.result()
                except Exception as exc:  # noqa: BLE001
                    task = tasks[i]
                    item = BatchItem(src=task.src, dest=task.dest, status="failed", error=str(exc))
                results[i] = item
                done += 1
                if on_item_done:
                    on_item_done(item, done, total)

    result = BatchResult(items=[r for r in results if r is not None])
    # 附带总耗时
    if result.items:
        result.items[0].meta.setdefault("batch_duration_seconds", round(time.time() - start, 3))
    return result
