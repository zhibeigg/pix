import ast
from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"
VERSION_NUM_LENGTH = 128


def test_boolean_server_defaults_are_cross_dialect() -> None:
    forbidden = ('server_default=sa.text("1")', 'server_default=sa.text("0")')
    offenders: list[str] = []

    for migration in sorted(MIGRATIONS.glob("*.py")):
        source = migration.read_text(encoding="utf-8")
        if any(pattern in source for pattern in forbidden):
            offenders.append(migration.name)

    assert offenders == []


def test_shared_settings_insert_uses_distinct_typed_key_parameters() -> None:
    source = (MIGRATIONS / "0021_shared_works.py").read_text(encoding="utf-8")

    assert ":insert_key" in source
    assert ":lookup_key" in source
    assert 'sa.bindparam("insert_key", type_=sa.String(length=96))' in source
    assert 'sa.bindparam("lookup_key", type_=sa.String(length=96))' in source


def test_revision_ids_fit_extended_version_table() -> None:
    revisions: list[str] = []
    for migration in sorted(MIGRATIONS.glob("*.py")):
        tree = ast.parse(migration.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == "revision" for target in node.targets):
                revisions.append(ast.literal_eval(node.value))

    assert revisions
    assert max(map(len, revisions)) <= VERSION_NUM_LENGTH


def test_empty_database_uses_extended_version_table(tmp_path, monkeypatch) -> None:
    database = tmp_path / "migration-smoke.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("PIX_DISABLE_DOTENV", "1")
    monkeypatch.setenv("PIX_WEB_DATABASE_URL", database_url)

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")

    engine = sa.create_engine(database_url)
    try:
        version_column = next(
            column
            for column in sa.inspect(engine).get_columns("alembic_version")
            if column["name"] == "version_num"
        )
        assert version_column["type"].length == VERSION_NUM_LENGTH
    finally:
        engine.dispose()
