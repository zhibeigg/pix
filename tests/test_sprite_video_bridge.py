from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

from pix.api.ark_video import ArkVideoClient, ArkVideoError
from pix.config import AppConfig
from pix.net_guard import UnsafeDownloadURLError
from pix.pixelize.core import PixelizeParams
from pix.pixelize.perfect_pixel import GeneratedPreprocessResult
from pix.sprite_video_bridge import (
    SpriteVideoBridgeInput,
    VideoBridgeWaiting,
    build_video_bridge_motion_prompt,
    derive_video_bridge_duration_seconds,
    _optimize_video_bridge_motion_prompt,
    _prepare_video_keyframes,
    _poll_video_task,
    _process_frames,
    _split_keyframes,
    _start_video_task,
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


def test_ark_video_client_create_task_uses_official_first_last_frame_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeHttp:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def post_json(self, path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"id": "cgt-test-1"}

    monkeypatch.setattr("pix.api.ark_video.ProviderHttpClient", FakeHttp)

    result = ArkVideoClient(_video_cfg()).create_task(
        prompt="固定机位，像素骑士挥剑。",
        first_frame_data_url="data:image/png;base64,first",
        last_frame_data_url="data:image/png;base64,last",
        model="doubao-seedance-2-0-260128",
        resolution="480p",
        ratio="1:1",
        duration=4,
        generate_audio=False,
        watermark=False,
    )

    assert result.id == "cgt-test-1"
    assert captured["path"] == "/contents/generations/tasks"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "doubao-seedance-2-0-260128"
    assert payload["duration"] == 4
    assert payload["content"][0] == {"type": "text", "text": "固定机位，像素骑士挥剑。"}
    assert payload["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,first"},
        "role": "first_frame",
    }
    assert payload["content"][2] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,last"},
        "role": "last_frame",
    }


def test_ark_video_client_get_task_reads_content_video_url(monkeypatch) -> None:
    class FakeHttp:
        def __init__(self, **_kwargs):
            pass

        def get_json(self, path):
            assert path == "/contents/generations/tasks/cgt-test-1"
            return {
                "id": "cgt-test-1",
                "status": "succeeded",
                "content": {"video_url": "https://example.com/video.mp4"},
                "duration": 4,
                "framespersecond": 24,
            }

    monkeypatch.setattr("pix.api.ark_video.ProviderHttpClient", FakeHttp)

    task = ArkVideoClient(_video_cfg()).get_task("cgt-test-1")

    assert task.status == "succeeded"
    assert task.video_url == "https://example.com/video.mp4"
    assert task.duration == 4
    assert task.framespersecond == 24


def test_ark_video_client_download_video_preserves_retryable_safe_get_error(tmp_path, monkeypatch) -> None:
    def fake_safe_get_with_redirects(*_args, **_kwargs):
        exc = UnsafeDownloadURLError("temporary upstream DNS failure")
        exc.retryable = True
        raise exc

    monkeypatch.setattr("pix.api.ark_video.safe_get_with_redirects", fake_safe_get_with_redirects)

    with pytest.raises(ArkVideoError) as exc_info:
        ArkVideoClient(_video_cfg()).download_video("https://example.com/video.mp4", tmp_path / "video.mp4")

    assert exc_info.value.category == "network"
    assert exc_info.value.retryable is True



def test_sprite_params_defaults_to_mosaic() -> None:
    req = JobCreateRequest(job_type="sprite_sheet", prompt="火焰法师")

    assert req.sprite.mode == "mosaic"
    assert req.sprite.frame_count == req.sprite.rows * req.sprite.cols
    assert req.sprite.video_return_to_first_frame is False
    assert req.sprite.video_model == "doubao-seedance-2-0-260128"
    data = params_json_from_request(req)
    assert data["sprite"]["mode"] == "mosaic"
    assert data["sprite"]["video_return_to_first_frame"] is False
    assert data["sprite"]["video_model"] == "doubao-seedance-2-0-260128"


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
    assert "Target extracted sprite frame size is 64x64" in preview.positive_prompt
    assert "Use no more than 16 visible foreground/subject colors" in preview.positive_prompt
    assert "Denoise discipline" in preview.positive_prompt
    assert preview.warnings


def test_video_bridge_return_to_first_frame_is_saved_and_previewed() -> None:
    req = JobCreateRequest(
        job_type="sprite_sheet",
        prompt="蓝色斗篷骑士",
        sprite=SpriteParamsSchema(
            mode="video_bridge",
            rows=1,
            cols=8,
            video_action_prompt="挥剑释放蓝色剑气",
            video_return_to_first_frame=True,
        ),
        pixelize=PixelizeParamsSchema(output_size=(64, 64), colors=16),
    )

    data = params_json_from_request(req)
    preview = build_prompt_preview(req, _video_cfg())

    assert data["sprite"]["video_return_to_first_frame"] is True
    assert any("回到首帧" in warning for warning in preview.warnings)


def test_video_bridge_motion_prompt_keeps_subject_inside_frame_and_pixel_grid() -> None:
    prompt = build_video_bridge_motion_prompt("暗黑法师刺客", "向前突刺并释放烟雾粒子", frame_count=24)

    assert "sampled into 24 sprite frames" in prompt
    assert "smooth evenly spaced in-between poses" in prompt
    assert "small consistent changes between adjacent frames" in prompt
    assert "no duplicated frozen frames" in prompt
    assert "Every frame must be TRUE pixel art" in prompt
    assert "crisp square pixel blocks aligned to a stable pixel grid" in prompt
    assert "axis-aligned horizontal/vertical square tiles" in prompt
    assert "never rotate, tilt, shear, skew, diamond-turn, or slant" in prompt
    assert "not by rotating chunks of pixels" in prompt
    assert "no anti-aliasing" in prompt
    assert "no motion blur" in prompt
    assert "no painterly smoothing" in prompt
    assert "fully inside the frame" in prompt
    assert "weapon" in prompt
    assert "smoke" in prompt
    assert "magic particles" in prompt
    assert "clear key-color padding on all four edges" in prompt
    assert "only the flat key-color background may touch the canvas edges" in prompt
    assert "every non-background / non-key-color pixel is foreground" in prompt
    assert "stray particles" in prompt
    assert "weapon tips" in prompt
    assert "Never crop, clip, truncate" in prompt
    assert "foreground pixel touch or cross the frame boundary" in prompt
    assert "scale the motion down" in prompt
    assert "Seedance prompt structure" in prompt
    assert "fixed orthographic game-sprite camera" in prompt
    assert "no subtitles" in prompt
    assert "do not generate Logo" in prompt
    assert "do not generate watermark" in prompt
    assert "duplicate subject" in prompt
    assert "Loop-return requirement" not in prompt


def test_video_bridge_motion_prompt_can_return_to_first_frame() -> None:
    prompt = build_video_bridge_motion_prompt(
        "暗黑法师刺客",
        "突刺后收招",
        frame_count=24,
        return_to_first_frame=True,
    )

    assert "Loop-return requirement" in prompt
    assert "first and final video frames must both match the provided first_frame image" in prompt
    assert "last_frame image is the peak/action target pose" in prompt
    assert "reaches the provided last_frame pose" in prompt
    assert "smooth return motion back to the provided first_frame pose" in prompt
    assert "final sampled frame must match first_frame again" in prompt
    assert "no sudden snap back" in prompt


def test_video_bridge_motion_prompt_includes_locked_timing() -> None:
    prompt = build_video_bridge_motion_prompt(
        "灵山野猪妖幼崽",
        "待机呼吸",
        frame_count=8,
        frame_duration_ms=125,
        video_duration_seconds=1,
    )

    assert "sampled into 8 sprite frames" in prompt
    assert "source video duration is locked to 1 second(s)" in prompt
    assert "8 sprite frames × 125 ms per frame" in prompt
    assert "1000 ms total animation time" in prompt


def test_derive_video_bridge_duration_seconds_snaps_to_allowed_tiers() -> None:
    # 默认档位对齐 Seedance 2.0 价格计算器：4–15 秒，推导秒数向上吸附到最近合法档位。
    assert derive_video_bridge_duration_seconds(8, 125) == 4  # 1s -> 4s
    assert derive_video_bridge_duration_seconds(9, 125) == 4  # 2s -> 4s
    assert derive_video_bridge_duration_seconds(40, 125) == 5  # 5s -> 5s
    assert derive_video_bridge_duration_seconds(56, 125) == 7  # 7s -> 7s
    assert derive_video_bridge_duration_seconds(200, 125) == 15  # 25s -> clamp 15s
    # 自定义档位可覆盖默认值。
    assert derive_video_bridge_duration_seconds(8, 125, (2, 3, 10)) == 2
    assert derive_video_bridge_duration_seconds(80, 125, (2, 3, 10)) == 10


def test_start_video_task_uses_sprite_timing_for_ark_duration(tmp_path, monkeypatch) -> None:
    cfg = _video_cfg()
    cfg.video_bridge.duration = 5
    captured: dict[str, object] = {}

    def fake_generate_image(_cfg, _prompt, dest_path, **_kwargs):
        image = Image.new("RGBA", (160, 80), (255, 0, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle([18, 30, 48, 62], fill=(30, 60, 90, 255))
        draw.rectangle([108, 26, 140, 62], fill=(30, 60, 90, 255))
        image.save(dest_path)
        return dest_path

    def fake_optimize(_cfg, **kwargs):
        return kwargs["base_prompt"], {"used": False, "mode": "test"}

    class FakeArkVideoClient:
        def __init__(self, _cfg):
            pass

        def create_task(self, **kwargs):
            captured.update(kwargs)
            return type("Created", (), {"id": "ark-task-1", "raw": {"id": "ark-task-1"}})()

    monkeypatch.setattr("pix.sprite_video_bridge.generate_image", fake_generate_image)
    monkeypatch.setattr("pix.sprite_video_bridge._optimize_video_bridge_motion_prompt", fake_optimize)
    monkeypatch.setattr("pix.sprite_video_bridge.ArkVideoClient", FakeArkVideoClient)

    inputs = SpriteVideoBridgeInput(
        prompt="灵山野猪妖幼崽",
        rows=1,
        cols=8,
        row_prompts=["待机呼吸"],
        video_model="doubao-seedance-2-0-fast-260128",
        pixelize_params=PixelizeParams(output_size=(32, 32), colors=8, generated_preprocess_method="none"),
        fps=8,
        duration_ms=125,
    )

    with pytest.raises(VideoBridgeWaiting) as exc_info:
        _start_video_task(
            cfg,
            inputs,
            run_dir=tmp_path,
            description="灵山野猪妖幼崽",
            action_prompt="待机呼吸",
            key_color="#FF00FF",
            notify=lambda _step, _payload: None,
        )

    assert captured["duration"] == 4
    assert captured["model"] == "doubao-seedance-2-0-fast-260128"
    assert "source video duration is locked to 4 second(s)" in str(captured["prompt"])
    assert exc_info.value.state["timing"] == {
        "source": "sprite_timing",
        "frame_count": 8,
        "frame_duration_ms": 125,
        "total_duration_ms": 1000,
        "raw_duration_seconds": 1,
        "ark_duration_seconds": 4,
    }
    assert exc_info.value.state["duration"] == 4
    assert exc_info.value.state["configured_duration"] == 5
    assert exc_info.value.state["duration_source"] == "sprite_timing"
    assert exc_info.value.state["model"] == "doubao-seedance-2-0-fast-260128"
    assert exc_info.value.state["video_model"] == "doubao-seedance-2-0-fast-260128"


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
            assert "only the flat key-color background is allowed to touch canvas edges" in content[0]["text"]
            assert "every non-background / non-key-color pixel is foreground" in content[0]["text"]
            assert "every visible pixel block must stay axis-aligned" in content[0]["text"]
            assert "never rotate, tilt, shear, skew, diamond-turn, or slant pixel blocks" in content[0]["text"]
            assert "weapon tips" in content[0]["text"]
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

    cfg = AppConfig()
    cfg.vision.model = "gpt-4o"
    base = build_video_bridge_motion_prompt("暗黑法师刺客", "突刺", frame_count=24)
    prompt, meta = _optimize_video_bridge_motion_prompt(
        cfg,
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
    assert meta["endpoint"] == "/v1/chat/completions"


def test_optimize_video_bridge_motion_prompt_routes_claude_to_anthropic_messages(tmp_path, monkeypatch) -> None:
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(first)
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(last)

    calls: list[str] = []

    class FakeClient:
        def post_json(self, path, payload):
            calls.append(path)
            assert path == "/v1/messages"
            assert payload["model"] == "claude-sonnet-5"
            content = payload["messages"][0]["content"]
            assert content[0]["type"] == "text"
            assert "every non-background / non-key-color pixel is foreground" in content[0]["text"]
            assert "every visible pixel block must stay axis-aligned" in content[0]["text"]
            assert "never rotate, tilt, shear, skew, diamond-turn, or slant pixel blocks" in content[0]["text"]
            assert content[1]["type"] == "image"
            assert content[1]["source"]["type"] == "base64"
            assert content[1]["source"]["media_type"] == "image/png"
            assert content[2]["type"] == "image"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": '{"optimized_motion_plan":"Use 24 readable smoke transformation poses; keep all foreground pixels at least 10 percent away from all frame edges."}',
                    }
                ]
            }

    monkeypatch.setattr("pix.sprite_video_bridge.require_vl_api_key", lambda _cfg: "vl-key")
    monkeypatch.setattr("pix.sprite_video_bridge.make_packy_client", lambda _cfg, _api_key: FakeClient())

    cfg = AppConfig()
    cfg.vision.model = "claude-sonnet-5"
    base = build_video_bridge_motion_prompt("暗黑法师刺客", "突刺", frame_count=24)
    prompt, meta = _optimize_video_bridge_motion_prompt(
        cfg,
        description="暗黑法师刺客",
        action_prompt="突刺",
        base_prompt=base,
        first_frame_path=first,
        last_frame_path=last,
        frame_count=24,
    )

    assert calls == ["/v1/messages"]
    assert prompt.startswith(base)
    assert "24 readable smoke transformation poses" in prompt
    assert meta["used"] is True
    assert meta["mode"] == "model"
    assert meta["endpoint"] == "/v1/messages"


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


def test_poll_video_task_keeps_waiting_on_retryable_ark_poll_error(tmp_path, monkeypatch) -> None:
    cfg = _video_cfg()
    cfg.video_bridge.poll_interval_seconds = 1

    class FakeArkVideoClient:
        def __init__(self, _cfg):
            pass

        def get_task(self, _task_id):
            raise ArkVideoError("temporary gateway timeout", category="timeout", provider_id="ark_video")

    monkeypatch.setattr("pix.sprite_video_bridge.ArkVideoClient", FakeArkVideoClient)
    state = {"kind": "video_bridge", "ark_task_id": "cgt-test-1", "created_at": datetime.now(timezone.utc).isoformat()}

    with pytest.raises(VideoBridgeWaiting) as exc_info:
        _poll_video_task(cfg, state, tmp_path)

    waiting_state = exc_info.value.state
    assert waiting_state["stage"] == "ark_poll_transient_error"
    assert waiting_state["last_transient_error"]["category"] == "timeout"
    assert waiting_state["transient_error_count"] == 1
    assert waiting_state["next_poll_at"]
    assert (tmp_path / "video_bridge_state.json").exists()


def test_poll_video_task_keeps_waiting_on_retryable_download_error(tmp_path, monkeypatch) -> None:
    cfg = _video_cfg()
    cfg.video_bridge.poll_interval_seconds = 1

    class FakeTask:
        status = "succeeded"
        raw = {"id": "cgt-test-1", "status": "succeeded"}
        error = None
        video_url = "https://example.com/video.mp4"

    class FakeArkVideoClient:
        def __init__(self, _cfg):
            pass

        def get_task(self, _task_id):
            return FakeTask()

        def download_video(self, _video_url, _dest):
            raise ArkVideoError("temporary read timeout", category="timeout", provider_id="ark_video")

    monkeypatch.setattr("pix.sprite_video_bridge.ArkVideoClient", FakeArkVideoClient)
    state = {"kind": "video_bridge", "ark_task_id": "cgt-test-1", "created_at": datetime.now(timezone.utc).isoformat()}

    with pytest.raises(VideoBridgeWaiting) as exc_info:
        _poll_video_task(cfg, state, tmp_path)

    waiting_state = exc_info.value.state
    assert waiting_state["stage"] == "ark_download_transient_error"
    assert waiting_state["last_status"] == "succeeded"
    assert waiting_state["last_transient_error"]["category"] == "timeout"
    assert waiting_state["transient_error_count"] == 1
    assert waiting_state["next_poll_at"]


def test_poll_video_task_fails_on_terminal_ark_status(tmp_path, monkeypatch) -> None:
    class FakeTask:
        status = "failed"
        raw = {"id": "cgt-test-1", "status": "failed"}
        error = {"code": "InvalidParameter", "message": "bad duration"}
        video_url = None

    class FakeArkVideoClient:
        def __init__(self, _cfg):
            pass

        def get_task(self, _task_id):
            return FakeTask()

    monkeypatch.setattr("pix.sprite_video_bridge.ArkVideoClient", FakeArkVideoClient)
    state = {"kind": "video_bridge", "ark_task_id": "cgt-test-1", "created_at": datetime.now(timezone.utc).isoformat()}

    with pytest.raises(RuntimeError) as exc_info:
        _poll_video_task(_video_cfg(), state, tmp_path)

    assert "Ark 视频任务失败：failed InvalidParameter bad duration" in str(exc_info.value)


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


def test_split_keyframes_uses_foreground_gutter_instead_of_midpoint(tmp_path) -> None:
    key = (0, 255, 255, 255)
    pair = tmp_path / "pair.png"
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    image = Image.new("RGBA", (200, 100), key)
    draw = ImageDraw.Draw(image)
    # 左姿势完整落在左半区，但右姿势的后腿/披风伸过几何中线 x=100。
    draw.rectangle([20, 20, 80, 80], fill=(10, 10, 10, 255))
    draw.rectangle([90, 70, 130, 90], fill=(30, 30, 30, 255))
    draw.rectangle([130, 30, 180, 80], fill=(40, 40, 40, 255))
    image.save(pair)

    meta = _split_keyframes(pair, first, last, key_rgb=key[:3], key_tolerance=16)

    assert meta["method"] == "axis_transition_gutter"
    assert meta["split_x"] < 100
    assert meta["split_x"] > 80
    first_bbox = _non_key_bbox(first, key=key[:3])
    last_bbox = _non_key_bbox(last, key=key[:3])
    assert first_bbox == (20, 20, 81, 81)
    # 若按中线硬切，尾帧 bbox 宽度只有 81；自适应 gutter 应保留 x=90..180 的完整伸出部分。
    assert last_bbox[2] - last_bbox[0] >= 91
    assert last_bbox[0] <= 5


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
    assert meta["content_padding"] == 16
    assert meta["normalized_size"][0] >= meta["last"]["content_size"][0] + 32
    assert meta["normalized_size"][1] >= meta["last"]["content_size"][1] + 32


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


def _alpha_bbox(path) -> tuple[int, int, int, int]:
    with Image.open(path) as opened:
        alpha = opened.convert("RGBA").getchannel("A")
    pixels = alpha.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(alpha.height):
        for x in range(alpha.width):
            if pixels[x, y] > 8:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_process_frames_detects_mode_grid_then_reprocesses_all_frames(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 255, 255)
    raw_paths = []
    for index, size in enumerate([(64, 64), (65, 64), (64, 65)], start=1):
        path = raw_dir / f"frame_{index:03d}.png"
        image = Image.new("RGBA", size, key)
        draw = ImageDraw.Draw(image)
        draw.rectangle([size[0] // 3, size[1] // 3, size[0] // 3 + 12, size[1] // 3 + 12], fill=(20, 20, 30, 255))
        image.save(path)
        raw_paths.append(path)

    calls: list[tuple[str, tuple[int, int], tuple[int, int] | None]] = []

    def fake_preprocess(image, *, method, target_size, grid_size=None, **_kwargs):
        if grid_size is None:
            detected = (17, 16) if image.size[0] == 65 else (16, 16)
            calls.append(("detect", image.size, None))
        else:
            detected = tuple(grid_size)
            calls.append(("fixed", image.size, tuple(grid_size)))
        out = Image.new("RGBA", detected, key)
        out_draw = ImageDraw.Draw(out)
        out_draw.rectangle([4, 4, min(detected[0] - 1, 10), min(detected[1] - 1, 10)], fill=(20, 20, 30, 255))
        return GeneratedPreprocessResult(
            image=out,
            meta={
                "method": method,
                "applied": True,
                "target_size": list(target_size),
                "refined_size": list(detected),
                "output_size": list(detected),
                "fixed_grid_size": list(grid_size) if grid_size else None,
            },
        )

    monkeypatch.setattr("pix.sprite_video_bridge.preprocess_generated_image", fake_preprocess)
    cfg = AppConfig()
    cfg.sprite.shared_palette = False

    _final_paths, _bboxes, _effective_size, _palette, process_meta = _process_frames(
        cfg,
        raw_paths,
        final_dir,
        target_size=(8, 8),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=key[:3],
        key_tolerance=0,
        max_colors=4,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="perfect_pixel",
        palette_mode="kmeans",
        run_dir=tmp_path,
    )

    grid_meta = process_meta["perfect_pixel_sequence_grid"]
    assert grid_meta["strategy"] == "detect_all_frames_take_mode_then_reprocess_with_fixed_grid"
    assert grid_meta["mode_grid_size"] == [16, 16]
    assert [item[0] for item in calls].count("detect") == 3
    assert [item[0] for item in calls].count("fixed") == 3
    assert all(call[2] == (16, 16) for call in calls if call[0] == "fixed")
    assert process_meta["common_preprocess_size"] == [16, 16]
    assert process_meta["final_canvas_rule"] == "next_power_of_two_square_transparent_padding"
    assert process_meta["preserve_perfect_pixel_detected_size"] is True
    assert [frame["normalized_size"] for frame in process_meta["frames"]] == [[16, 16]] * 3
    assert [frame["preprocess"]["fixed_grid_size"] for frame in process_meta["frames"]] == [[16, 16]] * 3



def test_process_frames_pads_detected_size_to_power_of_two_square(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 255, 255)
    raw_paths = []
    for index in range(2):
        path = raw_dir / f"frame_{index + 1:03d}.png"
        Image.new("RGBA", (512, 512), key).save(path)
        raw_paths.append(path)

    def fake_preprocess(image, *, method, target_size, grid_size=None, **_kwargs):
        detected = tuple(grid_size) if grid_size else (106, 106)
        out = Image.new("RGBA", detected, key)
        draw = ImageDraw.Draw(out)
        draw.rectangle([20, 20, 80, 80], fill=(20, 20, 30, 255))
        return GeneratedPreprocessResult(
            image=out,
            meta={
                "method": method,
                "applied": True,
                "target_size": list(target_size),
                "refined_size": list(detected),
                "output_size": list(detected),
                "fixed_grid_size": list(grid_size) if grid_size else None,
            },
        )

    monkeypatch.setattr("pix.sprite_video_bridge.preprocess_generated_image", fake_preprocess)
    cfg = AppConfig()
    cfg.sprite.shared_palette = False

    final_paths, _bboxes, effective_size, _palette, process_meta = _process_frames(
        cfg,
        raw_paths,
        final_dir,
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=key[:3],
        key_tolerance=0,
        max_colors=4,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="perfect_pixel",
        palette_mode="kmeans",
        run_dir=tmp_path,
    )

    assert effective_size == (128, 128)
    assert process_meta["common_preprocess_size"] == [106, 106]
    assert process_meta["required_frame_size"] == [106, 106]
    assert process_meta["final_canvas_rule"] == "next_power_of_two_square_transparent_padding"
    assert process_meta["perfect_pixel_sequence_grid"]["mode_grid_size"] == [106, 106]
    with Image.open(final_paths[0]) as opened:
        assert opened.size == (128, 128)
        assert opened.getpixel((0, 0))[3] == 0


def test_process_frames_keeps_foreground_away_from_output_edges(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 0, 255)
    raw_paths = []
    for index in range(2):
        path = raw_dir / f"frame_{index + 1:03d}.png"
        image = Image.new("RGBA", (64, 64), key)
        draw = ImageDraw.Draw(image)
        if index == 0:
            draw.rectangle([0, 18, 30, 63], fill=(20, 20, 30, 255))
        else:
            draw.rectangle([34, 0, 63, 44], fill=(20, 20, 30, 255))
        image.save(path)
        raw_paths.append(path)

    cfg = AppConfig()
    cfg.sprite.shared_palette = False
    final_paths, _bboxes, effective_size, _palette, process_meta = _process_frames(
        cfg,
        raw_paths,
        final_dir,
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=(255, 0, 0),
        key_tolerance=0,
        max_colors=16,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="none",
        palette_mode="kmeans",
        run_dir=tmp_path,
    )

    assert effective_size == (128, 128)
    assert process_meta["final_canvas_rule"] == "next_power_of_two_square_transparent_padding"
    assert process_meta["frame_padding"] == 5
    for path in final_paths:
        bbox = _alpha_bbox(path)
        assert bbox[0] >= 5
        assert bbox[1] >= 5
        assert effective_size[0] - bbox[2] >= 5
        assert effective_size[1] - bbox[3] >= 5


def _visible_colors(path) -> set[tuple[int, int, int]]:
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
    pixels = rgba.load()
    colors: set[tuple[int, int, int]] = set()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a > 8:
                colors.add((r, g, b))
    return colors


def test_process_frames_denoises_and_limits_colors_when_shared_palette_disabled(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 255, 255)
    raw_path = raw_dir / "frame_001.png"
    image = Image.new("RGBA", (64, 64), key)
    draw = ImageDraw.Draw(image)
    # 主体内故意放入多种颜色，验证即使 shared_palette=false 也会按 max_colors 限色。
    palette = [
        (10, 10, 20, 255),
        (30, 40, 90, 255),
        (70, 20, 120, 255),
        (120, 50, 40, 255),
        (180, 90, 30, 255),
        (220, 160, 60, 255),
    ]
    for offset, color in enumerate(palette):
        draw.rectangle([14 + offset * 4, 18, 17 + offset * 4, 42], fill=color)
    noise_color = (0, 255, 0, 255)
    draw.point((58, 6), fill=noise_color)
    image.save(raw_path)

    cfg = AppConfig()
    cfg.sprite.shared_palette = False
    # 显式选择 kmeans 逃生阀，验证旧的本地限色路径仍可用。
    final_paths, _bboxes, _effective_size, shared_palette, process_meta = _process_frames(
        cfg,
        [raw_path],
        final_dir,
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=key[:3],
        key_tolerance=0,
        max_colors=4,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="none",
        palette_mode="kmeans",
        run_dir=tmp_path,
    )

    colors = _visible_colors(final_paths[0])
    assert process_meta["denoise"]["dropped_component_count"] >= 1
    assert process_meta["palette_mode"] == "kmeans_per_frame"
    assert process_meta["requested_palette_mode"] == "kmeans"
    assert process_meta["frame_palettes"]
    assert shared_palette == []
    assert len(colors) <= 4
    assert noise_color[:3] not in colors


def _draw_multicolor_subject(path, key=(255, 0, 255, 255)) -> None:
    image = Image.new("RGBA", (64, 64), key)
    draw = ImageDraw.Draw(image)
    palette = [
        (10, 10, 20, 255),
        (30, 40, 90, 255),
        (70, 20, 120, 255),
        (120, 50, 40, 255),
        (180, 90, 30, 255),
        (220, 160, 60, 255),
    ]
    for offset, color in enumerate(palette):
        draw.rectangle([14 + offset * 4, 18, 17 + offset * 4, 42], fill=color)
    image.save(path)


def test_process_frames_defaults_to_vl_ramp_palette(tmp_path, monkeypatch) -> None:
    from pix.pixelize.ramp import ramp_from_dict

    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 255, 255)
    raw_paths = []
    for index in range(2):
        path = raw_dir / f"frame_{index + 1:03d}.png"
        _draw_multicolor_subject(path, key=key)
        raw_paths.append(path)

    ramp_colors = ["#101014", "#3A5AA0", "#C8B43C"]
    vl_ramp = ramp_from_dict(
        {
            "ramps": [
                {
                    "name": "main",
                    "hue": "main",
                    "steps": [
                        {"hex": ramp_colors[0], "role": "shadow"},
                        {"hex": ramp_colors[1], "role": "mid"},
                        {"hex": ramp_colors[2], "role": "highlight"},
                    ],
                }
            ]
        }
    )

    captured: dict[str, object] = {}

    def fake_ramp_from_vl(_cfg, image_path, **kwargs):
        captured["image_path"] = str(image_path)
        captured["max_colors"] = kwargs.get("max_colors")
        captured["model"] = kwargs.get("model")
        return vl_ramp

    monkeypatch.setattr("pix.sprite_video_bridge.require_vl_api_key", lambda _cfg: "vl-key")
    monkeypatch.setattr("pix.sprite_video_bridge.ramp_from_vl", fake_ramp_from_vl)

    cfg = AppConfig()
    cfg.sprite.shared_palette = True

    final_paths, _bboxes, _effective_size, shared_palette, process_meta = _process_frames(
        cfg,
        raw_paths,
        final_dir,
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=key[:3],
        key_tolerance=0,
        max_colors=8,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="none",
        palette_mode="auto",
        vl_model="gpt-4o",
        description="多彩主体",
        run_dir=tmp_path,
    )

    # VL 只应调用一次（共享色阶）
    assert process_meta["ramp"]["source"] == "vl"
    assert process_meta["ramp"]["shared_vl_call_count"] == 1
    assert process_meta["palette_mode"] == "vl_ramp_shared"
    assert captured["model"] == "gpt-4o"
    # 每帧颜色应落在 VL ramp 色板内
    allowed = {(16, 16, 20), (58, 90, 160), (200, 180, 60)}
    for path in final_paths:
        for color in _visible_colors(path):
            assert color in allowed
    assert set(shared_palette)  # 返回扁平色板


def test_process_frames_falls_back_to_local_ramp_when_vl_fails(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 255, 255)
    raw_paths = []
    for index in range(2):
        path = raw_dir / f"frame_{index + 1:03d}.png"
        _draw_multicolor_subject(path, key=key)
        raw_paths.append(path)

    def boom(_cfg, _image_path, **_kwargs):
        raise RuntimeError("vl exploded")

    local_calls: list[int] = []
    real_build_local_ramp = None
    from pix.pixelize import ramp as ramp_module

    real_build_local_ramp = ramp_module.build_local_ramp

    def tracking_local_ramp(image, **kwargs):
        local_calls.append(1)
        return real_build_local_ramp(image, **kwargs)

    monkeypatch.setattr("pix.sprite_video_bridge.require_vl_api_key", lambda _cfg: "vl-key")
    monkeypatch.setattr("pix.sprite_video_bridge.ramp_from_vl", boom)
    monkeypatch.setattr("pix.sprite_video_bridge.build_local_ramp", tracking_local_ramp)

    cfg = AppConfig()
    cfg.sprite.shared_palette = True

    final_paths, _bboxes, _effective_size, shared_palette, process_meta = _process_frames(
        cfg,
        raw_paths,
        final_dir,
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=key[:3],
        key_tolerance=0,
        max_colors=6,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="none",
        palette_mode="auto",
        description="多彩主体",
        run_dir=tmp_path,
    )

    assert local_calls == [1]
    assert process_meta["ramp"]["source"] == "local_fallback"
    assert "vl exploded" in process_meta["ramp"]["vl_error"]
    assert process_meta["palette_mode"] == "vl_ramp_shared"
    assert len(final_paths) == 2
    # 回退后仍应产出可见像素（限色未清空主体）
    assert any(_visible_colors(path) for path in final_paths)


def test_process_frames_local_ramp_when_no_vl_key(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    final_dir = tmp_path / "final"
    raw_dir.mkdir()
    key = (255, 0, 255, 255)
    raw_path = raw_dir / "frame_001.png"
    _draw_multicolor_subject(raw_path, key=key)

    def raise_missing_key(_cfg):
        raise RuntimeError("missing vl key")

    monkeypatch.setattr("pix.sprite_video_bridge.require_vl_api_key", raise_missing_key)

    cfg = AppConfig()
    cfg.sprite.shared_palette = True

    final_paths, _bboxes, _effective_size, _shared_palette, process_meta = _process_frames(
        cfg,
        [raw_path],
        final_dir,
        target_size=(64, 64),
        frame_size_step=16,
        anchor="bottom_center",
        key_rgb=key[:3],
        key_tolerance=0,
        max_colors=6,
        dither="none",
        edge_style="hard",
        bg_feather=0,
        generated_preprocess_method="none",
        palette_mode="auto",
        run_dir=tmp_path,
    )

    assert process_meta["ramp"]["source"] == "local"
    assert "missing vl key" in process_meta["ramp"]["vl_error"]
    assert process_meta["palette_mode"] == "vl_ramp_shared"
    assert len(final_paths) == 1
