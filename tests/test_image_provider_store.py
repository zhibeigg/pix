from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pix.api.image_model_registry import TEXT_TO_IMAGE, candidates_for_model, provider_api_key
from pix.config import AppConfig
from pix_web.models import Base, ImageProvider
from pix_web.provider_store import (
    apply_db_image_providers,
    ensure_seeded_image_providers,
    image_providers_from_db,
)


class ProviderStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _row(self, **kw) -> ImageProvider:
        defaults = dict(
            id="p1", display_name="P1", enabled=True, base_url="https://p1.example",
            api_key="k1", api_key_env="", priority=10, discover_models=False,
            protocols=["openai_images"],
            models=[{"id": "gpt-image-2", "provider_model": "gpt-image-2",
                     "protocol": "openai_images", "operations": ["text_to_image", "image_to_image"]}],
        )
        defaults.update(kw)
        row = ImageProvider(**defaults)
        self.db.add(row)
        self.db.commit()
        return row

    def test_seed_imports_from_load_config_when_empty(self) -> None:
        with patch.dict(os.environ, {"PACKY_API_KEY": "pk-seed"}, clear=True):
            ensure_seeded_image_providers(self.db)
        ids = {r.id for r in self.db.scalars(select(ImageProvider))}
        self.assertIn("packy", ids)

    def test_seed_is_idempotent(self) -> None:
        with patch.dict(os.environ, {"PACKY_API_KEY": "pk-seed"}, clear=True):
            ensure_seeded_image_providers(self.db)
            first = self.db.scalar(select(ImageProvider.id).limit(1))
            ensure_seeded_image_providers(self.db)
        count = len(list(self.db.scalars(select(ImageProvider))))
        same = self.db.scalar(select(ImageProvider.id).limit(1))
        self.assertGreaterEqual(count, 1)
        self.assertEqual(first, same)

    def test_apply_replaces_and_sorts_by_priority(self) -> None:
        self._row(id="p2", display_name="P2", base_url="https://p2.example", api_key="k2", priority=5)
        self._row(id="p1", priority=20)
        cfg = AppConfig()
        cfg.image_providers = []  # base cfg may already contain env providers; replace expected
        apply_db_image_providers(cfg, self.db)
        self.assertEqual([p.id for p in cfg.image_providers], ["p2", "p1"])

    def test_apply_keeps_base_when_db_empty(self) -> None:
        cfg = AppConfig()
        before = list(cfg.image_providers)
        apply_db_image_providers(cfg, self.db)
        self.assertEqual([p.id for p in cfg.image_providers], [p.id for p in before])

    def test_api_key_env_fallback_after_injection(self) -> None:
        self._row(id="p1", api_key="", api_key_env="MY_PROVIDER_KEY")
        cfg = AppConfig()
        apply_db_image_providers(cfg, self.db)
        provider = next(p for p in cfg.image_providers if p.id == "p1")
        with patch.dict(os.environ, {"MY_PROVIDER_KEY": "from-env"}, clear=True):
            self.assertEqual(provider_api_key(provider), "from-env")

    def test_db_providers_flow_into_candidates(self) -> None:
        self._row(id="p1", priority=10)
        self._row(id="p2", display_name="P2", base_url="https://p2.example", api_key="k2", priority=20)
        cfg = AppConfig()
        cfg.image_gen.model = "gpt-image-2"
        apply_db_image_providers(cfg, self.db)
        candidates = candidates_for_model(cfg, "gpt-image-2", TEXT_TO_IMAGE)
        self.assertEqual([c.provider.id for c in candidates], ["p1", "p2"])


if __name__ == "__main__":
    unittest.main()
