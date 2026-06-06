from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pix.api.http_client import ProviderError
from pix.api.image_dispatcher import dispatch_image_request
from pix.api.image_model_registry import TEXT_TO_IMAGE, available_model_infos
from pix.api.image_providers import ImageProviderResult
from pix.config import AppConfig, ImageProviderConfig, ImageProviderModelConfig, load_config


class ImageProviderConfigTests(unittest.TestCase):
    def test_legacy_packy_env_creates_provider(self) -> None:
        with patch.dict(os.environ, {"PACKY_API_KEY": "pk-test", "PACKY_BASE_URL": "https://packy.example"}, clear=True):
            cfg = load_config(env_file=None)
        provider = next((item for item in cfg.image_providers if item.id == "packy"), None)
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.base_url, "https://packy.example")
        self.assertEqual(provider.api_key, "pk-test")
        self.assertIn("gpt-image-2", [model.id for model in provider.models])

    def test_crazyrouter_env_adds_discoverable_provider(self) -> None:
        with patch.dict(os.environ, {"CRAZYROUTER_API_KEY": "cr-test", "PIX_IMAGE_DEFAULT_MODEL": "nano-banana"}, clear=True):
            cfg = load_config(env_file=None)
        provider = next((item for item in cfg.image_providers if item.id == "crazyrouter"), None)
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.base_url, "https://crazyrouter.com")
        self.assertTrue(provider.discover_models)
        self.assertEqual(cfg.image_gen.model, "nano-banana")

    def test_available_models_merges_builtin_crazyrouter_models(self) -> None:
        cfg = AppConfig()
        cfg.image_providers = [
            ImageProviderConfig(
                id="crazyrouter",
                display_name="Crazyrouter",
                base_url="https://crazyrouter.com",
                api_key="cr-test",
                priority=10,
                discover_models=False,
                protocols=["openai_images", "midjourney", "ideogram", "kling"],
            )
        ]
        infos = available_model_infos(cfg)
        ids = {item.id for item in infos}
        self.assertIn("gpt-image-2", ids)
        self.assertIn("midjourney", ids)
        self.assertIn("ideogram-v3", ids)


class _StubProvider:
    def __init__(self, provider_id: str, *, should_fail: bool, category: str = "server_error") -> None:
        self.provider_id = provider_id
        self.should_fail = should_fail
        self.category = category

    def generate(self, request):  # noqa: ANN001
        if self.should_fail:
            raise ProviderError("boom", category=self.category, provider_id=self.provider_id)
        return ImageProviderResult(b64_json="aGVsbG8=", provider_id=self.provider_id, provider_model="gpt-image-2", protocol="openai_images")


def _cfg_with_two_providers() -> AppConfig:
    cfg = AppConfig()
    model = ImageProviderModelConfig(
        id="gpt-image-2",
        provider_model="gpt-image-2",
        protocol="openai_images",
        operations=[TEXT_TO_IMAGE],
        sizes=["1024x1024"],
        qualities=["auto"],
        output_formats=["png"],
    )
    cfg.image_providers = [
        ImageProviderConfig(id="p1", display_name="P1", base_url="https://p1.example", api_key="k1", priority=10, models=[model]),
        ImageProviderConfig(id="p2", display_name="P2", base_url="https://p2.example", api_key="k2", priority=20, models=[model]),
    ]
    return cfg


class ImageDispatcherTests(unittest.TestCase):
    def test_failover_to_second_provider_on_retryable_error(self) -> None:
        cfg = _cfg_with_two_providers()

        def factory(_cfg, candidate):  # noqa: ANN001
            return _StubProvider(candidate.provider.id, should_fail=candidate.provider.id == "p1")

        with patch("pix.api.image_dispatcher.provider_for_candidate", side_effect=factory):
            result = dispatch_image_request(
                cfg,
                operation=TEXT_TO_IMAGE,
                prompt="test",
                model="gpt-image-2",
                size="1024x1024",
                quality="auto",
                output_format="png",
            )
        self.assertEqual(result.image.provider_id, "p2")
        self.assertEqual([attempt["status"] for attempt in result.attempts], ["failed", "success"])

    def test_non_retryable_error_does_not_failover(self) -> None:
        cfg = _cfg_with_two_providers()

        def factory(_cfg, candidate):  # noqa: ANN001
            return _StubProvider(candidate.provider.id, should_fail=True, category="invalid_request")

        with patch("pix.api.image_dispatcher.provider_for_candidate", side_effect=factory):
            with self.assertRaises(ProviderError) as ctx:
                dispatch_image_request(
                    cfg,
                    operation=TEXT_TO_IMAGE,
                    prompt="test",
                    model="gpt-image-2",
                    size="1024x1024",
                    quality="auto",
                    output_format="png",
                )
        self.assertEqual(ctx.exception.category, "invalid_request")


if __name__ == "__main__":
    unittest.main()
