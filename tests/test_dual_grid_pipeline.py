from __future__ import annotations

import contextlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

import pix_web.pipeline_adapter as pa
from pix.config import AppConfig
from pix_web.schemas import AssetParamsSchema


def test_schema_accepts_dual_grid_fields() -> None:
    p = AssetParamsSchema(
        name="草地泥土",
        asset_kind="dual_grid",
        material_a="草地",
        material_b="泥土",
        transition_style="rounded",
    )
    assert p.asset_kind == "dual_grid"
    assert p.material_a == "草地" and p.material_b == "泥土"
    assert p.transition_style == "rounded"


def test_schema_dual_grid_defaults_transition_rounded() -> None:
    p = AssetParamsSchema(name="x", asset_kind="dual_grid", material_a="草", material_b="")
    assert p.transition_style == "rounded"
    assert p.material_b == ""   # 空串 = 透明模式（不报错）


def test_dual_grid_pipeline_outputs(monkeypatch, tmp_path) -> None:
    # mock 生图：按 prompt 里材质关键词写纯色图，绕过真实 API
    def fake_generate_image(cfg, prompt, raw_path, **kw):
        color = (10, 200, 10, 255) if "草" in prompt else (180, 120, 60, 255)
        Image.new("RGBA", (256, 256), color).save(raw_path)
    monkeypatch.setattr(pa, "generate_image", fake_generate_image)
    # 本地阶段上下文在测试里用 nullcontext 占位（解耦真实生图环境）
    monkeypatch.setattr(pa, "_local_stage_context", lambda settings: (lambda: contextlib.nullcontext()))

    # job/settings 仿 tests/test_candidate_reprocess.py 的 SimpleNamespace 模式（无共享 helper）
    job = SimpleNamespace(
        id=101, job_type="asset", prompt="草地泥土双瓦片", input_image_path=None,
        params_json={
            "pixelize": {"output_size": [32, 32], "colors": 12},
            "asset": {
                "name": "草地泥土双瓦片", "asset_kind": "dual_grid",
                "material_a": "草地", "material_b": "泥土", "transition_style": "rounded",
            },
        },
    )
    settings = SimpleNamespace(storage_root=tmp_path)
    result = pa.run_dual_grid_asset_job_pipeline(job, settings, AppConfig())  # type: ignore[arg-type]

    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    assert meta["asset"]["asset_kind"] == "dual_grid"
    assert meta["asset"]["convention"] == "pix-dualgrid-v1"
    assert len(meta["asset"]["mapping"]) == 16
    atlas = Image.open(result.run_dir / "dual_grid_atlas.png")
    w, h = meta["asset"]["tile_size"]
    assert atlas.size == (w * 4, h * 4)
    assert (result.run_dir / "dual_grid_preview.png").exists()


def test_output_response_exposes_dual_grid_paths(tmp_path) -> None:
    meta = {"outputs": {"dual_grid_atlas": "dual_grid_atlas.png",
                        "dual_grid_preview": "dual_grid_preview.png"}}
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    (tmp_path / "dual_grid_atlas.png").write_bytes(b"x")
    (tmp_path / "dual_grid_preview.png").write_bytes(b"x")
    from pix_web.schemas import JobOutputResponse
    # JobOutputResponse 6 个必填字段（preview_path/analysis_json_path 无默认，须显式传）
    resp = JobOutputResponse(
        run_dir=str(tmp_path),
        source_path=str(tmp_path / "x.png"),
        pixelized_path=str(tmp_path / "dual_grid_atlas.png"),
        preview_path=str(tmp_path / "dual_grid_preview.png"),
        analysis_json_path=None,
        meta_json_path=str(meta_path),
    )
    assert resp.dual_grid_atlas_path and resp.dual_grid_atlas_path.endswith("dual_grid_atlas.png")
    assert resp.dual_grid_preview_path.endswith("dual_grid_preview.png")
