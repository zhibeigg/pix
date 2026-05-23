import json
from pathlib import Path

from PIL import Image

from pix.api.prompt_guard import local_prompt_guard
from pix.config import AppConfig
from pix.pipeline import PipelineInput, run_pipeline
from pix.pixelize.core import PixelizeParams


def test_source_only_prompt_policy_allows_single_image_constraints() -> None:
    result = local_prompt_guard("只生成一张蓝色药水图标，不要九宫格，不要抠图。", allow_template_break=True)

    assert result.allowed


def test_regular_prompt_policy_still_blocks_template_breaking() -> None:
    result = local_prompt_guard("只生成一张蓝色药水图标，不要九宫格，不要抠图。")

    assert not result.allowed


def test_source_only_pipeline_generates_one_unprocessed_image(monkeypatch, tmp_path: Path) -> None:
    prompt = "只生成一张蓝色药水图标，不要抠图。"

    def fake_generate_image(
        cfg: AppConfig,
        actual_prompt: str,
        dest_path: Path,
        *,
        size: str | None = None,
        quality: str | None = None,
        model: str | None = None,
        output_format: str | None = None,
        n: int = 1,
    ) -> Path:
        assert actual_prompt == prompt
        assert n == 1
        Image.new("RGB", (64, 64), (24, 96, 180)).save(dest_path)
        return dest_path

    monkeypatch.setattr("pix.pipeline.generate_image", fake_generate_image)
    cfg = AppConfig()
    cfg.cache.enabled = False
    cfg.image_gen.prompt_guard_remote = False
    result = run_pipeline(
        cfg,
        PipelineInput(
            prompt=prompt,
            skip_vl=False,
            source_only=True,
            out_root=tmp_path,
            pixelize_params=PixelizeParams(),
        ),
    )

    assert result.source_path == result.pixel_path
    assert result.source_path.exists()
    assert result.analysis_path is None
    assert result.preview_path is None
    assert not (result.run_dir / "01_contact_sheet.png").exists()
    assert not (result.run_dir / "03_pixelized.png").exists()

    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["image_gen"]["source_only"] is True
    assert meta["image_gen"]["contact_sheet"] is None
    assert meta["vision"]["skipped"] is True
    assert meta["pixelize"]["skipped"] is True
    assert meta["outputs"]["source"] == "01_source.png"
    assert meta["outputs"]["pixelized"] == "01_source.png"
