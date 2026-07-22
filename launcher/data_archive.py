from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4


ARCHIVE_FORMAT_VERSION = 1
DATABASE_MEMBER = "database/learning-flow-coach.db"
MATERIALS_PREFIX = "materials/"
MANIFEST_MEMBER = "manifest.json"


class ArchiveError(RuntimeError):
    pass


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_snapshot(source: Path, destination: Path) -> None:
    with closing(sqlite3.connect(source)) as source_connection:
        with closing(sqlite3.connect(destination)) as destination_connection:
            source_connection.backup(destination_connection)


def _unique_archive_path(destination: Path, timestamp: str) -> Path:
    candidate = destination / f"lumina-backup-{timestamp}.zip"
    suffix = 1
    while candidate.exists():
        candidate = destination / f"lumina-backup-{timestamp}-{suffix}.zip"
        suffix += 1
    return candidate


def _material_files(materials: Path) -> list[tuple[Path, str]]:
    if not materials.is_dir():
        return []
    resolved_root = materials.resolve()
    files: list[tuple[Path, str]] = []
    for source in sorted(materials.rglob("*")):
        if source.is_symlink() or not source.is_file():
            continue
        resolved = source.resolve()
        if not resolved.is_relative_to(resolved_root):
            raise ArchiveError("material path escapes the material directory")
        member = MATERIALS_PREFIX + source.relative_to(materials).as_posix()
        files.append((source, member))
    return files


def create_backup_archive(
    database: Path,
    materials: Path,
    destination_dir: Path,
    now: datetime | None = None,
    keep: int = 5,
) -> Path | None:
    source_database = database.resolve()
    if not source_database.is_file():
        return None
    destination_root = destination_dir.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    destination = _unique_archive_path(destination_root, timestamp)

    with tempfile.TemporaryDirectory(prefix="lumina-backup-") as temporary:
        temporary_root = Path(temporary)
        snapshot = temporary_root / "database.db"
        _database_snapshot(source_database, snapshot)
        _validate_database(snapshot)
        files = [(snapshot, DATABASE_MEMBER), *_material_files(materials)]
        manifest = {
            "format_version": ARCHIVE_FORMAT_VERSION,
            "application": "lumina-study-coach",
            "created_at": (now or datetime.now()).isoformat(timespec="seconds"),
            "files": [
                {
                    "path": member,
                    "size": source.stat().st_size,
                    "sha256": _file_digest(source),
                }
                for source, member in files
            ],
            "excluded": ["ai-auth", "logs", "service.pid", "backups"],
        }
        temporary_archive = destination_root / f".{destination.name}.{uuid4().hex}.tmp"
        try:
            with zipfile.ZipFile(
                temporary_archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                archive.writestr(
                    MANIFEST_MEMBER,
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                for source, member in files:
                    archive.write(source, member)
            inspect_backup_archive(temporary_archive)
            temporary_archive.replace(destination)
        finally:
            temporary_archive.unlink(missing_ok=True)

    if keep > 0:
        archives = sorted(
            destination_root.glob("lumina-backup-*.zip"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for old_archive in archives[keep:]:
            old_archive.unlink(missing_ok=True)
    return destination


def _validated_member_name(raw_name: str) -> str:
    path = PurePosixPath(raw_name)
    if path.is_absolute() or ".." in path.parts or "\\" in raw_name:
        raise ArchiveError(f"unsafe archive member: {raw_name}")
    name = path.as_posix()
    if name == MANIFEST_MEMBER or name == DATABASE_MEMBER:
        return name
    if name.startswith(MATERIALS_PREFIX) and len(path.parts) > 1:
        return name
    raise ArchiveError(f"unexpected archive member: {raw_name}")


def _load_manifest(archive: zipfile.ZipFile) -> dict:
    try:
        manifest = json.loads(archive.read(MANIFEST_MEMBER).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveError("backup manifest is missing or invalid") from error
    if manifest.get("format_version") != ARCHIVE_FORMAT_VERSION:
        raise ArchiveError("backup format version is not supported")
    if manifest.get("application") != "lumina-study-coach":
        raise ArchiveError("backup belongs to another application")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ArchiveError("backup manifest file list is invalid")
    return manifest


def _validate_database(path: Path) -> None:
    try:
        with closing(sqlite3.connect(path)) as connection:
            integrity = connection.execute("pragma integrity_check").fetchone()
            foreign_keys = connection.execute("pragma foreign_key_check").fetchall()
    except sqlite3.Error as error:
        raise ArchiveError("backup database cannot be opened") from error
    if integrity != ("ok",) or foreign_keys:
        raise ArchiveError("backup database failed integrity checks")


def inspect_backup_archive(archive_path: Path) -> dict:
    source = archive_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    with zipfile.ZipFile(source) as archive:
        names = [_validated_member_name(info.filename) for info in archive.infolist()]
        if len(names) != len(set(names)):
            raise ArchiveError("backup contains duplicate file names")
        manifest = _load_manifest(archive)
        expected = {
            item.get("path"): item
            for item in manifest["files"]
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        archived_files = set(names) - {MANIFEST_MEMBER}
        if set(expected) != archived_files or DATABASE_MEMBER not in expected:
            raise ArchiveError("backup contents do not match the manifest")
        for member, metadata in expected.items():
            content = archive.read(member)
            if len(content) != metadata.get("size"):
                raise ArchiveError(f"backup size check failed: {member}")
            if hashlib.sha256(content).hexdigest() != metadata.get("sha256"):
                raise ArchiveError(f"backup hash check failed: {member}")
        return manifest


def restore_backup_archive(
    archive_path: Path,
    runtime_data: Path,
    *,
    replace: bool = False,
) -> dict:
    manifest = inspect_backup_archive(archive_path)
    runtime_root = runtime_data.resolve()
    target_database = runtime_root / "learning-flow-coach.db"
    target_materials = runtime_root / "materials"
    if not replace and (target_database.exists() or target_materials.exists()):
        raise ArchiveError("restore target already contains local data")

    runtime_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="lumina-restore-",
        dir=runtime_root.parent,
    ) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive_path.resolve()) as archive:
            for item in manifest["files"]:
                member = _validated_member_name(item["path"])
                relative = (
                    Path("learning-flow-coach.db")
                    if member == DATABASE_MEMBER
                    else Path(member).relative_to("materials")
                )
                destination = staging / (
                    relative if member == DATABASE_MEMBER else Path("materials") / relative
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)

        staged_database = staging / "learning-flow-coach.db"
        staged_materials = staging / "materials"
        _validate_database(staged_database)
        staged_materials.mkdir(exist_ok=True)

        runtime_root.mkdir(parents=True, exist_ok=True)
        rollback_id = uuid4().hex
        old_database = runtime_root / f".restore-old-{rollback_id}.db"
        old_materials = runtime_root / f".restore-old-materials-{rollback_id}"
        database_moved = False
        materials_moved = False
        try:
            if target_database.exists():
                target_database.replace(old_database)
                database_moved = True
            if target_materials.exists():
                target_materials.replace(old_materials)
                materials_moved = True
            staged_database.replace(target_database)
            staged_materials.replace(target_materials)
        except OSError as error:
            target_database.unlink(missing_ok=True)
            if target_materials.exists():
                shutil.rmtree(target_materials)
            if database_moved:
                old_database.replace(target_database)
            if materials_moved:
                old_materials.replace(target_materials)
            raise ArchiveError("restore failed and existing data was rolled back") from error
        old_database.unlink(missing_ok=True)
        if old_materials.exists():
            shutil.rmtree(old_materials)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumina local data archive")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--database", type=Path, required=True)
    create_parser.add_argument("--materials", type=Path, required=True)
    create_parser.add_argument("--destination", type=Path, required=True)
    create_parser.add_argument("--keep", type=int, default=5)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--archive", type=Path, required=True)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--runtime-data", type=Path, required=True)
    restore_parser.add_argument("--replace", action="store_true")
    restore_parser.add_argument("--confirm", required=True)

    arguments = parser.parse_args()
    if arguments.command == "create":
        result = create_backup_archive(
            arguments.database,
            arguments.materials,
            arguments.destination,
            keep=arguments.keep,
        )
        print(result or "no-data")
        return 0
    if arguments.command == "inspect":
        print(json.dumps(inspect_backup_archive(arguments.archive), ensure_ascii=False))
        return 0
    if arguments.confirm != "RESTORE":
        raise ArchiveError("restore requires --confirm RESTORE")
    print(
        json.dumps(
            restore_backup_archive(
                arguments.archive,
                arguments.runtime_data,
                replace=arguments.replace,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
