from __future__ import annotations

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pix_web.models import Base, ImageProvider, User
from pix_web.routers.providers import (
    create_provider,
    delete_provider,
    list_presets,
    list_providers,
    update_provider,
)
from pix_web.schemas import ImageProviderCreateRequest, ImageProviderUpdateRequest


def _create_req(**kw) -> ImageProviderCreateRequest:
    defaults = dict(id="p1", display_name="P1", base_url="https://p1.example",
                    api_key="k1", protocols=["openai_images"], models=[])
    defaults.update(kw)
    return ImageProviderCreateRequest(**defaults)


def _update_req(**kw) -> ImageProviderUpdateRequest:
    defaults = dict(display_name="P1", base_url="https://p1.example", protocols=["openai_images"], models=[])
    defaults.update(kw)
    return ImageProviderUpdateRequest(**defaults)


class AdminProvidersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db: Session = sessionmaker(bind=self.engine)()
        self.admin = User(email="admin@example.com", password_hash="x", display_name="admin", role="admin", status="active")
        self.db.add(self.admin)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_create_and_list_masks_key(self) -> None:
        created = create_provider(_create_req(), _admin=self.admin, db=self.db)
        self.assertTrue(created.has_api_key)
        self.assertFalse(hasattr(created, "api_key"))
        rows = list_providers(_admin=self.admin, db=self.db)
        self.assertEqual([r.id for r in rows], ["p1"])
        self.assertTrue(rows[0].has_api_key)

    def test_create_duplicate_returns_409(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            create_provider(_create_req(), _admin=self.admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_unknown_protocol_returns_422(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_provider(_create_req(protocols=["nope"]), _admin=self.admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_empty_base_url_returns_422(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_provider(_create_req(base_url="  "), _admin=self.admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_update_keeps_key_when_blank(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        update_provider("p1", _update_req(api_key=""), _admin=self.admin, db=self.db)
        self.assertEqual(self.db.get(ImageProvider, "p1").api_key, "k1")

    def test_update_overwrites_key_and_clears(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        update_provider("p1", _update_req(api_key="k2"), _admin=self.admin, db=self.db)
        self.assertEqual(self.db.get(ImageProvider, "p1").api_key, "k2")
        update_provider("p1", _update_req(clear_api_key=True), _admin=self.admin, db=self.db)
        self.assertEqual(self.db.get(ImageProvider, "p1").api_key, "")

    def test_delete(self) -> None:
        create_provider(_create_req(), _admin=self.admin, db=self.db)
        out = delete_provider("p1", _admin=self.admin, db=self.db)
        self.assertEqual(out, {"deleted": True})
        self.assertIsNone(self.db.get(ImageProvider, "p1"))

    def test_presets_available(self) -> None:
        presets = list_presets(_admin=self.admin)
        self.assertIn("shengsuanyun", [p.key for p in presets])


if __name__ == "__main__":
    unittest.main()
