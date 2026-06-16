"""数据库初始化与会话。"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from pix_web.models import Base
from pix_web.billing import ensure_default_packages
from pix_web.pricing import ensure_default_pricing
from pix_web.provider_store import ensure_seeded_image_providers
from pix_web.system_settings import ensure_default_system_settings


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(engine: Engine, *, create_schema: bool = True) -> None:
    if create_schema:
        Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        ensure_default_pricing(db)
        ensure_default_system_settings(db)
        ensure_default_packages(db)
        ensure_seeded_image_providers(db)


def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
