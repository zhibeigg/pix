from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "ix_payment_orders_paid_at"


def test_paid_at_index_migration_round_trips(tmp_path, monkeypatch) -> None:
    database = tmp_path / "admin-dashboard-index.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("PIX_DISABLE_DOTENV", "1")
    monkeypatch.setenv("PIX_WEB_DATABASE_URL", database_url)

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "0027_admin_dashboard_paid_at_index")

    engine = sa.create_engine(database_url)
    try:
        index_names = {
            item["name"] for item in sa.inspect(engine).get_indexes("payment_orders")
        }
        assert INDEX_NAME in index_names
    finally:
        engine.dispose()

    command.downgrade(config, "0026_promo_order_snapshots")

    engine = sa.create_engine(database_url)
    try:
        index_names = {
            item["name"] for item in sa.inspect(engine).get_indexes("payment_orders")
        }
        assert INDEX_NAME not in index_names
    finally:
        engine.dispose()
