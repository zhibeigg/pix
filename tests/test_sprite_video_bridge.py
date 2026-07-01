from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

from pix.config import AppConfig
from pix.sprite_video_bridge import (
    build_video_bridge_motion_prompt,
    _optimize_video_bridge_motion_prompt,
    _prepare_video_keyframes,
    is_waiting_state_due,
)
from pix_web.jobs import params_json_from_request, validate_job_request
from pix_web.prompt_preview import build_prompt_preview
from pix_web.schemas import JobCreateRequest, PixelizeParamsSchema, SpriteParamsSchema
from pix_web.worker import _video_bridge_state_from_params


def _video_cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.video_bridge.enabled = True
    cfg.video_bridge.api_key = "test-ark-key"
    return cfg


def test_sprite_params_defaults_to_mosaic() -> None:
    req = JobCreateRequest(job_type="sprite_sheet", prompt="火焰法师")

    assert req.sprite.mode == "mosaic"
    assert req.sprite.frame_count == req.sprite.rows * req.sprite.cols

    data = params_json_from_request(req)
    assert data["sprite"]["mode"] == "mosaic"


def test_video_bridge_validation_requires_enabled_and_key() -> None:
    req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="蓝色骑士",
        sprite=SpriteParamsSchema(mode="video_bridge", rows=1, cols=8, video_action_prompt="挥剑"),
        pixelize=PixelizeParamsSchema(output_size=(64, 64)),
    )

    with pytest.raises(HTTPException) as disabled:
        validate_job_request(req, AppConfig())
    assert disabled.value.status_code == 409
    assert "未启用" in str(disabled.value.detail)

    cfg = AppConfig()
    cfg.video_bridge.enabled = True
    with pytest.raises(HTTPException) as missing_key:
        validate_job_request(req, cfg)
    assert missing_key.value.status_code == 409
    assert "Ark API Key" in str(missing_key.value.detail)

    validate_job_request(req, _video_cfg())


def test_video_bridge_validation_allows_multirow_without_row_prompts() -> None:
    req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="蓝色骑士",
        sprite=SpriteParamsSchema(mode="video_bridge", rows=2, cols=4, video_action_prompt="翻滚后起身"),
        pixelize=PixelizeParamsSchema(output_size=(64, 64)),
    )

    validate_job_request(req, _video_cfg())


def test_video_bridge_rejects_single_frame() -> None:
    req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="蓝色骑士",
        sprite=SpriteParamsSchema(mode="video_bridge", rows=1, cols=1, video_action_prompt="挥剑"),
        pixelize=PixelizeParamsSchema(output_size=(64, 64)),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_job_request(req, _video_cfg())
    assert exc_info.value.status_code == 422
    assert "至少需要 2 帧" in str(exc_info.value.detail)


def test_video_bridge_prompt_preview_uses_keyframe_prompt() -> None:
    req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="蓝色斗篷骑士",
        sprite=SpriteParamsSchema(mode="video_bridge", rows=1, cols=8, video_action_prompt="挥剑释放蓝色剑气"),
        pixelize=PixelizeParamsSchema(output_size=(64, 64), colors=16),
    )

    preview = build_prompt_preview(req, _video_cfg())

    assert preview.mode == "sprite_video_bridge"
    assert "START pose" in preview.positive_prompt
    assert "END pose" in preview.positive_prompt
    assert "蓝色斗篷骑士" in preview.positive_prompt
    assert preview.warnings


def test_video_bridge_motion_prompt_keeps_subject_inside_frame_and_pixel_grid() -> None:
    prompt = build_video_bridge_motion_prompt("暗黑法师刺客", "向前突刺并释放烟雾粒子", frame_count=24)

    assert "sampled into 24 sprite frames" in prompt
    assert "smooth evenly spaced in-between poses" in prompt
    assert "small consistent changes between adjacent frames" in prompt
    assert "no duplicated frozen frames" in prompt
    assert "Every frame must be TRUE pixel art" in prompt
    assert "crisp square pixel blocks aligned to a stable pixel grid" in prompt
    assert "no anti-aliasing" in prompt
    assert "no motion blur" in prompt
    assert "no painterly smoothing" in prompt
    assert "fully inside the frame" in prompt
    assert "weapon" in prompt
    assert "smoke" in prompt
    assert "magic particles" in prompt
    assert "clear key-color padding on all four edges" in prompt
    assert "Never crop, clip, truncate" in prompt
    assert "scale the motion down" in prompt


def test_optimize_video_bridge_motion_prompt_uses_vl_motion_plan(tmp_path, monkeypatch) -> None:
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(first)
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(last)

    class FakeClient:
        def post_json(self, path, payload):
            assert path == "/v1/chat/completions"
            content = payload["messages"][0]["content"]
            assert content[0]["type"] == "text"
            assert "Target sampled sprite frames: 24" in content[0]["text"]
            assert "first_frame" in content[0]["text"]
            assert content[1]["type"] == "image_url"
            assert content[2]["type"] == "image_url"
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"optimized_motion_plan":"Use a controlled smoke-to-lunge arc with evenly spaced readable poses; keep every pixel block crisp and all dagger trails inside the canvas."}'
                        }
                    }
                ]
            }

    monkeypatch.setattr("pix.sprite_video_bridge.require_vl_api_key", lambda _cfg: "vl-key")
    monkeypatch.setattr("pix.sprite_video_bridge.make_packy_client", lambda _cfg, _api_key: FakeClient())

    base = build_video_bridge_motion_prompt("暗黑法师刺客", "突刺", frame_count=24)
    prompt, meta = _optimize_video_bridge_motion_prompt(
        AppConfig(),
        description="暗黑法师刺客",
        action_prompt="突刺",
        base_prompt=base,
        first_frame_path=first,
        last_frame_path=last,
        frame_count=24,
    )

    assert prompt.startswith(base)
    assert "Optimized motion plan" in prompt
    assert "controlled smoke-to-lunge arc" in prompt
    assert "every pixel block crisp" in prompt
    assert meta["used"] is True
    assert meta["mode"] == "model"


def test_optimize_video_bridge_motion_prompt_falls_back_without_vl_key(tmp_path, monkeypatch) -> None:
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(first)
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(last)

    def raise_missing_key(_cfg):
        raise RuntimeError("missing vl key")

    monkeypatch.setattr("pix.sprite_video_bridge.require_vl_api_key", raise_missing_key)
    base = build_video_bridge_motion_prompt("暗黑法师刺客", "突刺", frame_count=24)
    prompt, meta = _optimize_video_bridge_motion_prompt(
        AppConfig(),
        description="暗黑法师刺客",
        action_prompt="突刺",
        base_prompt=base,
        first_frame_path=first,
        last_frame_path=last,
        frame_count=24,
    )

    assert prompt == base
    assert meta["used"] is False
    assert meta["mode"] == "unavailable"
    assert "missing vl key" in meta["error"]


def test_waiting_state_due_parses_iso_time() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)

    assert is_waiting_state_due({"next_poll_at": (now - timedelta(seconds=1)).isoformat()}, now=now)
    assert not is_waiting_state_due({"next_poll_at": (now + timedelta(seconds=30)).isoformat()}, now=now)
    assert is_waiting_state_due({}, now=now)


def test_waiting_state_is_stored_under_sprite_params() -> None:
    state = {"kind": "video_bridge", "ark_task_id": "task-1"}

    assert _video_bridge_state_from_params({"sprite": {"video_bridge_state": state}}) == state
    assert _video_bridge_state_from_params({"video_bridge_state": state}) == state
    assert _video_bridge_state_from_params({"sprite": {}}) is None


def _non_key_bbox(path, key=(255, 0, 255)) -> tuple[int, int, int, int]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    pixels = image.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y] != key:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_prepare_video_keyframes_crops_and_normalizes_subject_bbox(tmp_path) -> None:
    key = (255, 0, 255, 255)
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    first_video = tmp_path / "first_video.png"
    last_video = tmp_path / "last_video.png"

    first_img = Image.new("RGBA", (320, 160), key)
    first_draw = ImageDraw.Draw(first_img)
    first_draw.rectangle([20, 80, 80, 140], fill=(20, 20, 20, 255))
    first_img.save(first)

    last_img = Image.new("RGBA", (320, 160), key)
    last_draw = ImageDraw.Draw(last_img)
    last_draw.rectangle([230, 55, 300, 140], fill=(20, 20, 20, 255))
    last_img.save(last)

    meta = _prepare_video_keyframes(
        first,
        last,
        first_video,
        last_video,
        (256, 256),
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=(255, 0, 255),
        key_tolerance=0,
        generated_preprocess_method="none",
    )

    first_bbox = _non_key_bbox(first_video)
    last_bbox = _non_key_bbox(last_video)
    first_center = (first_bbox[0] + first_bbox[2]) / 2
    last_center = (last_bbox[0] + last_bbox[2]) / 2
    assert abs(first_center - last_center) <= 2
    assert first_bbox[3] == last_bbox[3]
    assert meta["first"]["selection"]["subject_bbox"] == [20, 80, 81, 141]
    assert meta["last"]["selection"]["subject_bbox"] == [230, 55, 301, 141]
    assert meta["first"]["bbox"][0] < 20
    assert meta["last"]["bbox"][2] > 301
    assert meta["content_padding"] == 8
    assert meta["normalized_size"][0] >= meta["last"]["content_size"][0] + 16
    assert meta["normalized_size"][1] >= meta["last"]["content_size"][1] + 16


def test_prepare_video_keyframes_uses_subject_contour_and_safe_padding(tmp_path) -> None:
    key = (255, 0, 0, 255)
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    first_video = tmp_path / "first_video.png"
    last_video = tmp_path / "last_video.png"

    first_img = Image.new("RGBA", (160, 120), key)
    first_draw = ImageDraw.Draw(first_img)
    first_draw.rectangle([34, 45, 72, 105], fill=(18, 18, 28, 255))
    first_draw.rectangle([18, 72, 36, 92], fill=(30, 14, 42, 255))
    first_draw.rectangle([150, 8, 153, 11], fill=(75, 20, 255, 255))
    first_draw.rectangle([147, 108, 149, 110], fill=(75, 20, 255, 255))
    first_img.save(first)

    last_img = Image.new("RGBA", (160, 120), key)
    last_draw = ImageDraw.Draw(last_img)
    last_draw.rectangle([45, 55, 96, 105], fill=(18, 18, 28, 255))
    last_draw.rectangle([92, 60, 159, 66], fill=(210, 210, 220, 255))
    last_draw.rectangle([8, 8, 10, 10], fill=(75, 20, 255, 255))
    last_img.save(last)

    meta = _prepare_video_keyframes(
        first,
        last,
        first_video,
        last_video,
        (256, 256),
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=(255, 0, 0),
        key_tolerance=0,
        generated_preprocess_method="none",
    )

    assert meta["first"]["selection"]["raw_bbox"] == [18, 8, 154, 111]
    assert meta["first"]["selection"]["subject_bbox"] == [18, 45, 73, 106]
    assert meta["first"]["selection"]["dropped_component_count"] >= 1
    assert meta["last"]["selection"]["subject_bbox"] == [45, 55, 160, 106]

    first_bbox = _non_key_bbox(first_video, key=(255, 0, 0))
    last_bbox = _non_key_bbox(last_video, key=(255, 0, 0))
    assert first_bbox[0] > 0
    assert first_bbox[2] < 256
    assert last_bbox[0] > 0
    assert last_bbox[2] < 256
