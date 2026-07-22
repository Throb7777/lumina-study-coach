import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.maintenance import backup_database


def test_database_backup_is_consistent_and_rotated(tmp_path: Path) -> None:
    database_path = tmp_path / "learning-flow-coach.db"
    backup_dir = tmp_path / "backups"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('kept')")
        connection.commit()

    start = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    latest = None
    for offset in range(7):
        latest = backup_database(
            database_path,
            backup_dir,
            now_provider=lambda offset=offset: start + timedelta(seconds=offset),
        )

    assert latest is not None
    assert len(list(backup_dir.glob("learning-flow-coach-*.db"))) == 5
    with closing(sqlite3.connect(latest)) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("kept",)


def test_database_backup_skips_missing_database(tmp_path: Path) -> None:
    assert backup_database(tmp_path / "missing.db", tmp_path / "backups") is None
    assert not (tmp_path / "backups").exists()
