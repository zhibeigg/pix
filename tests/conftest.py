"""pytest 根 fixtures。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """避免真实环境里的 .env / env var 影响测试。"""
    for key in ("PACKY_API_KEY", "PACKY_VL_API_KEY", "PACKY_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    # 禁用 .env 自动加载；config.load_config 默认会搜索，我们用环境变量明确阻断
    monkeypatch.setenv("PIX_DISABLE_DOTENV", "1")


@pytest.fixture
def tmp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """生成一张简单的几何图用于像素化测试。"""
    img = Image.new("RGB", (512, 512), (30, 90, 180))
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, 240, 240), fill=(240, 200, 80))
    draw.ellipse((260, 120, 480, 380), fill=(220, 60, 80))
    draw.polygon([(100, 300), (300, 480), (60, 480)], fill=(60, 170, 80))
    path = tmp_path / "sample.png"
    img.save(path)
    return path


@pytest.fixture
def fake_analysis_dict() -> dict:
    return {
        "description": "smoke analysis",
        "style": {
            "style_tags": ["geometric"],
            "recommended_preset": "auto",
            "target_color_count": 8,
            "suggested_dither": "ordered",
            "contrast_level": "high",
        },
        "palette": [
            {"hex": "#1E5AB4", "weight": 0.35, "role": "background"},
            {"hex": "#F0C850", "weight": 0.25, "role": "primary"},
            {"hex": "#DC3C50", "weight": 0.25, "role": "accent"},
            {"hex": "#3CAA50", "weight": 0.15, "role": "secondary"},
        ],
        "main_subjects": [
            {
                "label": "circle",
                "bbox_norm": {"x": 0.5, "y": 0.2, "w": 0.45, "h": 0.55},
                "importance": 0.9,
                "sharpness_hint": "sharp",
            }
        ],
        "semantic_regions": [
            {
                "label": "circle",
                "bbox_norm": {"x": 0.5, "y": 0.2, "w": 0.45, "h": 0.55},
                "palette_hint": ["#F04050", "#DC3C50"],
            }
        ],
    }
