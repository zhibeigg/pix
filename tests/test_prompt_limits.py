from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from pix.config import load_config
from pix_web.jobs import validate_job_request
from pix_web.schemas import JobCreateRequest


def _cfg():
    return load_config(
        config_file=Path("__missing_prompt_limit_test__.toml"),
        env_file=None,
        overrides={
            "asset": {
                "subject_max_chars": 3,
                "extra_prompt_max_chars": 5,
            },
            "sprite": {
                "subject_max_chars": 4,
                "row_prompt_max_chars": 3,
            },
        },
    )


def test_asset_extra_prompt_limit_uses_config() -> None:
    req = JobCreateRequest(
        job_type="asset",
        asset={"name": "axe", "extra_prompt": "abcdef", "asset_kind": "item_icon"},
        pixelize={"output_size": [32, 32]},
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_job_request(req, _cfg())

    assert exc_info.value.status_code == 422
    assert "额外风格描述最多支持 5 字" in str(exc_info.value.detail)


def test_dual_grid_material_limit_uses_asset_subject_config() -> None:
    req = JobCreateRequest(
        job_type="asset",
        asset={
            "name": "mix",
            "asset_kind": "dual_grid",
            "material_a": "stone",
            "material_b": "mud",
        },
        pixelize={"output_size": [32, 32]},
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_job_request(req, _cfg())

    assert exc_info.value.status_code == 422
    assert "材质 A 描述最多支持 3 字" in str(exc_info.value.detail)


def test_sprite_subject_and_row_prompt_limits_use_config() -> None:
    subject_req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="hero!",
        sprite={"rows": 1, "cols": 2, "row_prompts": []},
        pixelize={"output_size": [64, 64]},
    )
    with pytest.raises(HTTPException) as subject_exc:
        validate_job_request(subject_req, _cfg())
    assert "序列帧主体描述最多支持 4 字" in str(subject_exc.value.detail)

    row_req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="hero",
        sprite={"rows": 2, "cols": 2, "row_prompts": ["walk", "run"]},
        pixelize={"output_size": [64, 64]},
    )
    with pytest.raises(HTTPException) as row_exc:
        validate_job_request(row_req, _cfg())
    assert "第 1 行动作描述最多支持 3 字" in str(row_exc.value.detail)
