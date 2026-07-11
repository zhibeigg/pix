from __future__ import annotations

import pytest

from pix.api.prompt_guard import local_prompt_guard


@pytest.mark.parametrize(
    "prompt",
    [
        "copy image",
        "copy the reference image exactly",
        "clone this picture directly",
        "replicate source artwork 1:1",
        "recreate the source image one-to-one",
        "make an exact copy",
    ],
)
def test_direct_reference_copy_english_phrases_are_rejected(prompt: str) -> None:
    result = local_prompt_guard(prompt)

    assert result.allowed is False
    assert "直接复刻参考图" in result.reason


@pytest.mark.parametrize(
    "prompt",
    [
        "copy the reference",
        "copycat image with a new composition",
        "replicate source visuals as an original icon",
        "recreate the scene with different characters",
        "make a direct composition study",
    ],
)
def test_direct_reference_copy_english_near_misses_are_allowed(prompt: str) -> None:
    assert local_prompt_guard(prompt).allowed is True


def test_direct_reference_copy_long_whitespace_near_miss_is_allowed() -> None:
    prompt = "copy" + (" " * 3000) + "reference"

    assert local_prompt_guard(prompt, max_chars=len(prompt) + 1).allowed is True
