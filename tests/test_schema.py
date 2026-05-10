"""Schema 校验。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pix.analysis.schema import (
    BBoxNorm,
    ColorSwatch,
    PixAnalysis,
    SemanticRegion,
    StyleAnalysis,
)


class TestColorSwatch:
    def test_normalizes_hex(self) -> None:
        s = ColorSwatch(hex="aa00ff", weight=0.5, role="primary")
        assert s.hex == "#AA00FF"

    def test_accepts_hash_prefix(self) -> None:
        s = ColorSwatch(hex="#1234AB", weight=0.1, role="accent")
        assert s.hex == "#1234AB"

    @pytest.mark.parametrize("bad", ["xyz", "#GGGGGG", "ff00", "ff00ff00"])
    def test_rejects_bad_hex(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(hex=bad, weight=0.1, role="primary")

    @pytest.mark.parametrize("weight", [-0.1, 1.5, 2.0])
    def test_rejects_out_of_range_weight(self, weight: float) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(hex="#000000", weight=weight, role="primary")

    def test_rejects_unknown_role(self) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(hex="#000000", weight=0.5, role="unknown")


class TestBBoxNorm:
    def test_ok(self) -> None:
        BBoxNorm(x=0.0, y=0.0, w=1.0, h=1.0)
        BBoxNorm(x=0.5, y=0.5, w=0.5, h=0.5)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"x": -0.1, "y": 0.0, "w": 0.5, "h": 0.5},
            {"x": 0.0, "y": 1.1, "w": 0.5, "h": 0.5},
            {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.5},  # w 必须 > 0
            {"x": 0.0, "y": 0.0, "w": 1.5, "h": 0.5},
        ],
    )
    def test_rejects(self, kwargs: dict) -> None:
        with pytest.raises(ValidationError):
            BBoxNorm(**kwargs)


class TestSemanticRegion:
    def test_normalizes_palette_hint(self) -> None:
        reg = SemanticRegion(
            label="sky",
            bbox_norm=BBoxNorm(x=0, y=0, w=1, h=0.5),
            palette_hint=["88ccee", "#1234ab"],
        )
        assert reg.palette_hint == ["#88CCEE", "#1234AB"]

    def test_rejects_bad_palette_hint(self) -> None:
        with pytest.raises(ValidationError):
            SemanticRegion(
                label="bad",
                bbox_norm=BBoxNorm(x=0, y=0, w=1, h=0.5),
                palette_hint=["not-a-color"],
            )


class TestStyleAnalysis:
    def test_defaults(self) -> None:
        s = StyleAnalysis()
        assert s.recommended_preset == "auto"
        assert s.target_color_count == 16
        assert s.suggested_dither == "floyd_steinberg"
        assert s.contrast_level == "mid"

    @pytest.mark.parametrize("n", [1, 0, 257, -1])
    def test_rejects_bad_color_count(self, n: int) -> None:
        with pytest.raises(ValidationError):
            StyleAnalysis(target_color_count=n)


class TestPixAnalysis:
    def test_accepts_minimum(self, fake_analysis_dict: dict) -> None:
        p = PixAnalysis.model_validate(fake_analysis_dict)
        assert p.description == "smoke analysis"
        assert len(p.palette) == 4
        assert p.main_subjects[0].label == "circle"
        assert p.semantic_regions[0].palette_hint[0].startswith("#")

    def test_defaults_when_optional_missing(self) -> None:
        p = PixAnalysis.model_validate(
            {
                "description": "x",
                "style": {},
                "palette": [],
            }
        )
        assert p.style.recommended_preset == "auto"
        assert p.main_subjects == []
        assert p.semantic_regions == []

    def test_json_roundtrip(self, fake_analysis_dict: dict) -> None:
        p = PixAnalysis.model_validate(fake_analysis_dict)
        raw = p.model_dump_json()
        p2 = PixAnalysis.model_validate_json(raw)
        assert p2.palette[0].hex == p.palette[0].hex
