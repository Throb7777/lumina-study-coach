from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unicodedata
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

ARCHIVE_FORMAT_VERSION = 2
SUPPORTED_ARCHIVE_FORMAT_VERSIONS = {1, 2}
DATABASE_MEMBER = "database/learning-flow-coach.db"
MATERIALS_PREFIX = "materials/"
ATTACHMENTS_PREFIX = "answer-attachments/"
NOTES_PREFIX = "notes/"
MANIFEST_MEMBER = "manifest.json"
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 200
MIN_COMPRESSION_RATIO_CHECK_BYTES = 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class ArchiveError(RuntimeError):
    pass


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_snapshot(source: Path, destination: Path) -> None:
    with (
        closing(sqlite3.connect(source)) as source_connection,
        closing(sqlite3.connect(destination)) as destination_connection,
    ):
        source_connection.backup(destination_connection)


def _unique_archive_path(destination: Path, timestamp: str) -> Path:
    candidate = destination / f"lumina-backup-{timestamp}.zip"
    suffix = 1
    while candidate.exists():
        candidate = destination / f"lumina-backup-{timestamp}-{suffix}.zip"
        suffix += 1
    return candidate


def _tree_files(
    root: Path,
    prefix: str,
    *,
    exclude_ocr_cache: bool = False,
) -> list[tuple[Path, str]]:
    if not root.is_dir():
        return []
    resolved_root = root.resolve()
    files: list[tuple[Path, str]] = []
    for source in sorted(root.rglob("*")):
        if source.is_symlink() or not source.is_file():
            continue
        relative = source.relative_to(root)
        if exclude_ocr_cache and "ocr-cache" in relative.parts:
            continue
        resolved = source.resolve()
        if not resolved.is_relative_to(resolved_root):
            raise ArchiveError("backup source path escapes its configured directory")
        member = prefix + relative.as_posix()
        files.append((source, member))
    return files


def managed_note_files(database: Path) -> list[tuple[Path, str]]:
    if not database.is_file():
        return []
    try:
        with closing(sqlite3.connect(database)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "select name from sqlite_master where type = 'table'"
                )
            }
            if not {"app_settings", "sections"}.issubset(tables):
                return []
            row = connection.execute(
                "select value from app_settings where key = 'obsidian_vault_path'"
            ).fetchone()
            relative_paths = [
                item[0]
                for item in connection.execute(
                    "select note_relative_path from sections "
                    "where note_relative_path is not null and trim(note_relative_path) != ''"
                )
            ]
    except sqlite3.Error as error:
        raise ArchiveError("cannot read managed note paths from the database") from error
    if row is None or not str(row[0]).strip():
        return []
    vault = Path(str(row[0])).expanduser()
    if not vault.is_dir():
        if relative_paths:
            raise ArchiveError(
                "configured Obsidian vault is unavailable; managed notes were not backed up"
            )
        return []
    resolved_vault = vault.resolve()
    files: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for raw_relative in relative_paths:
        relative = PurePosixPath(str(raw_relative).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ArchiveError("managed note path is unsafe")
        source = (resolved_vault / Path(*relative.parts)).resolve()
        if not source.is_relative_to(resolved_vault):
            raise ArchiveError("managed note path escapes the Obsidian vault")
        member = NOTES_PREFIX + relative.as_posix()
        if source.is_file() and member.casefold() not in seen:
            files.append((source, member))
            seen.add(member.casefold())
    return files


def managed_attachment_files(database: Path, attachments: Path) -> list[tuple[Path, str]]:
    if not database.is_file():
        return []
    try:
        with closing(sqlite3.connect(database)) as connection:
            table = connection.execute(
                "select 1 from sqlite_master "
                "where type = 'table' and name = 'exercise_response_attachments'"
            ).fetchone()
            if table is None:
                return []
            relative_paths = [
                row[0]
                for row in connection.execute(
                    "select storage_path from exercise_response_attachments"
                )
            ]
    except sqlite3.Error as error:
        raise ArchiveError("cannot read attachment paths from the database") from error

    root = attachments.resolve()
    files: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for raw_relative in relative_paths:
        relative = PurePosixPath(str(raw_relative).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ArchiveError("answer attachment path is unsafe")
        source = (root / Path(*relative.parts)).resolve()
        if not source.is_relative_to(root):
            raise ArchiveError("answer attachment path escapes its configured directory")
        if not source.is_file():
            raise ArchiveError(
                "a referenced answer attachment is missing: " + relative.as_posix()
            )
        member = ATTACHMENTS_PREFIX + relative.as_posix()
        canonical = _canonical_member_name(member)
        if canonical not in seen:
            files.append((source, member))
            seen.add(canonical)
    return files


def create_backup_archive(
    database: Path,
    materials: Path,
    destination_dir: Path,
    now: datetime | None = None,
    keep: int = 5,
    *,
    attachments: Path | None = None,
    notes: list[tuple[Path, str]] | None = None,
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
        note_files = notes if notes is not None else managed_note_files(source_database)
        files = [
            (snapshot, DATABASE_MEMBER),
            *_tree_files(materials, MATERIALS_PREFIX, exclude_ocr_cache=True),
            *(
                managed_attachment_files(snapshot, attachments)
                if attachments is not None
                else []
            ),
            *note_files,
        ]
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
            "excluded": [
                "ai-auth",
                "logs",
                "service.pid",
                "backups",
                "ocr-cache",
                "search-index",
                "appearance-preferences",
            ],
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


def _canonical_member_name(raw_name: str) -> str:
    return "/".join(
        unicodedata.normalize("NFC", part).casefold()
        for part in PurePosixPath(raw_name).parts
    )


def _validated_member_name(raw_name: str) -> str:
    path = PurePosixPath(raw_name)
    if (
        not raw_name
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in raw_name
        or path.as_posix() != raw_name
    ):
        raise ArchiveError(f"unsafe archive member: {raw_name}")
    for part in path.parts:
        normalized = unicodedata.normalize("NFC", part)
        if (
            normalized != part
            or part.rstrip(" .") != part
            or ":" in part
            or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
        ):
            raise ArchiveError(f"unsafe archive member: {raw_name}")
    name = path.as_posix()
    if name in (MANIFEST_MEMBER, DATABASE_MEMBER):
        return name
    if any(
        name.startswith(prefix) and len(path.parts) > 1
        for prefix in (MATERIALS_PREFIX, ATTACHMENTS_PREFIX, NOTES_PREFIX)
    ):
        return name
    raise ArchiveError(f"unexpected archive member: {raw_name}")


def _read_member_limited(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    limit: int,
) -> bytes:
    content = bytearray()
    with archive.open(info) as source:
        while chunk := source.read(min(1024 * 1024, limit + 1 - len(content))):
            content.extend(chunk)
            if len(content) > limit:
                raise ArchiveError(f"backup member is too large: {info.filename}")
    return bytes(content)


def _load_manifest(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict:
    try:
        manifest = json.loads(
            _read_member_limited(
                archive,
                info,
                MAX_ARCHIVE_MANIFEST_BYTES,
            ).decode("utf-8")
        )
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveError("backup manifest is missing or invalid") from error
    if manifest.get("format_version") not in SUPPORTED_ARCHIVE_FORMAT_VERSIONS:
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
    try:
        archive_file = zipfile.ZipFile(source)
    except zipfile.BadZipFile as error:
        raise ArchiveError("backup is not a valid ZIP archive") from error
    with archive_file as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveError("backup contains too many files")
        total_size = 0
        names: list[str] = []
        canonical_names: set[str] = set()
        info_by_name: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            name = _validated_member_name(info.filename)
            if info.is_dir() or info.flag_bits & 0x1:
                raise ArchiveError(f"unsupported archive member: {name}")
            if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ArchiveError(f"backup member is too large: {name}")
            total_size += info.file_size
            if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                raise ArchiveError("backup expands beyond the allowed total size")
            if (
                info.file_size >= MIN_COMPRESSION_RATIO_CHECK_BYTES
                and info.file_size
                > max(info.compress_size, 1) * MAX_ARCHIVE_COMPRESSION_RATIO
            ):
                raise ArchiveError(f"suspicious compression ratio: {name}")
            canonical = _canonical_member_name(name)
            if canonical in canonical_names:
                raise ArchiveError("backup contains colliding file names")
            canonical_names.add(canonical)
            names.append(name)
            info_by_name[name] = info
        if len(names) != len(set(names)):
            raise ArchiveError("backup contains duplicate file names")
        manifest_info = info_by_name.get(MANIFEST_MEMBER)
        if manifest_info is None:
            raise ArchiveError("backup manifest is missing or invalid")
        manifest = _load_manifest(archive, manifest_info)
        expected: dict[str, dict] = {}
        expected_canonical: set[str] = set()
        for item in manifest["files"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ArchiveError("backup manifest file list is invalid")
            member = _validated_member_name(item["path"])
            canonical = _canonical_member_name(member)
            if member in expected or canonical in expected_canonical:
                raise ArchiveError("backup manifest contains colliding file names")
            if (
                not isinstance(item.get("size"), int)
                or isinstance(item.get("size"), bool)
                or item["size"] < 0
                or item["size"] > MAX_ARCHIVE_MEMBER_BYTES
                or not isinstance(item.get("sha256"), str)
                or len(item["sha256"]) != 64
                or any(character not in "0123456789abcdef" for character in item["sha256"])
            ):
                raise ArchiveError(f"backup manifest metadata is invalid: {member}")
            expected[member] = item
            expected_canonical.add(canonical)
        archived_files = set(names) - {MANIFEST_MEMBER}
        if set(expected) != archived_files or DATABASE_MEMBER not in expected:
            raise ArchiveError("backup contents do not match the manifest")
        for member, metadata in expected.items():
            info = info_by_name[member]
            if info.file_size != metadata["size"]:
                raise ArchiveError(f"backup size check failed: {member}")
            digest = hashlib.sha256()
            size = 0
            with archive.open(info) as member_source:
                for chunk in iter(lambda: member_source.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > metadata["size"]:
                        raise ArchiveError(f"backup size check failed: {member}")
                    digest.update(chunk)
            if size != metadata["size"]:
                raise ArchiveError(f"backup size check failed: {member}")
            if digest.hexdigest() != metadata["sha256"]:
                raise ArchiveError(f"backup hash check failed: {member}")
        return manifest


def restore_backup_archive(
    archive_path: Path,
    runtime_data: Path,
    *,
    replace: bool = False,
    note_destination: Path | None = None,
) -> dict:
    manifest = inspect_backup_archive(archive_path)
    runtime_root = runtime_data.resolve()
    target_database = runtime_root / "learning-flow-coach.db"
    target_materials = runtime_root / "materials"
    target_attachments = runtime_root / "answer-attachments"
    if not replace and (
        target_database.exists() or target_materials.exists() or target_attachments.exists()
    ):
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
                if member == DATABASE_MEMBER:
                    destination = staging / "learning-flow-coach.db"
                else:
                    destination = staging / Path(*PurePosixPath(member).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as target:
                    digest = hashlib.sha256()
                    size = 0
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        size += len(chunk)
                        if size > item["size"]:
                            raise ArchiveError(f"backup size check failed: {member}")
                        digest.update(chunk)
                        target.write(chunk)
                    if size != item["size"] or digest.hexdigest() != item["sha256"]:
                        raise ArchiveError(f"backup changed during restore: {member}")

        staged_database = staging / "learning-flow-coach.db"
        staged_materials = staging / "materials"
        staged_attachments = staging / "answer-attachments"
        staged_notes = staging / "notes"
        _validate_database(staged_database)
        staged_materials.mkdir(exist_ok=True)
        staged_attachments.mkdir(exist_ok=True)

        note_targets: list[tuple[Path, Path]] = []
        if staged_notes.is_dir():
            if note_destination is None:
                raise ArchiveError("backup contains Obsidian notes; choose a destination vault")
            resolved_vault = note_destination.expanduser().resolve()
            if not resolved_vault.is_dir():
                raise ArchiveError("note destination vault does not exist")
            for source in sorted(staged_notes.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(staged_notes)
                target = (resolved_vault / relative).resolve()
                if not target.is_relative_to(resolved_vault):
                    raise ArchiveError("note restore path escapes the destination vault")
                if target.exists() and _file_digest(target) != _file_digest(source):
                    raise ArchiveError(
                        "note already exists with different content: "
                        f"{relative.as_posix()}"
                    )
                note_targets.append((source, target))

        if note_destination is not None:
            _set_obsidian_vault(staged_database, note_destination.expanduser().resolve())

        runtime_root.mkdir(parents=True, exist_ok=True)
        rollback_id = uuid4().hex
        old_database = runtime_root / f".restore-old-{rollback_id}.db"
        old_materials = runtime_root / f".restore-old-materials-{rollback_id}"
        old_attachments = runtime_root / f".restore-old-attachments-{rollback_id}"
        database_moved = False
        materials_moved = False
        attachments_moved = False
        created_notes: list[Path] = []
        try:
            if target_database.exists():
                target_database.replace(old_database)
                database_moved = True
            if target_materials.exists():
                target_materials.replace(old_materials)
                materials_moved = True
            if target_attachments.exists():
                target_attachments.replace(old_attachments)
                attachments_moved = True
            staged_database.replace(target_database)
            staged_materials.replace(target_materials)
            staged_attachments.replace(target_attachments)
            for source, target in note_targets:
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary_note = target.parent / f".{target.name}.{rollback_id}.tmp"
                shutil.copy2(source, temporary_note)
                temporary_note.replace(target)
                created_notes.append(target)
        except OSError as error:
            target_database.unlink(missing_ok=True)
            if target_materials.exists():
                shutil.rmtree(target_materials)
            if target_attachments.exists():
                shutil.rmtree(target_attachments)
            for created_note in created_notes:
                created_note.unlink(missing_ok=True)
            if database_moved:
                old_database.replace(target_database)
            if materials_moved:
                old_materials.replace(target_materials)
            if attachments_moved:
                old_attachments.replace(target_attachments)
            raise ArchiveError("restore failed and existing data was rolled back") from error
        old_database.unlink(missing_ok=True)
        if old_materials.exists():
            shutil.rmtree(old_materials)
        if old_attachments.exists():
            shutil.rmtree(old_attachments)
    return manifest


def _set_obsidian_vault(database: Path, vault: Path) -> None:
    try:
        with closing(sqlite3.connect(database)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "select name from sqlite_master where type = 'table'"
                )
            }
            if "app_settings" not in tables:
                return
            connection.execute(
                "insert into app_settings (key, value) values ('obsidian_vault_path', ?) "
                "on conflict(key) do update set value = excluded.value",
                (str(vault),),
            )
            connection.commit()
    except sqlite3.Error as error:
        raise ArchiveError("cannot update the restored Obsidian vault path") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumina local data archive")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--database", type=Path, required=True)
    create_parser.add_argument("--materials", type=Path, required=True)
    create_parser.add_argument("--attachments", type=Path)
    create_parser.add_argument("--destination", type=Path, required=True)
    create_parser.add_argument("--keep", type=int, default=5)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--archive", type=Path, required=True)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--runtime-data", type=Path, required=True)
    restore_parser.add_argument("--replace", action="store_true")
    restore_parser.add_argument("--note-destination", type=Path)
    restore_parser.add_argument("--confirm", required=True)

    arguments = parser.parse_args()
    if arguments.command == "create":
        result = create_backup_archive(
            arguments.database,
            arguments.materials,
            arguments.destination,
            keep=arguments.keep,
            attachments=arguments.attachments,
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
                note_destination=arguments.note_destination,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
