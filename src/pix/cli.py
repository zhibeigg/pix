"""Typer CLI。"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pix import __version__
from pix.analysis.schema import PixAnalysis
from pix.api.image_gen import generate_image
from pix.api.vision import analyze_image
from pix.asset import build_asset_prompt, safe_asset_filename, validate_asset_image
from pix.config import AppConfig, load_config
from pix.grid.extract import extract_pixel_grid
from pix.grid.postprocess import polish_pixel_grid
from pix.grid.render import render_grid_file, render_pixel_grid
from pix.grid.review import review_grid_file, review_pixel_grid
from pix.grid.schema import load_grid, save_grid
from pix.pipeline import PipelineInput, run_pipeline
from pix.pixelize.core import PixelizeParams, pixelize as run_pixelize
from pix.pixelize.presets import list_presets


def _make_console() -> Console:
    """Windows cp936 终端下 rich 用 Unicode 会炸，这里强制 utf-8。"""
    try:
        # 强制 sys.stdout 使用 utf-8，避免 cp936 编码 '✓' '→' 这类字符失败
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return Console()


app = typer.Typer(add_completion=False, help="pix — prompt → AI 图 → JSON → 像素图")
console = _make_console()


def _parse_size(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception as exc:
        raise typer.BadParameter(f"尺寸必须形如 128x128，收到 {s}") from exc


def _base_config(
    config_file: Optional[Path],
    overrides: dict | None = None,
) -> AppConfig:
    cfg = load_config(config_file=config_file, overrides=overrides)
    return cfg


def _progress_printer(step: str, payload: dict) -> None:
    console.log(f"[cyan]{step}[/cyan] {payload}")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="打印版本并退出"),
) -> None:
    if version:
        console.print(f"pix {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


# ---------- gen-only ----------


@app.command("gen-only")
def cmd_gen_only(
    prompt: str = typer.Argument(..., help="文生图提示词"),
    out: Path = typer.Option(Path("outputs/gen-only"), help="输出目录"),
    size: str = typer.Option("1024x1024", help="生图尺寸，如 1024x1024"),
    quality: str = typer.Option("high", help="low|medium|high|auto"),
    model: str = typer.Option("gpt-image-2", help="生图模型"),
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """只做文生图，把结果保存到输出目录。"""
    cfg = _base_config(config)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "01_source.png"
    console.log(f"开始生图：{prompt!r} → {dest}")
    generate_image(cfg, prompt, dest, size=size, quality=quality, model=model)
    console.print(Panel.fit(f"[green][OK][/green] 图片已保存：{dest}", title="gen-only"))


# ---------- analyze ----------


@app.command("analyze")
def cmd_analyze(
    image: Path = typer.Argument(..., exists=True, readable=True, help="输入图片"),
    out: Optional[Path] = typer.Option(None, help="输出 JSON 路径，默认与图片同目录"),
    model: Optional[str] = typer.Option(None, help="VL 模型，如 claude-sonnet-4-5 / gemini-2.5-pro"),
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """让多模态模型输出结构化 JSON。"""
    cfg = _base_config(config)
    target = out or image.with_name("02_analysis.json")
    console.log(f"分析中：{image} (model={model or cfg.vision.model})")
    result = analyze_image(cfg, image, model=model)
    target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    console.print(Panel.fit(f"[green][OK][/green] JSON 已保存：{target}", title="analyze"))


# ---------- pixelize ----------


@app.command("pixelize")
def cmd_pixelize(
    image: Path = typer.Argument(..., exists=True, readable=True, help="输入图片"),
    out: Optional[Path] = typer.Option(None, help="输出 PNG 路径"),
    analysis_json: Optional[Path] = typer.Option(
        None, "--analysis", help="可选：已有的 PixAnalysis JSON 文件"
    ),
    pixel_size: str = typer.Option("128x128", help="输出像素尺寸"),
    colors: int = typer.Option(16, min=2, max=256, help="调色板颜色数"),
    dither: str = typer.Option("floyd_steinberg", help="none|ordered|floyd_steinberg"),
    preset: str = typer.Option("auto", help=f"风格预设：{list_presets()}"),
    preview_scale: int = typer.Option(4, help="预览放大倍数，0 关闭"),
    edge_enhance: float = typer.Option(0.1, min=0.0, max=1.0, help="主体锐化强度"),
    saturation: float = typer.Option(1.0, min=0.0, max=2.0, help="饱和度缩放"),
    resample: str = typer.Option("smart", help="下采样：smart|box|bicubic|lanczos|nearest"),
    snap_to_grid: bool = typer.Option(True, "--snap/--no-snap", help="smart 模式下探测输入像素格并吸附"),
    remove_bg: bool = typer.Option(False, "--remove-bg", help="自动抠背景（四角 flood-fill，输出 PNG 带 alpha）"),
    bg_tolerance: int = typer.Option(12, min=0, max=128, help="背景颜色容差，越大抠越狠"),
    bg_feather: int = typer.Option(0, min=0, max=8, help="主体边缘保留的像素圈数"),
    auto_crop: bool = typer.Option(False, "--auto-crop/--no-auto-crop", help="自动裁剪主体后再缩小"),
    crop_padding: float = typer.Option(0.12, min=0.0, max=1.0, help="自动裁剪外扩比例"),
    crop_square: bool = typer.Option(True, "--crop-square/--no-crop-square", help="自动裁剪时保持正方形"),
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """把图片像素化（不依赖网络）。"""
    _base_config(config)  # 读一次 .env/config 以保持行为一致（即便不用 cfg 本体）
    size = _parse_size(pixel_size)
    params = PixelizeParams(
        output_size=size,
        colors=colors,
        dither=dither,  # type: ignore[arg-type]
        preset=preset,
        preview_scale=preview_scale,
        edge_enhance=edge_enhance,
        saturation=saturation,
        resample=resample,  # type: ignore[arg-type]
        snap_to_grid=snap_to_grid,
        remove_bg=remove_bg,
        bg_tolerance=bg_tolerance,
        bg_feather=bg_feather,
        auto_crop=auto_crop,
        crop_padding=crop_padding,
        crop_square=crop_square,
    )
    analysis: PixAnalysis | None = None
    if analysis_json:
        try:
            analysis = PixAnalysis.model_validate_json(analysis_json.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[yellow]分析 JSON 解析失败，将跳过：{exc}[/yellow]")

    pixel_img, preview_img, meta = run_pixelize(image, params, analysis=analysis)
    target = out or image.with_name(f"{image.stem}_pix.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    pixel_img.save(target)
    console.print(Panel.fit(f"[green][OK][/green] {target}\n{json.dumps(meta, ensure_ascii=False, indent=2)}", title="pixelize"))
    if preview_img is not None:
        preview_target = target.with_name(target.stem + "_preview.png")
        preview_img.save(preview_target)
        console.print(f"预览：{preview_target}")


# ---------- grid commands ----------


@app.command("grid-extract")
def cmd_grid_extract(
    image: Path = typer.Argument(..., exists=True, readable=True, help="输入高清伪像素图"),
    out: Path = typer.Option(..., help="输出 .grid.json 路径"),
    render: Optional[Path] = typer.Option(None, help="可选：同时渲染 PNG 到该路径"),
    pixel_size: str = typer.Option("16x16", help="目标网格尺寸"),
    colors: int = typer.Option(12, min=2, max=256, help="最大调色板颜色数"),
    preview_scale: int = typer.Option(0, min=0, help="渲染 PNG 时的预览放大倍数"),
    auto_crop: bool = typer.Option(True, "--auto-crop/--no-auto-crop", help="提取前自动裁剪主体"),
    crop_padding: float = typer.Option(0.12, min=0.0, max=1.0, help="自动裁剪外扩比例"),
    crop_square: bool = typer.Option(True, "--crop-square/--no-crop-square", help="自动裁剪保持正方形"),
    remove_bg: bool = typer.Option(True, "--remove-bg/--no-remove-bg", help="提取前把四角背景转透明"),
    bg_tolerance: int = typer.Option(26, min=0, max=128, help="背景容差"),
) -> None:
    """从伪像素图提取 Pixel Grid JSON。"""
    size = _parse_size(pixel_size)
    grid = extract_pixel_grid(
        image,
        output_size=size,
        max_colors=colors,
        auto_crop=auto_crop,
        crop_padding=crop_padding,
        crop_square=crop_square,
        remove_bg=remove_bg,
        bg_tolerance=bg_tolerance,
    )
    save_grid(grid, out)
    rendered: Path | None = None
    preview: Path | None = None
    if render is not None:
        rendered, preview = render_grid_file(out, render, preview_scale=preview_scale)
    console.print(Panel.fit(
        f"[green][OK][/green] Grid JSON：{out}\n"
        f"渲染：{rendered or '未渲染'}\n"
        f"预览：{preview or '未输出'}",
        title="grid-extract",
    ))


@app.command("grid-render")
def cmd_grid_render(
    grid_json: Path = typer.Argument(..., exists=True, readable=True, help="Pixel Grid JSON"),
    out: Path = typer.Option(..., help="输出 PNG 路径"),
    preview_scale: int = typer.Option(0, min=0, help="预览放大倍数"),
) -> None:
    """根据 Pixel Grid JSON 精确渲染 PNG。"""
    rendered, preview = render_grid_file(grid_json, out, preview_scale=preview_scale)
    console.print(Panel.fit(
        f"[green][OK][/green] PNG：{rendered}\n预览：{preview or '未输出'}",
        title="grid-render",
    ))


@app.command("grid-polish")
def cmd_grid_polish(
    grid_json: Path = typer.Argument(..., exists=True, readable=True, help="Pixel Grid JSON"),
    out: Path = typer.Option(..., help="后处理后的 JSON 输出路径"),
    render: Optional[Path] = typer.Option(None, help="可选：同时渲染 PNG"),
    preview_scale: int = typer.Option(0, min=0, help="渲染 PNG 时的预览放大倍数"),
    cleanup: bool = typer.Option(True, "--cleanup/--no-cleanup", help="清理孤立噪点"),
    outline: bool = typer.Option(True, "--outline/--no-outline", help="统一主体轮廓"),
    outline_strength: int = typer.Option(1, min=0, max=3, help="轮廓强度"),
    min_neighbors: int = typer.Option(1, min=0, max=8, help="非透明像素最小邻居数"),
    max_colors: int = typer.Option(12, min=2, max=256, help="最大调色板颜色数"),
) -> None:
    """对 Pixel Grid JSON 做清噪、补轮廓和调色板整理。"""
    grid = load_grid(grid_json)
    polished = polish_pixel_grid(
        grid,
        cleanup=cleanup,
        outline=outline,
        outline_strength=outline_strength,
        min_neighbors=min_neighbors,
        max_colors=max_colors,
    )
    save_grid(polished, out)
    rendered: Path | None = None
    preview: Path | None = None
    if render is not None:
        rendered, preview = render_grid_file(out, render, preview_scale=preview_scale)
    console.print(Panel.fit(
        f"[green][OK][/green] 后处理 JSON：{out}\n"
        f"调色板：{len(polished.palette)} 色\n"
        f"渲染：{rendered or '未渲染'}\n"
        f"预览：{preview or '未输出'}",
        title="grid-polish",
    ))


@app.command("grid-review")
def cmd_grid_review(
    grid_json: Path = typer.Argument(..., exists=True, readable=True, help="Pixel Grid JSON"),
    out: Path = typer.Option(..., help="审核后 JSON 输出路径"),
    model: Optional[str] = typer.Option(None, help="覆盖视觉/LLM 模型"),
    instruction: str = typer.Option("", help="额外审核要求"),
    render: Optional[Path] = typer.Option(None, help="可选：同时渲染审核后的 PNG"),
    preview_scale: int = typer.Option(0, min=0, help="渲染 PNG 时的预览放大倍数"),
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """让 AI 审核/修正 Pixel Grid JSON。"""
    cfg = _base_config(config)
    reviewed = review_grid_file(cfg, grid_json, out, model=model, instruction=instruction)
    rendered: Path | None = None
    preview: Path | None = None
    if render is not None:
        rendered, preview = render_grid_file(out, render, preview_scale=preview_scale)
    console.print(Panel.fit(
        f"[green][OK][/green] 审核 JSON：{out}\n"
        f"尺寸：{reviewed.canvas.width}x{reviewed.canvas.height}\n"
        f"渲染：{rendered or '未渲染'}\n"
        f"预览：{preview or '未输出'}",
        title="grid-review",
    ))


# ---------- asset (game-ready sprite output) ----------


@app.command("asset")
def cmd_asset(
    name: str = typer.Argument(..., help="素材名称，会注入游戏物品 prompt 模板"),
    out: Optional[Path] = typer.Option(None, help="最终 PNG 路径；默认写到 [asset].output_dir/name.png"),
    pixel_size: Optional[str] = typer.Option(None, help="输出像素尺寸，默认读 [asset].pixel_size"),
    colors: int = typer.Option(0, min=0, max=256, help="可见颜色数；0 表示读 [asset].colors"),
    extra_prompt: str = typer.Option("", help="追加到内置游戏素材模板后的额外英文/中文提示"),
    image_size: Optional[str] = typer.Option(None, help="生图尺寸，默认读 [image_gen].size"),
    image_quality: Optional[str] = typer.Option(None, help="生图质量，默认读 [asset].image_quality"),
    vl_model: Optional[str] = typer.Option(None, help="启用 --use-vl 时覆盖视觉模型"),
    use_vl: bool = typer.Option(False, "--use-vl", help="启用多模态分析；默认跳过以节省成本"),
    no_cache: bool = typer.Option(False, help="禁用缓存"),
    refresh: bool = typer.Option(False, help="忽略缓存命中，强制刷新"),
    overwrite: bool = typer.Option(False, "--overwrite", help="允许覆盖已存在的最终 PNG/预览/sidecar"),
    no_preview: bool = typer.Option(False, "--no-preview", help="不输出放大预览图"),
    no_sidecars: bool = typer.Option(False, "--no-sidecars", help="不输出 .asset.json 元数据"),
    source_copy: Optional[bool] = typer.Option(None, "--source-copy/--no-source-copy", help="把原始生图源文件复制到最终目录旁边"),
    grid_mode: Optional[bool] = typer.Option(None, "--grid-mode/--no-grid-mode", help="用 Pixel Grid JSON 工程图渲染最终 PNG"),
    grid_review: bool = typer.Option(False, "--grid-review", help="让 AI 审核/修正 Grid JSON 后再渲染"),
    grid_cleanup: Optional[bool] = typer.Option(None, "--grid-cleanup/--no-grid-cleanup", help="Grid JSON 后处理：清理孤立噪点"),
    grid_outline: Optional[bool] = typer.Option(None, "--grid-outline/--no-grid-outline", help="Grid JSON 后处理：统一主体轮廓"),
    grid_json: Optional[Path] = typer.Option(None, help="Grid JSON 输出路径；默认 target.stem + .grid.json"),
    no_grid_json: bool = typer.Option(False, "--no-grid-json", help="grid-mode 下不保存 .grid.json"),
    run_root: Optional[Path] = typer.Option(None, help="中间运行目录根；默认使用 [output].root"),
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """生成可直接用于游戏资源目录的透明像素素材。"""
    cfg = _base_config(config)
    size = _parse_size(pixel_size) if pixel_size else tuple(cfg.asset.pixel_size)
    effective_colors = int(colors or cfg.asset.colors)
    if effective_colors < 2:
        raise typer.BadParameter("颜色数必须 >= 2；传 0 表示使用配置默认值")

    target = out or Path(cfg.asset.output_dir) / f"{safe_asset_filename(name)}.png"
    preview_target = target.with_name(target.stem + "_preview.png")
    source_target = target.with_name(target.stem + "_source.png")
    sidecar_target = target.with_name(target.stem + ".asset.json")
    grid_target = grid_json or target.with_name(target.stem + ".grid.json")
    effective_grid_mode = bool(cfg.asset.grid_mode if grid_mode is None else grid_mode)
    effective_source_copy = bool(cfg.asset.source_copy if source_copy is None else source_copy)
    write_targets = [target]
    if not no_preview:
        write_targets.append(preview_target)
    if effective_source_copy:
        write_targets.append(source_target)
    if not no_sidecars:
        write_targets.append(sidecar_target)
    if effective_grid_mode and cfg.asset.grid_json and not no_grid_json:
        write_targets.append(grid_target)
    for p in write_targets:
        if p.exists() and not overwrite:
            console.print(f"[red]目标已存在：{p}[/red]\n如需覆盖请加 --overwrite。")
            raise typer.Exit(code=2)

    prompt = build_asset_prompt(
        cfg.asset.prompt_template,
        name,
        size=size,
        extra_prompt=extra_prompt,
    )
    params = PixelizeParams(
        output_size=size,
        colors=effective_colors,
        dither=cfg.asset.dither,  # type: ignore[arg-type]
        preset="auto",
        preview_scale=0 if no_preview else cfg.asset.preview_scale,
        edge_enhance=cfg.pixelize.edge_enhance,
        saturation=cfg.pixelize.saturation,
        resample=cfg.pixelize.resample,  # type: ignore[arg-type]
        snap_to_grid=cfg.pixelize.snap_to_grid,
        remove_bg=cfg.asset.remove_bg,
        bg_tolerance=cfg.asset.bg_tolerance,
        bg_feather=cfg.asset.bg_feather,
        auto_crop=cfg.asset.auto_crop,
        crop_padding=cfg.asset.crop_padding,
        crop_square=cfg.asset.crop_square,
    )
    console.log(f"生成素材：{name!r} → {target}")
    result = run_pipeline(
        cfg,
        PipelineInput(
            prompt=prompt,
            image_size=image_size or cfg.image_gen.size,
            image_quality=image_quality or cfg.asset.image_quality,
            vl_model=vl_model,
            skip_vl=(not use_vl) if use_vl else cfg.asset.skip_vl,
            pixelize_params=params,
            out_root=run_root or cfg.output.root,
            use_cache=not no_cache,
            refresh_cache=refresh,
        ),
        progress=_progress_printer,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    copied_preview: Path | None = None
    copied_source: Path | None = None
    saved_grid: Path | None = None
    if effective_source_copy:
        shutil.copyfile(result.source_path, source_target)
        copied_source = source_target
    if effective_grid_mode:
        grid = extract_pixel_grid(
            result.source_path,
            output_size=size,
            max_colors=effective_colors,
            auto_crop=cfg.asset.auto_crop,
            crop_padding=cfg.asset.crop_padding,
            crop_square=cfg.asset.crop_square,
            remove_bg=cfg.asset.remove_bg,
            bg_tolerance=cfg.asset.bg_tolerance,
            metadata={"asset_name": name, "prompt": prompt, "run_dir": str(result.run_dir)},
        )
        effective_cleanup = cfg.asset.grid_cleanup if grid_cleanup is None else grid_cleanup
        effective_outline = cfg.asset.grid_outline if grid_outline is None else grid_outline
        if effective_cleanup or effective_outline:
            grid = polish_pixel_grid(
                grid,
                cleanup=effective_cleanup,
                outline=effective_outline,
                outline_strength=cfg.asset.grid_outline_strength,
                min_neighbors=cfg.asset.grid_min_neighbors,
                max_colors=effective_colors,
            )
        if grid_review or cfg.asset.grid_review:
            grid = review_pixel_grid(cfg, grid, model=vl_model)
        if cfg.asset.grid_json and not no_grid_json:
            save_grid(grid, grid_target)
            saved_grid = grid_target
        final_img = render_pixel_grid(grid)
        final_img.save(target)
        if not no_preview:
            final_img.resize(
                (final_img.width * cfg.asset.preview_scale, final_img.height * cfg.asset.preview_scale),
                resample=Image.Resampling.NEAREST,
            ).save(preview_target)
            copied_preview = preview_target
    else:
        shutil.copyfile(result.pixel_path, target)
        if result.preview_path is not None and not no_preview:
            shutil.copyfile(result.preview_path, preview_target)
            copied_preview = preview_target

    if not no_sidecars:
        sidecar = {
            "name": name,
            "prompt": prompt,
            "target": str(target),
            "preview": str(copied_preview) if copied_preview else None,
            "source_copy": str(copied_source) if copied_source else None,
            "grid_mode": effective_grid_mode,
            "grid": str(saved_grid) if saved_grid else None,
            "run_dir": str(result.run_dir),
            "source": str(result.source_path),
            "analysis": str(result.analysis_path) if result.analysis_path else None,
            "meta": result.meta,
        }
        sidecar_target.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")

    report = validate_asset_image(
        target,
        expected_size=size,
        max_colors=effective_colors,
        require_alpha=True,
        require_transparency=params.remove_bg,
    )
    _print_validation_report(report)
    if not report.ok:
        raise typer.Exit(code=1)

    console.print(Panel.fit(
        f"[green][OK][/green] 素材已保存：{target}\n"
        f"原图源文件：{copied_source or result.source_path}\n"
        f"预览：{copied_preview or '未输出'}\n"
        f"运行目录：{result.run_dir}",
        title="asset",
    ))


# ---------- gen (full pipeline from prompt) ----------


@app.command("gen")
def cmd_gen(
    prompt: str = typer.Argument(..., help="文生图提示词"),
    image_size: str = typer.Option("1024x1024", help="生图尺寸"),
    image_quality: str = typer.Option("high", help="low|medium|high|auto"),
    pixel_size: str = typer.Option("128x128", help="输出像素尺寸"),
    colors: int = typer.Option(16, min=2, max=256),
    dither: str = typer.Option("floyd_steinberg"),
    preset: str = typer.Option("auto"),
    vl_model: Optional[str] = typer.Option(None, help="VL 模型"),
    no_vl: bool = typer.Option(False, help="跳过多模态分析"),
    no_cache: bool = typer.Option(False, help="禁用缓存"),
    refresh: bool = typer.Option(False, help="忽略缓存命中，强制刷新"),
    out: Optional[Path] = typer.Option(None, help="输出根目录；为空则使用配置里的 output.root"),
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """prompt 一路到底：文生图 → 分析 → 像素化。"""
    cfg = _base_config(config)
    params = PixelizeParams(
        output_size=_parse_size(pixel_size),
        colors=colors,
        dither=dither,  # type: ignore[arg-type]
        preset=preset,
    )
    inputs = PipelineInput(
        prompt=prompt,
        image_size=image_size,
        image_quality=image_quality,
        vl_model=vl_model,
        skip_vl=no_vl,
        pixelize_params=params,
        out_root=out,
        use_cache=not no_cache,
        refresh_cache=refresh,
    )
    result = run_pipeline(cfg, inputs, progress=_progress_printer)
    _print_result(result.meta, result.run_dir)


# ---------- run (full pipeline from image) ----------


@app.command("run")
def cmd_run(
    image: Path = typer.Argument(..., exists=True, readable=True, help="已有图片"),
    pixel_size: str = typer.Option("128x128"),
    colors: int = typer.Option(16, min=2, max=256),
    dither: str = typer.Option("floyd_steinberg"),
    preset: str = typer.Option("auto"),
    vl_model: Optional[str] = typer.Option(None),
    no_vl: bool = typer.Option(False),
    no_cache: bool = typer.Option(False),
    refresh: bool = typer.Option(False),
    out: Optional[Path] = typer.Option(None),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """已有图片 → 分析 → 像素化。"""
    cfg = _base_config(config)
    params = PixelizeParams(
        output_size=_parse_size(pixel_size),
        colors=colors,
        dither=dither,  # type: ignore[arg-type]
        preset=preset,
    )
    inputs = PipelineInput(
        image_path=image,
        vl_model=vl_model,
        skip_vl=no_vl,
        pixelize_params=params,
        out_root=out,
        use_cache=not no_cache,
        refresh_cache=refresh,
    )
    result = run_pipeline(cfg, inputs, progress=_progress_printer)
    _print_result(result.meta, result.run_dir)


# ---------- validate ----------


@app.command("validate")
def cmd_validate(
    image: Path = typer.Argument(..., exists=True, readable=True, help="要检查的 PNG 素材"),
    pixel_size: Optional[str] = typer.Option(None, help="期望尺寸，如 16x16；为空则不检查尺寸"),
    max_colors: int = typer.Option(16, min=0, max=256, help="最大可见颜色数；0 表示不检查"),
    allow_no_alpha: bool = typer.Option(False, "--allow-no-alpha", help="允许没有 alpha 通道"),
    allow_opaque: bool = typer.Option(False, "--allow-opaque", help="允许没有透明背景像素"),
) -> None:
    """检查 PNG 是否适合作为像素游戏素材。"""
    expected = _parse_size(pixel_size) if pixel_size else None
    report = validate_asset_image(
        image,
        expected_size=expected,
        max_colors=max_colors or None,
        require_alpha=not allow_no_alpha,
        require_transparency=not allow_opaque,
    )
    _print_validation_report(report)
    raise typer.Exit(code=0 if report.ok else 1)


# ---------- batch ----------


@app.command("batch")
def cmd_batch(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, readable=True, help="输入目录（递归扫描）"),
    output_dir: Path = typer.Argument(..., help="输出目录，自动创建"),
    pixel_size: str = typer.Option("128x128", help="输出像素尺寸"),
    colors: int = typer.Option(16, min=2, max=256),
    dither: str = typer.Option("floyd_steinberg"),
    preset: str = typer.Option("auto"),
    resample: str = typer.Option("smart", help="下采样：smart|box|bicubic|lanczos|nearest"),
    snap_to_grid: bool = typer.Option(True, "--snap/--no-snap"),
    remove_bg: bool = typer.Option(False, "--remove-bg"),
    bg_tolerance: int = typer.Option(12, min=0, max=128),
    bg_feather: int = typer.Option(0, min=0, max=8),
    auto_crop: bool = typer.Option(False, "--auto-crop/--no-auto-crop"),
    crop_padding: float = typer.Option(0.12, min=0.0, max=1.0),
    crop_square: bool = typer.Option(True, "--crop-square/--no-crop-square"),
    use_vl: bool = typer.Option(False, "--use-vl/--no-vl", help="是否调用视觉模型分析每张图（成本较高）"),
    vl_model: Optional[str] = typer.Option(None, help="覆盖 VL 模型名"),
    workers: int = typer.Option(4, min=1, max=32, help="并发线程数"),
    overwrite: bool = typer.Option(False, "--overwrite", help="已存在的输出也覆盖；默认跳过"),
    no_sidecars: bool = typer.Option(False, "--no-sidecars", help="不产出 .analysis.json / .meta.json"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """批量像素化一个目录里的图片（支持并发）。"""
    cfg = _base_config(config)
    from pix.batch import BatchItem, run_batch  # 延迟导入，减少 pix --help 的启动开销

    params = PixelizeParams(
        output_size=_parse_size(pixel_size),
        colors=colors,
        dither=dither,  # type: ignore[arg-type]
        preset=preset,
        resample=resample,  # type: ignore[arg-type]
        snap_to_grid=snap_to_grid,
        remove_bg=remove_bg,
        bg_tolerance=bg_tolerance,
        bg_feather=bg_feather,
        auto_crop=auto_crop,
        crop_padding=crop_padding,
        crop_square=crop_square,
    )

    def _on_done(item: BatchItem, done: int, total: int) -> None:
        mark = {
            "ok": "[green][OK][/green]",
            "skipped": "[yellow][skip][/yellow]",
            "failed": "[red][FAIL][/red]",
        }.get(item.status, item.status)
        tail = f" · {item.error}" if item.error else ""
        console.log(f"[{done}/{total}] {mark} {item.src.name}{tail}")

    result = run_batch(
        cfg,
        input_dir,
        output_dir,
        pixelize_params=params,
        use_vl=use_vl,
        vl_model=vl_model,
        workers=workers,
        write_sidecars=not no_sidecars,
        overwrite=overwrite,
        on_item_done=_on_done,
    )
    console.print(Panel.fit(result.summary(), title="pix batch"))
    if result.failed:
        console.print("[red]失败文件：[/red]")
        for it in result.failed:
            console.print(f"  - {it.src} · {it.error}")


# ---------- presets ----------


@app.command("presets")
def cmd_presets() -> None:
    """列出所有可用预设。"""
    tbl = Table(title="预设")
    tbl.add_column("name")
    for n in list_presets():
        tbl.add_row(n)
    console.print(tbl)


# ---------- gui ----------


@app.command("gui")
def cmd_gui(
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """启动可视化窗口。"""
    try:
        from pix.gui.app import run_gui
    except ImportError as exc:
        console.print(f"[red]无法启动 GUI：{exc}。请先安装 PySide6（pip install PySide6）。[/red]")
        raise typer.Exit(code=2)
    run_gui(config_file=config)


# ---------- helpers ----------


def _print_validation_report(report) -> None:
    tbl = Table(title=f"资源检查：{report.path}")
    tbl.add_column("项目")
    tbl.add_column("值")
    tbl.add_row("尺寸", f"{report.size[0]}x{report.size[1]}" if report.size else "未知")
    tbl.add_row("模式", report.mode or "未知")
    tbl.add_row("可见颜色数", str(report.visible_color_count))
    tbl.add_row("主体 bbox", str(report.alpha_bbox))
    status = "[green]OK[/green]" if report.ok else "[red]FAILED[/red]"
    tbl.add_row("结果", status)
    console.print(tbl)
    for issue in report.issues:
        color = "red" if issue.level == "error" else "yellow"
        console.print(f"[{color}]{issue.level.upper()} {issue.code}[/] {issue.message}")


def _print_result(meta: dict, run_dir: Path) -> None:
    console.print(Panel.fit(
        f"运行目录：[bold]{run_dir}[/bold]\n" + json.dumps(meta, ensure_ascii=False, indent=2),
        title="pix 完成",
    ))


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
