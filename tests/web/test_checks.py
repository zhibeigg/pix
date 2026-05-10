from __future__ import annotations

from pix_web.checks import check_database, check_jwt_secret, check_queue, check_storage
from pix_web.config import WebSettings


def test_jwt_secret_check_rejects_default() -> None:
    result = check_jwt_secret(WebSettings())

    assert result.ok is False


def test_jwt_secret_check_accepts_long_secret() -> None:
    result = check_jwt_secret(WebSettings(jwt_secret="x" * 40))

    assert result.ok is True


def test_storage_check_accepts_writable_directory(tmp_path) -> None:
    result = check_storage(WebSettings(storage_root=tmp_path / "storage"))

    assert result.ok is True


def test_database_check_accepts_sqlite(tmp_path) -> None:
    db_path = tmp_path / "check.db"
    settings = WebSettings(database_url=f"sqlite:///{db_path}")

    result = check_database(settings)

    assert result.ok is True


def test_queue_database_backend_does_not_require_redis() -> None:
    result = check_queue(WebSettings(queue_backend="database"))

    assert result.ok is True


def test_database_check_reports_invalid_path(tmp_path) -> None:
    bad_dir = tmp_path / "missing" / "nested"
    result = check_database(WebSettings(database_url=f"sqlite:///{bad_dir / 'bad.db'}"))

    assert result.ok is False
