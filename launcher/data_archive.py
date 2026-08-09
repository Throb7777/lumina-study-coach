"""Compatibility entry point for Lumina's shared data archive implementation."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from app.data_archive import (
        ArchiveError,
        create_backup_archive,
        inspect_backup_archive,
        main,
        managed_note_files,
        restore_backup_archive,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.data_archive import (
        ArchiveError,
        create_backup_archive,
        inspect_backup_archive,
        main,
        managed_note_files,
        restore_backup_archive,
    )

__all__ = [
    "ArchiveError",
    "create_backup_archive",
    "inspect_backup_archive",
    "managed_note_files",
    "restore_backup_archive",
]


if __name__ == "__main__":
    raise SystemExit(main())
