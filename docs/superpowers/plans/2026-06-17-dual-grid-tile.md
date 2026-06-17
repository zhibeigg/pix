# 双瓦片（dual-grid）素材直出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `asset_kind="dual_grid"` 素材直出：AI 生成两张无缝材质 A/B，代码用 16 个角掩码确定性合成可无缝拼接的 4×4 双瓦片图集 + 应用预览 + 映射 meta。

**Architecture:** 纯算法模块 `src/pix/dual_grid.py`（角掩码 / 单瓦片合成 / 图集 / 预览，零网络）+ Web 端 `run_dual_grid_asset_job_pipeline`（复用现有 tile_texture 生图路径生成 A、B，再调纯算法合成落盘）。无缝性由「边不变量」构造保证：每条瓦片边只由该边两端两个角 + 中点二分决定，rounded 过渡用双线性角场阈值实现（沿边只依赖端点角 → 无缝，内部曲线 → 圆角）。

**Tech Stack:** Python 3.12、numpy、Pillow、pydantic、FastAPI。测试 `uv run --extra dev python -m pytest`。

详见设计：`docs/superpowers/specs/2026-06-17-dual-grid-tile-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/pix/dual_grid.py` | 纯算法：角位编码、16 归属掩码、单瓦片合成、4×4 图集 + 映射、应用预览、种子派生 | 新建 |
| `tests/test_dual_grid.py` | 纯算法全部单测（含核心无缝性测试） | 新建 |
| `src/pix_web/schemas.py` | `AssetParamsSchema` 加 `dual_grid` 与字段；`JobOutputResponse` 加 atlas/preview computed_field | 修改 |
| `src/pix_web/pipeline_adapter.py` | 抽出 `_generate_tile_material()` 复用；加 `run_dual_grid_asset_job_pipeline`；`run_job_pipeline` 路由 | 修改 |
| `src/pix/asset.py` | `dual_grid` 注册进 `ASSET_KIND_LABELS`（防 KeyError） | 修改 |
| `tests/test_dual_grid_pipeline.py` | pipeline 端到端（mock 生图） | 新建 |
| 文档/配置/语言/版本 | `docs/dual-grid-rules.md`、README、`config.example.toml`、locales、ApiPage、CHANGELOG、版本号 | 修改 |

---

## Task 1: 角位编码 + 16 归属掩码 + 无缝性

**Files:**
- Create: `src/pix/dual_grid.py`
- Test: `tests/test_dual_grid.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_dual_grid.py
from __future__ import annotations
import numpy as np
from pix.dual_grid import TL, TR, BL, BR, material_mask


def test_mask_index_0_all_b_and_15_all_a() -> None:
    assert not material_mask(0, 32, 32, "hard").any()
    assert material_mask(15, 32, 32, "hard").all()
    assert not material_mask(0, 32, 32, "rounded").any()
    assert material_mask(15, 32, 32, "rounded").all()


def test_mask_quadrant_corner_mapping_hard() -> None:
    # 仅 TL 角为 A → 左上象限为 A，其余 B
    m = material_mask(TL, 32, 32, "hard")
    assert m[:16, :16].all()
    assert not m[:16, 16:].any()
    assert not m[16:, :16].any()
    assert not m[16:, 16:].any()


def _shares_horizontal_edge(left: int, right: int) -> bool:
    # 水平相邻：左瓦片右两角(TR,BR) == 右瓦片左两角(TL,BL)
    return (bool(left & TR) == bool(right & TL)) and (bool(left & BR) == bool(right & BL))


def _shares_vertical_edge(top: int, bottom: int) -> bool:
    # 竖直相邻：上瓦片下两角(BL,BR) == 下瓦片上两角(TL,TR)
    return (bool(top & BL) == bool(bottom & TL)) and (bool(top & BR) == bool(bottom & TR))


import pytest


@pytest.mark.parametrize("style", ["hard", "rounded", "outline"])
@pytest.mark.parametrize("size", [(32, 32), (33, 31), (16, 16)])
def test_seamless_shared_edges_match(style: str, size: tuple[int, int]) -> None:
    """核心无缝性：任意两张共享一条边的瓦片，沿共享边逐像素归属一致。"""
    w, h = size
    masks = [material_mask(i, w, h, style) for i in range(16)]
    for a in range(16):
        for b in range(16):
            if _shares_horizontal_edge(a, b):
                assert np.array_equal(masks[a][:, -1], masks[b][:, 0]), f"H {a}->{b} {style} {size}"
            if _shares_vertical_edge(a, b):
                assert np.array_equal(masks[a][-1, :], masks[b][0, :]), f"V {a}->{b} {style} {size}"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid.py -q`
Expected: FAIL（`ModuleNotFoundError: pix.dual_grid` 或 `material_mask` 未定义）

- [ ] **Step 3: 写最小实现**

```python
# src/pix/dual_grid.py
"""dual-grid 双瓦片纯算法：16 角掩码 → 单瓦片合成 → 4×4 图集 → 应用预览。

零网络、零 I/O。无缝性由「边不变量」构造保证：每条瓦片边只由该边两端两个角 + 中点二分
决定；相邻显示瓦片共享边 → 共享该边两端两个角 → 边逐像素归属一致。rounded 过渡用
双线性角场阈值：沿任一边，场只由该边两端角线性插值 → 阈值点恒在中点，故边规则成立；
内部是曲线 → 圆角。
"""
from __future__ import annotations

from typing import Literal

import numpy as np

# 角位：TL=bit0, TR=bit1, BL=bit2, BR=bit3；A=1, B=0
TL, TR, BL, BR = 1, 2, 4, 8
ATLAS_ROWS = ATLAS_COLS = 4
CONVENTION = "pix-dualgrid-v1"

TransitionStyle = Literal["rounded", "hard", "outline"]


def material_mask(idx: int, w: int, h: int, style: str) -> np.ndarray:
    """返回 (h, w) 的布尔掩码：True = 该像素归材质 A。idx ∈ [0,15] 的角位组合。"""
    sw, sh = max(1, int(w)), max(1, int(h))
    tl, tr, bl, br = (idx & TL) != 0, (idx & TR) != 0, (idx & BL) != 0, (idx & BR) != 0
    if style == "hard":
        mx, my = sw // 2, sh // 2
        m = np.empty((sh, sw), dtype=bool)
        m[:my, :mx] = tl
        m[:my, mx:] = tr
        m[my:, :mx] = bl
        m[my:, mx:] = br
        return m
    # rounded / outline 共用双线性角场（outline 的描边在合成阶段叠加）
    xs = np.linspace(0.0, 1.0, sw) if sw > 1 else np.zeros(1)
    ys = np.linspace(0.0, 1.0, sh) if sh > 1 else np.zeros(1)
    u = xs[None, :]
    v = ys[:, None]
    field = (
        float(tl) * (1 - u) * (1 - v)
        + float(tr) * u * (1 - v)
        + float(bl) * (1 - u) * v
        + float(br) * u * v
    )
    return field >= 0.5
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid.py -q`
Expected: PASS（全部用例，含三种 style × 三种尺寸的无缝性）

- [ ] **Step 5: 提交**

```bash
git add src/pix/dual_grid.py tests/test_dual_grid.py
git commit -m "feat(dual-grid): corner-bit masks with seam-safe edge invariant"
```

---

## Task 2: 单瓦片合成 + 4×4 图集 + 映射（含透明/描边）

**Files:**
- Modify: `src/pix/dual_grid.py`
- Test: `tests/test_dual_grid.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_dual_grid.py
from pix.dual_grid import compose_atlas, compose_tile


def _solid(w: int, h: int, rgba: tuple[int, int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :] = rgba
    return arr


def test_compose_tile_fills_a_and_b() -> None:
    mat_a = _solid(32, 32, (10, 200, 10, 255))
    mat_b = _solid(32, 32, (10, 10, 200, 255))
    mask = material_mask(TL, 32, 32, "hard")
    tile = compose_tile(mask, mat_a, mat_b, "hard", (0, 0, 0))
    assert tuple(tile[0, 0]) == (10, 200, 10, 255)      # TL 象限 = A
    assert tuple(tile[0, 31]) == (10, 10, 200, 255)     # TR 象限 = B


def test_compose_tile_transparent_b() -> None:
    mat_a = _solid(32, 32, (10, 200, 10, 255))
    mask = material_mask(TL, 32, 32, "rounded")
    tile = compose_tile(mask, mat_a, None, "rounded", (0, 0, 0))
    assert tile[~mask, 3].max() == 0          # B 区透明
    assert tile[mask, 3].min() == 255         # A 区不透明


def test_compose_tile_outline_borders_a_side() -> None:
    mat_a = _solid(32, 32, (10, 200, 10, 255))
    mask = material_mask(TL, 32, 32, "outline")
    tile = compose_tile(mask, mat_a, None, "outline", (0, 0, 0))
    # 存在被描边的 A 像素（A 区内缘）
    outlined = np.all(tile[:, :, :3] == (0, 0, 0), axis=2) & (tile[:, :, 3] == 255)
    assert outlined.any()
    # 描边只落在 A 区（mask 为 True 处）
    assert not (outlined & ~mask).any()


def test_compose_atlas_layout_and_mapping() -> None:
    mat_a = _solid(16, 16, (10, 200, 10, 255))
    mat_b = _solid(16, 16, (10, 10, 200, 255))
    atlas, tiles, mapping = compose_atlas(mat_a, mat_b, "hard", (0, 0, 0))
    assert atlas.shape == (64, 64, 4)         # 4×4 × 16
    assert len(tiles) == 16 and len(mapping) == 16
    for idx, entry in enumerate(mapping):
        assert entry["bitmask"] == idx
        r, c = entry["row"], entry["col"]
        assert (r, c) == (idx // 4, idx % 4)
        sub = atlas[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
        assert np.array_equal(sub, tiles[idx])
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid.py -q`
Expected: FAIL（`compose_tile` / `compose_atlas` 未定义）

- [ ] **Step 3: 写最小实现（追加到 `src/pix/dual_grid.py`）**

```python
def _a_side_border(mask: np.ndarray) -> np.ndarray:
    """A 区内缘：mask 为 True、且 4 邻域里存在非 A 像素的位置。"""
    non_a = ~mask
    nb = np.zeros_like(mask)
    nb[:-1, :] |= non_a[1:, :]
    nb[1:, :] |= non_a[:-1, :]
    nb[:, :-1] |= non_a[:, 1:]
    nb[:, 1:] |= non_a[:, :-1]
    return mask & nb


def compose_tile(
    mask: np.ndarray,
    mat_a: np.ndarray,
    mat_b: np.ndarray | None,
    style: str,
    outline_rgb: tuple[int, int, int],
) -> np.ndarray:
    """按归属掩码采样材质（本地坐标）合成单瓦片 RGBA。mat_b=None 即透明模式。"""
    h, w = mask.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[mask] = mat_a[mask]
    if mat_b is not None:
        out[~mask] = mat_b[~mask]
    if style == "outline":
        border = _a_side_border(mask)
        out[border, :3] = np.array(outline_rgb, dtype=np.uint8)
        out[border, 3] = 255
    return out


def compose_atlas(
    mat_a: np.ndarray,
    mat_b: np.ndarray | None,
    style: str,
    outline_rgb: tuple[int, int, int],
) -> tuple[np.ndarray, list[np.ndarray], list[dict]]:
    """生成 16 瓦片 + 4×4 图集 + bitmask→cell 映射表。"""
    h, w = mat_a.shape[:2]
    atlas = np.zeros((h * ATLAS_ROWS, w * ATLAS_COLS, 4), dtype=np.uint8)
    tiles: list[np.ndarray] = []
    mapping: list[dict] = []
    for idx in range(16):
        mask = material_mask(idx, w, h, style)
        tile = compose_tile(mask, mat_a, mat_b, style, outline_rgb)
        tiles.append(tile)
        row, col = idx // ATLAS_COLS, idx % ATLAS_COLS
        atlas[row * h:(row + 1) * h, col * w:(col + 1) * w] = tile
        mapping.append({
            "bitmask": idx,
            "row": row,
            "col": col,
            "corners": {"tl": bool(idx & TL), "tr": bool(idx & TR),
                        "bl": bool(idx & BL), "br": bool(idx & BR)},
        })
    return atlas, tiles, mapping
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/pix/dual_grid.py tests/test_dual_grid.py
git commit -m "feat(dual-grid): tile composition, 4x4 atlas, mapping, transparent + outline"
```

---

## Task 3: 应用预览 + 确定性种子

**Files:**
- Modify: `src/pix/dual_grid.py`
- Test: `tests/test_dual_grid.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_dual_grid.py
from pix.dual_grid import preview_seed, render_preview


def test_render_preview_size_and_determinism() -> None:
    mat_a = _solid(16, 16, (10, 200, 10, 255))
    mat_b = _solid(16, 16, (10, 10, 200, 255))
    _atlas, tiles, _ = compose_atlas(mat_a, mat_b, "hard", (0, 0, 0))
    seed = preview_seed("草地泥土", "草地", "泥土", "rounded")
    p1 = render_preview(tiles, 16, 16, seed, cells=8)
    p2 = render_preview(tiles, 16, 16, seed, cells=8)
    assert p1.shape == (7 * 16, 7 * 16, 4)   # (cells-1) × tile
    assert np.array_equal(p1, p2)            # 同种子可复现


def test_preview_seed_is_deterministic() -> None:
    assert preview_seed("n", "a", "b", "rounded") == preview_seed("n", "a", "b", "rounded")
    assert preview_seed("n", "a", "b", "rounded") != preview_seed("n", "a", "b", "hard")
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid.py -q`
Expected: FAIL（`render_preview` / `preview_seed` 未定义）

- [ ] **Step 3: 写最小实现（追加到 `src/pix/dual_grid.py`）**

```python
import hashlib


def preview_seed(name: str, material_a: str, material_b: str, style: str) -> int:
    """从参数确定性派生 32-bit 预览种子（同参数同预览，测试稳定）。"""
    raw = f"{name}\n{material_a}\n{material_b}\n{style}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


def render_preview(
    tiles: list[np.ndarray], w: int, h: int, seed: int, cells: int = 8
) -> np.ndarray:
    """随机 cells×cells 世界格 → (cells-1)×(cells-1) 显示瓦片，验证无缝拼接。"""
    rng = np.random.default_rng(int(seed))
    world = rng.integers(0, 2, size=(cells, cells))
    disp = max(1, cells - 1)
    out = np.zeros((disp * h, disp * w, 4), dtype=np.uint8)
    for i in range(disp):
        for j in range(disp):
            idx = (int(world[i, j]) * TL | int(world[i, j + 1]) * TR
                   | int(world[i + 1, j]) * BL | int(world[i + 1, j + 1]) * BR)
            out[i * h:(i + 1) * h, j * w:(j + 1) * w] = tiles[idx]
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/pix/dual_grid.py tests/test_dual_grid.py
git commit -m "feat(dual-grid): deterministic-seed applied-map preview"
```

---

## Task 4: Schema 字段（`asset_kind=dual_grid` + 输入字段）

**Files:**
- Modify: `src/pix_web/schemas.py:427-461`（`AssetParamsSchema`）
- Test: `tests/test_dual_grid_pipeline.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_dual_grid_pipeline.py
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
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid_pipeline.py -q`
Expected: FAIL（`dual_grid` 不在 Literal / 字段不存在）

- [ ] **Step 3: 写最小实现**

`src/pix_web/schemas.py` 的 `AssetParamsSchema`：
1. `asset_kind` Literal 追加 `"dual_grid"`。
2. 在 `no_preview` 后新增字段：

```python
    material_a: str = Field(default="", max_length=160)
    material_b: str = Field(default="", max_length=160)
    material_a_texture_kind: str = "auto"
    material_b_texture_kind: str = "auto"
    transition_style: Literal["rounded", "hard", "outline"] = "rounded"
```

3. `_normalize_subject_kind` 内：`dual_grid` 也归一 `subject_kind="tileable_pattern"`（追加一个 elif 分支，与 tile_texture 同处理）。

- [ ] **Step 4: 运行确认通过**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid_pipeline.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/pix_web/schemas.py tests/test_dual_grid_pipeline.py
git commit -m "feat(dual-grid): AssetParamsSchema dual_grid kind + material/transition fields"
```

---

## Task 5: 后端 pipeline（生成 A/B + 合成落盘 + 路由）

**Files:**
- Modify: `src/pix_web/pipeline_adapter.py`（抽 `_generate_tile_material`；加 `run_dual_grid_asset_job_pipeline`；`run_job_pipeline:610-614` 路由）
- Modify: `src/pix/asset.py`（`ASSET_KIND_LABELS` 加 `dual_grid`）
- Test: `tests/test_dual_grid_pipeline.py`

> **实现要点：** 把 `run_tile_asset_job_pipeline` 中「prompt 构造 → generate_image → perfect_pixel → 落到 (w,h)」抽成 `_generate_tile_material(asset_cfg, settings, *, name, extra_prompt, texture_kind, size, image_*, run_dir, tag) -> Path`，原 tile pipeline 改为调用它（保持行为不变，回归现有 tile 测试）。`run_dual_grid_asset_job_pipeline` 调它两次（A、B；透明模式跳过 B），把结果 `np.asarray(Image.open(p).convert("RGBA").resize((w,h), NEAREST))` 后交给 `compose_atlas` / `render_preview`，落盘 atlas/preview/materials/meta。透明模式 outline 缺省色 = 材质 A 最暗可见色（`mat_a` 里 alpha>0 的像素按亮度取最小；若 A 全透明则回退 `(32,32,32)`，避免空数组 `min()`）。

- [ ] **Step 1: 写失败测试（mock 生图）**

```python
# 追加到 tests/test_dual_grid_pipeline.py
import contextlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

import pix_web.pipeline_adapter as pa
from pix.config import AppConfig


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
```

> 注：本测试不依赖共享 helper —— job/settings 直接用 `SimpleNamespace`（仿 `tests/test_candidate_reprocess.py`），cfg 用 `AppConfig()`，生图与 `_local_stage_context` 均 monkeypatch。`tests/` 下无 `conftest.py`/共享 fixture，勿去找。若 mock 生图的纯色图经 perfect_pixel 后尺寸非 32×32，断言改读 `meta["asset"]["tile_size"]`（已如此）。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid_pipeline.py -q`
Expected: FAIL（`run_dual_grid_asset_job_pipeline` 未定义）

- [ ] **Step 3: 实现**

1. `src/pix/asset.py`：`ASSET_KIND_LABELS` 加 `"dual_grid": "dual-grid tileset"`。（dual_grid 生成材质时复用 `tile_texture` 的 prompt profile，运行期不会查 dual_grid 的 `ASSET_PROMPT_PROFILES`/`COMPATIBLE_SUBJECT_KINDS`，故**仅注册 label** 即可，无需在那两张表加项——与 spec §5.1 的差异是有意的。）
2. `pipeline_adapter.py`：抽 `_generate_tile_material(...)`（见上「实现要点」），原 `run_tile_asset_job_pipeline` 改调它。
3. 新增 `run_dual_grid_asset_job_pipeline(job, settings, cfg)`：解析 `material_a/b/transition_style/material_*_texture_kind`；生成 A（必）与 B（非透明时）；`compose_atlas` + `render_preview`；落盘 `dual_grid_atlas.png` / `dual_grid_preview.png` / `materials/material_a.png`(+`material_b.png`) / `meta.json`（含 `asset_kind/material_a/material_b/transition_style/transparent_mode/tile_size/atlas_size/convention/mapping/preview_seed/resolved_texture_kind_*`），返回 `PipelineResult`（`pixel_path`=atlas、`preview_path`=preview）。
4. `run_job_pipeline`：`asset_kind=="dual_grid"` → 新 pipeline。

```python
# run_job_pipeline 内：置于现有 `if job.job_type == "asset":` 块中、
# `asset = _asset_data(job)` 之后，替换原 tile_texture 单行判断（复用已取的 asset）：
        kind = str(asset.get("asset_kind") or "item_icon")
        if kind == "dual_grid":
            return run_dual_grid_asset_job_pipeline(job, settings, resolved_cfg)
        if kind == "tile_texture":
            return run_tile_asset_job_pipeline(job, settings, resolved_cfg)
        return run_asset_job_pipeline(job, settings, resolved_cfg)
```

- [ ] **Step 4: 运行确认通过（含现有 tile 回归）**

Run: `uv run --extra dev python -m pytest tests/test_dual_grid_pipeline.py tests/test_tile_texture_prompt_rules.py tests/test_candidate_reprocess.py -q`
Expected: PASS（新测试通过，且抽取 helper 未破坏既有 tile pipeline）

- [ ] **Step 5: 提交**

```bash
git add src/pix_web/pipeline_adapter.py src/pix/asset.py tests/test_dual_grid_pipeline.py
git commit -m "feat(dual-grid): backend pipeline generating A/B materials + atlas/preview/meta"
```

---

## Task 6: OutputResponse 暴露 atlas/preview 路径

**Files:**
- Modify: `src/pix_web/schemas.py`（`JobOutputResponse`，schemas.py:509，仿 `sprite_mosaic_path` computed_field）
- Test: `tests/test_dual_grid_pipeline.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_dual_grid_pipeline.py
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
```

> 注：`tests/` 无现成 `JobOutputResponse` 构造可复用（grep 0 处），故上面显式传全部 6 必填字段。

- [ ] **Step 2: 运行确认失败** → `dual_grid_atlas_path` 不存在
- [ ] **Step 3: 实现**：在 `JobOutputResponse`（schemas.py:509）上仿 `sprite_mosaic_path`/`_url` 加四个 computed_field：`dual_grid_atlas_path/url`、`dual_grid_preview_path/url`，从 `_outputs_meta` 读 `dual_grid_atlas`/`dual_grid_preview`，路径用 `_resolve_meta_relative_path`。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交**

```bash
git add src/pix_web/schemas.py tests/test_dual_grid_pipeline.py
git commit -m "feat(dual-grid): expose atlas/preview paths on OutputResponse"
```

---

## Task 7: 全套件回归

- [ ] **Step 1:** Run `uv run --extra dev python -m pytest -q`，Expected: 全绿（含既有 136 + 新增）。
- [ ] **Step 2:** 失败则定位修复，勿改测试迁就实现。

---

## Task 8: 文档 / 配置 / 语言 / 版本同步（CLAUDE.md 规则）

**Files:** `docs/dual-grid-rules.md`(新)、`README.md`、`config.example.toml`、`apps/web/src/locales/zh-CN.ts`+`en.ts`、`apps/web/src/pages/ApiPage.tsx`、`CHANGELOG.md`、`pyproject.toml`、`src/pix/__init__.py`

- [ ] **Step 1:** 新建 `docs/dual-grid-rules.md`：字段、4×4 约定、bitmask→cell 表、透明/过渡说明、应用预览含义。
- [ ] **Step 2:** README + ApiPage 加 `dual_grid` asset_kind 与字段示例（外部 API 文档）。
- [ ] **Step 3:** `config.example.toml` 如引入 `[asset]` dual_grid 默认（如 outline 颜色）则补；否则注明无新增配置。
- [ ] **Step 4:** locales 加 `dual_grid` 素材类型标签（zh-CN + en），保证 `JobParameterSnapshotDialog` 能展示。
- [ ] **Step 5:** `CHANGELOG.md` `[Unreleased] > Added` 加条目。
- [ ] **Step 6:** 版本 `1.88.2 → 1.89.0`（`pyproject.toml` + `src/pix/__init__.py`）。
- [ ] **Step 7:** 提交

```bash
git add -A
git commit -m "docs(dual-grid): rules doc, README/API, locales, changelog, bump 1.89.0"
```

---

## 完成判据

- [ ] `uv run --extra dev python -m pytest -q` 全绿。
- [ ] 核心无缝性测试 `test_seamless_shared_edges_match` 覆盖三种 style × 多尺寸通过。
- [ ] dual_grid 任务端到端（mock 生图）产出 4×4 图集 + 预览 + 含 mapping 的 meta。
- [ ] 既有 tile_texture / asset pipeline 回归不破。
- [ ] 文档/配置/语言/API/版本号按 CLAUDE.md 同步。
