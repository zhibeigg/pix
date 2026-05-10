from __future__ import annotations

from sqlalchemy import select

from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.models import Base, PricingRule


def test_init_db_creates_schema_and_default_pricing(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'web.db'}")
    init_db(engine, create_schema=True)

    session_factory = make_session_factory(engine)
    with session_factory() as db:
        rules = list(db.scalars(select(PricingRule)))

    assert {rule.key for rule in rules} >= {"text_to_image", "image_to_image", "local_pixelize", "repixelize"}


def test_init_db_without_schema_creation_uses_existing_schema(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'existing.db'}")
    Base.metadata.create_all(engine)

    init_db(engine, create_schema=False)

    session_factory = make_session_factory(engine)
    with session_factory() as db:
        assert db.scalar(select(PricingRule).where(PricingRule.key == "text_to_image")) is not None
