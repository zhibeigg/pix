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


def make_engine(
    database_url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout: float = 30.0,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
) -> Engine:
    """创建数据库 engine。

    SQLite 使用内置连接池（QueuePool 参数不适用），仅放开跨线程检查。
    其余后端（如 PostgreSQL）显式配置连接池，避免默认 5+10 上限在高并发/
    慢序列化接口下被耗尽（QueuePool limit reached），并启用 pool_pre_ping
    以回收被服务端关闭的空闲连接。
    """
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False}, future=True)
    return create_engine(
        database_url,
        future=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )


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
