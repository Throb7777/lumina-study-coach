from __future__ import annotations

import json
import hashlib
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


def add_attachment_reference(path: Path, storage_path: str) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "create table exercise_response_attachments (storage_path text not null)"
        )
        connection.execute(
            "insert into exercise_response_attachments values (?)",
            (storage_path,),
        )
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
            ocr_cache = materials / "42" / "ocr-cache" / "derived.txt"
            ocr_cache.parent.mkdir()
            ocr_cache.write_text("derived", encoding="utf-8")
            attachments = source / "answer-attachments"
            attachment = attachments / "9" / "answer.png"
            attachment.parent.mkdir(parents=True)
            attachment.write_bytes(b"image-content")
            add_attachment_reference(database, "9/answer.png")
            attachment_cache = attachments / "9" / "ocr-cache" / "derived.txt"
            attachment_cache.parent.mkdir()
            attachment_cache.write_text("derived", encoding="utf-8")
            orphan = attachments / "orphan" / "unused.png"
            orphan.parent.mkdir()
            orphan.write_bytes(b"orphan")
            note = source / "vault" / "Course" / "Section.md"
            note.parent.mkdir(parents=True)
            note.write_text("# Managed note", encoding="utf-8")

            archive = create_backup_archive(
                database,
                materials,
                root / "backups",
                datetime(2026, 7, 22, 12, 34, 56),
                attachments=attachments,
                notes=[(note, "notes/Course/Section.md")],
            )

            self.assertIsNotNone(archive)
            assert archive is not None
            self.assertEqual(archive.name, "lumina-backup-20260722-123456.zip")
            manifest = inspect_backup_archive(archive)
            self.assertEqual(manifest["format_version"], 2)
            self.assertEqual(
                {item["path"] for item in manifest["files"]},
                {
                    "database/learning-flow-coach.db",
                    "materials/42/source.pdf",
                    "answer-attachments/9/answer.png",
                    "notes/Course/Section.md",
                },
            )
            self.assertIn("ocr-cache", manifest["excluded"])
            self.assertNotIn(
                "answer-attachments/9/ocr-cache/derived.txt",
                {item["path"] for item in manifest["files"]},
            )
            self.assertNotIn(
                "answer-attachments/orphan/unused.png",
                {item["path"] for item in manifest["files"]},
            )

            restored = root / "restored-runtime-data"
            restored_vault = root / "restored-vault"
            restored_vault.mkdir()
            restore_backup_archive(archive, restored, note_destination=restored_vault)
            with closing(sqlite3.connect(restored / "learning-flow-coach.db")) as connection:
                self.assertEqual(
                    connection.execute("select value from records").fetchone(),
                    ("kept",),
                )
            self.assertEqual((restored / "materials/42/source.pdf").read_bytes(), b"pdf-content")
            self.assertEqual(
                (restored / "answer-attachments/9/answer.png").read_bytes(),
                b"image-content",
            )
            self.assertEqual(
                (restored_vault / "Course/Section.md").read_text(encoding="utf-8"),
                "# Managed note",
            )

    def test_cross_machine_restore_moves_managed_notes_and_rebinds_vault(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_runtime = root / "source-runtime"
            database = source_runtime / "learning-flow-coach.db"
            source_vault = root / "old-machine-vault"
            note = source_vault / "Course" / "Section.md"
            note.parent.mkdir(parents=True)
            note.write_text("# Portable note", encoding="utf-8")
            database.parent.mkdir(parents=True)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("create table app_settings (key text primary key, value text)")
                connection.execute("create table sections (note_relative_path text)")
                connection.execute(
                    "insert into app_settings values ('obsidian_vault_path', ?)",
                    (str(source_vault),),
                )
                connection.execute("insert into sections values ('Course/Section.md')")
                connection.commit()

            archive = create_backup_archive(
                database,
                source_runtime / "materials",
                root / "backups",
            )
            assert archive is not None
            self.assertIn(
                "notes/Course/Section.md",
                {item["path"] for item in inspect_backup_archive(archive)["files"]},
            )

            new_vault = root / "new-machine-vault"
            new_vault.mkdir()
            restored_runtime = root / "restored-runtime"
            restore_backup_archive(
                archive,
                restored_runtime,
                note_destination=new_vault,
            )

            self.assertEqual(
                (new_vault / "Course/Section.md").read_text(encoding="utf-8"),
                "# Portable note",
            )
            with closing(
                sqlite3.connect(restored_runtime / "learning-flow-coach.db")
            ) as connection:
                self.assertEqual(
                    connection.execute(
                        "select value from app_settings where key='obsidian_vault_path'"
                    ).fetchone(),
                    (str(new_vault.resolve()),),
                )

    def test_backup_rejects_unavailable_vault_when_managed_notes_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime" / "learning-flow-coach.db"
            database.parent.mkdir(parents=True)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("create table app_settings (key text primary key, value text)")
                connection.execute("create table sections (note_relative_path text)")
                connection.execute(
                    "insert into app_settings values ('obsidian_vault_path', ?)",
                    (str(root / "missing-vault"),),
                )
                connection.execute("insert into sections values ('Course/Section.md')")
                connection.commit()

            with self.assertRaisesRegex(ArchiveError, "vault is unavailable"):
                create_backup_archive(
                    database,
                    root / "runtime" / "materials",
                    root / "backups",
                )

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

    def test_archive_rejects_case_insensitive_member_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "collision.zip"
            payloads = {
                "database/learning-flow-coach.db": b"database",
                "materials/A.txt": b"first",
                "materials/a.txt": b"second",
            }
            manifest = {
                "format_version": 2,
                "application": "lumina-study-coach",
                "files": [
                    {
                        "path": name,
                        "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                    for name, content in payloads.items()
                ],
            }
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("manifest.json", json.dumps(manifest))
                for name, content in payloads.items():
                    bundle.writestr(name, content)

            with self.assertRaisesRegex(ArchiveError, "colliding file names"):
                inspect_backup_archive(archive)

    def test_archive_rejects_suspicious_compression_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "compression-bomb.zip"
            content = b"0" * (20 * 1024 * 1024)
            manifest = {
                "format_version": 2,
                "application": "lumina-study-coach",
                "files": [
                    {
                        "path": "database/learning-flow-coach.db",
                        "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ],
            }
            with zipfile.ZipFile(
                archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as bundle:
                bundle.writestr("manifest.json", json.dumps(manifest))
                bundle.writestr("database/learning-flow-coach.db", content)

            with self.assertRaisesRegex(ArchiveError, "compression ratio"):
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
