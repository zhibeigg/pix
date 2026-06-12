from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pix.api.candidate_ranker import rank_candidates
from pix.config import AppConfig


class _FakePackyClient:
    def __init__(self) -> None:
        self.path = ""
        self.data: dict[str, object] = {}
        self.files: dict[str, tuple[str, bytes, str]] = {}

    def post_json(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AssertionError("VL 候选评分必须直接 multipart 上传图片，不应走 image_url JSON payload")

    def post_multipart(self, path, *, data, files):  # noqa: ANN001, ANN201
        self.path = path
        self.data = dict(data)
        self.files = dict(files)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "selected_index": 2,
                                "candidates": [
                                    {"index": 2, "rank": 1, "score": 95, "reason": "更清晰"},
                                    {"index": 1, "rank": 2, "score": 80, "reason": "可用"},
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }


class CandidateRankerUploadTests(unittest.TestCase):
    def test_rank_candidates_uploads_images_as_multipart_files(self) -> None:
        cfg = AppConfig()
        cfg.api.vl_api_key = "vl-test"
        fake = _FakePackyClient()

        with tempfile.TemporaryDirectory() as tmp:
            paths: list[Path] = []
            for index, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255)), start=1):
                path = Path(tmp) / f"candidate_{index}.png"
                Image.new("RGBA", (4, 4), color).save(path)
                paths.append(path)

            with patch("pix.api.candidate_ranker.make_packy_client", return_value=fake):
                ranking = rank_candidates(
                    cfg,
                    [(1, paths[0]), (2, paths[1])],
                    user_prompt="红色宝石",
                    target_size=(16, 16),
                )

        self.assertEqual(ranking.model, "claude-opus-4-8")
        self.assertEqual(ranking.selected_index, 2)
        self.assertEqual(fake.path, "/v1/chat/completions")
        self.assertEqual(fake.data.get("model"), "claude-opus-4-8")
        self.assertIn("candidate_01", fake.files)
        self.assertIn("candidate_02", fake.files)
        self.assertEqual(fake.files["candidate_01"][2], "image/png")
        messages = str(fake.data.get("messages", ""))
        payload = str(fake.data.get("payload", ""))
        self.assertNotIn("image_url", messages)
        self.assertNotIn("data:image", messages)
        self.assertNotIn("image_url", payload)
        self.assertNotIn("data:image", payload)
        manifest = json.loads(str(fake.data["candidate_manifest"]))
        self.assertEqual([item["field"] for item in manifest], ["candidate_01", "candidate_02"])


if __name__ == "__main__":
    unittest.main()
