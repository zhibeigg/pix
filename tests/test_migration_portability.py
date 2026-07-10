from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def test_boolean_server_defaults_are_cross_dialect() -> None:
    forbidden = ('server_default=sa.text("1")', 'server_default=sa.text("0")')
    offenders: list[str] = []

    for migration in sorted(MIGRATIONS.glob("*.py")):
        source = migration.read_text(encoding="utf-8")
        if any(pattern in source for pattern in forbidden):
            offenders.append(migration.name)

    assert offenders == []
