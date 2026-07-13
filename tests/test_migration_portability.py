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


def test_promo_migration_adds_order_snapshots_and_round_trips(tmp_path, monkeypatch) -> None:
    database = tmp_path / "promo-migration.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("PIX_DISABLE_DOTENV", "1")
    monkeypatch.setenv("PIX_WEB_DATABASE_URL", database_url)

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "0024_membership")

    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.execute(
                sa.text(
                    """
                    INSERT INTO payment_orders (
                        user_id,
                        provider,
                        provider_order_id,
                        status,
                        amount_cents,
                        currency,
                        credits,
                        created_at
                    ) VALUES (
                        :user_id,
                        :provider,
                        :provider_order_id,
                        :status,
                        :amount_cents,
                        :currency,
                        :credits,
                        :created_at
                    )
                    """
                ),
                {
                    "user_id": 1,
                    "provider": "legacy",
                    "provider_order_id": "legacy-order",
                    "status": "paid",
                    "amount_cents": 1280,
                    "currency": "cny",
                    "credits": 100,
                    "created_at": "2026-07-13T00:00:00+00:00",
                },
            )
    finally:
        engine.dispose()

    def assert_upgraded_schema_and_data() -> None:
        migrated_engine = sa.create_engine(database_url)
        try:
            inspector = sa.inspect(migrated_engine)
            columns = {
                column["name"]: column
                for column in inspector.get_columns("payment_orders")
            }
            assert columns["promo_code"]["nullable"] is False
            assert columns["promo_discount_rate"]["nullable"] is False
            assert columns["original_amount_cents"]["nullable"] is False
            assert isinstance(columns["promo_discount_rate"]["type"], sa.Float)
            assert isinstance(columns["original_amount_cents"]["type"], sa.Integer)
            assert "ix_payment_orders_promo_code" in {
                index["name"] for index in inspector.get_indexes("payment_orders")
            }

            with migrated_engine.connect() as connection:
                row = connection.execute(
                    sa.text(
                        """
                        SELECT promo_code, promo_discount_rate, original_amount_cents
                        FROM payment_orders
                        WHERE provider_order_id = :provider_order_id
                        """
                    ),
                    {"provider_order_id": "legacy-order"},
                ).mappings().one()
            assert row["promo_code"] == ""
            assert row["promo_discount_rate"] == 1.0
            assert row["original_amount_cents"] == 1280
        finally:
            migrated_engine.dispose()

    command.upgrade(config, "0025_promo_links")
    migration_0025_engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(migration_0025_engine)
        payment_columns = {
            column["name"] for column in inspector.get_columns("payment_orders")
        }
        assert "promo_code" in payment_columns
        assert "promo_discount_rate" not in payment_columns
        assert "original_amount_cents" not in payment_columns
    finally:
        migration_0025_engine.dispose()

    command.upgrade(config, "0026_promo_order_snapshots")
    assert_upgraded_schema_and_data()

    command.downgrade(config, "0025_promo_links")
    downgraded_engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(downgraded_engine)
        payment_columns = {
            column["name"] for column in inspector.get_columns("payment_orders")
        }
        assert "promo_code" in payment_columns
        assert "promo_discount_rate" not in payment_columns
        assert "original_amount_cents" not in payment_columns
        assert "promo_links" in inspector.get_table_names()
    finally:
        downgraded_engine.dispose()

    command.upgrade(config, "0026_promo_order_snapshots")
    assert_upgraded_schema_and_data()


def test_promo_snapshot_migration_preserves_reconciled_production_schema(
    tmp_path, monkeypatch
) -> None:
    database = tmp_path / "promo-reconciled.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("PIX_DISABLE_DOTENV", "1")
    monkeypatch.setenv("PIX_WEB_DATABASE_URL", database_url)

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "0025_promo_links")

    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.exec_driver_sql(
                "ALTER TABLE payment_orders "
                "ADD COLUMN promo_discount_rate FLOAT NOT NULL DEFAULT 1.0"
            )
            connection.exec_driver_sql(
                "ALTER TABLE payment_orders "
                "ADD COLUMN original_amount_cents INTEGER NOT NULL DEFAULT 0"
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO payment_orders (
                        user_id,
                        provider,
                        provider_order_id,
                        status,
                        amount_cents,
                        currency,
                        credits,
                        promo_discount_rate,
                        original_amount_cents,
                        created_at
                    ) VALUES (
                        :user_id,
                        :provider,
                        :provider_order_id,
                        :status,
                        :amount_cents,
                        :currency,
                        :credits,
                        :promo_discount_rate,
                        :original_amount_cents,
                        :created_at
                    )
                    """
                ),
                {
                    "user_id": 1,
                    "provider": "reconciled",
                    "provider_order_id": "reconciled-order",
                    "status": "paid",
                    "amount_cents": 1500,
                    "currency": "cny",
                    "credits": 100,
                    "promo_discount_rate": 0.75,
                    "original_amount_cents": 2000,
                    "created_at": "2026-07-13T00:00:00+00:00",
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "0026_promo_order_snapshots")

    verified_engine = sa.create_engine(database_url)
    try:
        with verified_engine.connect() as connection:
            version = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            row = connection.execute(
                sa.text(
                    """
                    SELECT promo_discount_rate, original_amount_cents
                    FROM payment_orders
                    WHERE provider_order_id = :provider_order_id
                    """
                ),
                {"provider_order_id": "reconciled-order"},
            ).mappings().one()
        assert version == "0026_promo_order_snapshots"
        assert row["promo_discount_rate"] == 0.75
        assert row["original_amount_cents"] == 2000
    finally:
        verified_engine.dispose()
