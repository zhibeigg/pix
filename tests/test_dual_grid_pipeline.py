from __future__ import annotations
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
