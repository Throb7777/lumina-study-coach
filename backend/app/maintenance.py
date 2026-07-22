import argparse
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings


def backup_database(
    database_path: Path,
    backup_dir: Path,
    now_provider: Callable[[], datetime] | None = None,
    keep: int = 5,
) -> Path | None:
    if not database_path.is_file():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = (now_provider or (lambda: datetime.now(UTC)))()
    destination = backup_dir / f"learning-flow-coach-{now:%Y%m%d-%H%M%S}.db"
    with closing(sqlite3.connect(database_path)) as source, closing(
        sqlite3.connect(destination)
    ) as target:
        source.backup(target)

    backups = sorted(backup_dir.glob("learning-flow-coach-*.db"), reverse=True)
    for expired in backups[keep:]:
        expired.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Learning Flow Coach maintenance commands")
    parser.add_argument("command", choices=["backup-database"])
    args = parser.parse_args()
    if args.command == "backup-database":
        destination = backup_database(
            settings.database_path.expanduser().resolve(),
            settings.runtime_data_dir.expanduser().resolve() / "backups",
        )
        if destination is not None:
            print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
