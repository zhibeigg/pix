"""Typer CLI。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _make_console() -> "Console":
    """Windows cp936 终端下 rich 用 Unicode 会炸，这里强制 utf-8。"""
    try:
        # 强制 sys.stdout 使用 utf-8，避免 cp936 编码 '✓' '→' 这类字符失败
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return Console()

from pix import __version__
from pix.analysis.schema import PixAnalysis
from pix.api.image_gen import generate_image
from pix.api.vision import analyze_image
from pix.config import AppConfig, load_config
from pix.pipeline import PipelineInput, run_pipeline
from pix.pixelize.core import PixelizeParams, pixelize as run_pixelize
from pix.pixelize.presets import list_presets


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
    config: Optional[Path] = typer.Option(None, "--config", help="TOML 配置文件"),
) -> None:
    """把图片像素化（不依赖网络）。"""
    cfg = _base_config(config)
    size = _parse_size(pixel_size)
    params = PixelizeParams(
        output_size=size,
        colors=colors,
        dither=dither,  # type: ignore[arg-type]
        preset=preset,
        preview_scale=preview_scale,
        edge_enhance=edge_enhance,
        saturation=saturation,
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


# ---------- presets ----------


# ---------- batch ----------


@app.command("batch")
def cmd_batch(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, readable=True, help="输入目录（递归扫描）"),
    output_dir: Path = typer.Argument(..., help="输出目录，自动创建"),
    pixel_size: str = typer.Option("128x128", help="输出像素尺寸"),
    colors: int = typer.Option(16, min=2, max=256),
    dither: str = typer.Option("floyd_steinberg"),
    preset: str = typer.Option("auto"),
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


def _print_result(meta: dict, run_dir: Path) -> None:
    console.print(Panel.fit(
        f"运行目录：[bold]{run_dir}[/bold]\n" + json.dumps(meta, ensure_ascii=False, indent=2),
        title="pix 完成",
    ))


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
