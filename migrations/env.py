"""Alembic migration environment for Pix Web."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
import sqlalchemy as sa
from sqlalchemy import engine_from_config, pool

from pix_web.config import load_web_settings
from pix_web.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_VERSION_TABLE = "alembic_version"
_VERSION_NUM_LENGTH = 128


def _database_url() -> str:
    return load_web_settings().database_url


def _ensure_version_table_capacity(connection: sa.Connection) -> None:
    inspector = sa.inspect(connection)
    if not inspector.has_table(_VERSION_TABLE):
        table = sa.Table(
            _VERSION_TABLE,
            sa.MetaData(),
            sa.Column("version_num", sa.String(_VERSION_NUM_LENGTH), nullable=False),
            sa.PrimaryKeyConstraint("version_num", name=f"{_VERSION_TABLE}_pkc"),
        )
        table.create(connection)
        return

    if connection.dialect.name != "postgresql":
        return

    version_column = next(
        column for column in inspector.get_columns(_VERSION_TABLE) if column["name"] == "version_num"
    )
    current_length = getattr(version_column["type"], "length", None)
    if current_length is not None and current_length < _VERSION_NUM_LENGTH:
        connection.execute(
            sa.text(
                f"ALTER TABLE {_VERSION_TABLE} "
                f"ALTER COLUMN version_num TYPE VARCHAR({_VERSION_NUM_LENGTH})"
            )
        )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        with connection.begin():
            _ensure_version_table_capacity(connection)
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
