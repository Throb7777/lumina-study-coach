from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from launcher.data_archive import (
    ArchiveError,
    create_backup_archive,
    inspect_backup_archive,
    restore_backup_archive,
)


def create_database(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("create table records (value text)")
        connection.execute("insert into records values (?)", (value,))
        connection.commit()


class DataArchiveTests(unittest.TestCase):
    def test_archive_round_trip_includes_database_and_nested_materials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            database = source / "learning-flow-coach.db"
            materials = source / "materials"
            create_database(database, "kept")
            material = materials / "42" / "source.pdf"
            material.parent.mkdir(parents=True)
            material.write_bytes(b"pdf-content")

            archive = create_backup_archive(
                database,
                materials,
                root / "backups",
                datetime(2026, 7, 22, 12, 34, 56),
            )

            self.assertIsNotNone(archive)
            assert archive is not None
            self.assertEqual(archive.name, "lumina-backup-20260722-123456.zip")
            manifest = inspect_backup_archive(archive)
            self.assertEqual(manifest["format_version"], 1)
            self.assertEqual(
                {item["path"] for item in manifest["files"]},
                {"database/learning-flow-coach.db", "materials/42/source.pdf"},
            )

            restored = root / "restored-runtime-data"
            restore_backup_archive(archive, restored)
            with closing(sqlite3.connect(restored / "learning-flow-coach.db")) as connection:
                self.assertEqual(
                    connection.execute("select value from records").fetchone(),
                    ("kept",),
                )
            self.assertEqual((restored / "materials/42/source.pdf").read_bytes(), b"pdf-content")

    def test_restore_rejects_existing_data_without_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "source.db"
            create_database(database, "backup")
            archive = create_backup_archive(database, root / "materials", root / "backups")
            assert archive is not None
            target = root / "runtime-data"
            create_database(target / "learning-flow-coach.db", "current")

            with self.assertRaises(ArchiveError):
                restore_backup_archive(archive, target)

            with closing(sqlite3.connect(target / "learning-flow-coach.db")) as connection:
                self.assertEqual(
                    connection.execute("select value from records").fetchone(),
                    ("current",),
                )

    def test_replace_restores_data_but_preserves_runtime_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "source.db"
            create_database(database, "backup")
            source_materials = root / "source-materials"
            source_materials.mkdir()
            (source_materials / "new.txt").write_text("new", encoding="utf-8")
            archive = create_backup_archive(database, source_materials, root / "backups")
            assert archive is not None

            target = root / "runtime-data"
            create_database(target / "learning-flow-coach.db", "current")
            (target / "materials").mkdir()
            (target / "materials/old.txt").write_text("old", encoding="utf-8")
            (target / "logs").mkdir()
            (target / "logs/server.log").write_text("keep-log", encoding="utf-8")

            restore_backup_archive(archive, target, replace=True)

            with closing(sqlite3.connect(target / "learning-flow-coach.db")) as connection:
                self.assertEqual(
                    connection.execute("select value from records").fetchone(),
                    ("backup",),
                )
            self.assertFalse((target / "materials/old.txt").exists())
            self.assertEqual((target / "materials/new.txt").read_text(), "new")
            self.assertEqual((target / "logs/server.log").read_text(), "keep-log")

    def test_tampered_archive_fails_hash_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "source.db"
            create_database(database, "backup")
            archive = create_backup_archive(database, root / "materials", root / "backups")
            assert archive is not None
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(tampered, "w") as target:
                for entry in source.infolist():
                    content = source.read(entry.filename)
                    if entry.filename == "database/learning-flow-coach.db":
                        content = b"tampered"
                    target.writestr(entry, content)

            with self.assertRaises(ArchiveError):
                inspect_backup_archive(tampered)

    def test_archive_rejects_path_traversal_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.zip"
            manifest = {
                "format_version": 1,
                "application": "lumina-study-coach",
                "files": [],
            }
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("manifest.json", json.dumps(manifest))
                bundle.writestr("../outside.txt", "unsafe")

            with self.assertRaises(ArchiveError):
                inspect_backup_archive(archive)

    def test_missing_database_returns_no_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(
                create_backup_archive(
                    root / "missing.db",
                    root / "materials",
                    root / "backups",
                )
            )


if __name__ == "__main__":
    unittest.main()
