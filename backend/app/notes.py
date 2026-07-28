import os
import tempfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.file_names import safe_path_segment
from app.models import AppSetting, Chapter, Course, Section

OBSIDIAN_VAULT_KEY = "obsidian_vault_path"
NOTE_SEGMENT_MAX_LENGTH = 200


class NotePathError(ValueError):
    pass


class NoteConflictError(RuntimeError):
    pass


def _filesystem_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    raw_path = str(path)
    if raw_path.startswith("\\\\?\\"):
        return path
    if raw_path.startswith("\\\\"):
        return Path(f"\\\\?\\UNC\\{raw_path[2:]}")
    return Path(f"\\\\?\\{raw_path}")


@lru_cache(maxsize=256)
def _cached_note_text(path: str, modified_at_ns: int, size: int) -> str:
    del modified_at_ns, size
    return Path(path).read_text(encoding="utf-8")


def get_vault_path(session: Session) -> Path | None:
    setting = session.get(AppSetting, OBSIDIAN_VAULT_KEY)
    if setting is None or not setting.value.strip():
        return None
    return Path(setting.value)


def save_vault_path(session: Session, raw_path: str) -> Path:
    vault = Path(raw_path.strip()).expanduser()
    if not vault.is_absolute():
        raise NotePathError("Obsidian vault 路径必须是绝对路径")
    try:
        vault = vault.resolve(strict=True)
    except OSError as error:
        raise NotePathError("Obsidian vault 路径不存在或无法访问") from error
    if not vault.is_dir():
        raise NotePathError("Obsidian vault 路径必须指向文件夹")

    setting = session.get(AppSetting, OBSIDIAN_VAULT_KEY)
    if setting is None:
        session.add(AppSetting(key=OBSIDIAN_VAULT_KEY, value=str(vault)))
    else:
        setting.value = str(vault)
    session.commit()
    return vault


def _segment_collision(
    session: Session,
    model: type[Course] | type[Chapter] | type[Section],
    value: str,
    entity_id: int,
    parent_field: object | None = None,
    parent_id: int | None = None,
) -> bool:
    statement = select(model)
    if parent_field is not None:
        statement = statement.where(parent_field == parent_id)
    peers = session.scalars(statement)
    expected = safe_path_segment(value, "_", max_length=NOTE_SEGMENT_MAX_LENGTH).casefold()
    return any(
        item.id != entity_id
        and safe_path_segment(
            item.name if isinstance(item, Course) else item.title,
            "_",
            max_length=NOTE_SEGMENT_MAX_LENGTH,
        ).casefold()
        == expected
        for item in peers
    )


def assign_note_relative_path(session: Session, section: Section) -> str:
    course = section.chapter.course
    chapter = section.chapter
    course_segment = safe_path_segment(
        course.name,
        f"课程-{course.id}",
        max_length=NOTE_SEGMENT_MAX_LENGTH,
        suffix=f"--c{course.id}",
        force_suffix=_segment_collision(session, Course, course.name, course.id),
    )
    chapter_segment = safe_path_segment(
        chapter.title,
        f"章节-{chapter.id}",
        max_length=NOTE_SEGMENT_MAX_LENGTH,
        suffix=f"--h{chapter.id}",
        force_suffix=_segment_collision(
            session,
            Chapter,
            chapter.title,
            chapter.id,
            Chapter.course_id,
            chapter.course_id,
        ),
    )
    section_segment = safe_path_segment(
        section.title,
        f"小节-{section.id}",
        max_length=NOTE_SEGMENT_MAX_LENGTH,
        suffix=f"--s{section.id}",
        force_suffix=_segment_collision(
            session,
            Section,
            section.title,
            section.id,
            Section.chapter_id,
            section.chapter_id,
        ),
    )
    relative_path = f"{course_segment}/{chapter_segment}/{section_segment}.md"

    existing_paths = {
        path.casefold()
        for path in session.scalars(
            select(Section.note_relative_path).where(
                Section.id != section.id,
                Section.note_relative_path.is_not(None),
            )
        )
        if path
    }
    if relative_path.casefold() in existing_paths:
        section_segment = safe_path_segment(
            section.title,
            f"小节-{section.id}",
            max_length=NOTE_SEGMENT_MAX_LENGTH,
            suffix=f"--s{section.id}",
            force_suffix=True,
        )
        relative_path = f"{course_segment}/{chapter_segment}/{section_segment}.md"
    if relative_path.casefold() in existing_paths:
        raise NotePathError("无法为小节分配唯一的 Markdown 文件路径")

    section.note_relative_path = relative_path
    return relative_path


def _stored_note_path(section: Section) -> PurePosixPath:
    if not section.note_relative_path:
        raise NotePathError("小节笔记路径尚未初始化")
    relative_path = PurePosixPath(section.note_relative_path)
    if (
        relative_path.is_absolute()
        or len(relative_path.parts) != 3
        or relative_path.suffix.casefold() != ".md"
        or any(
            part in {"", ".", ".."}
            or safe_path_segment(part, "_", max_length=1000) != part
            for part in relative_path.parts
        )
    ):
        raise NotePathError("小节笔记路径配置无效")
    return relative_path


def section_note_paths(session: Session, section: Section) -> tuple[Path, Path, str]:
    vault = get_vault_path(session)
    if vault is None:
        raise NotePathError("请先在设置中配置 Obsidian vault 路径")
    try:
        vault = vault.resolve(strict=True)
    except OSError as error:
        raise NotePathError("已配置的 Obsidian vault 路径不存在或无法访问") from error

    if not section.note_relative_path:
        assign_note_relative_path(session, section)
        session.commit()
    relative_path = _stored_note_path(section)
    course_directory = (vault / relative_path.parts[0]).resolve(strict=False)
    chapter_directory = (course_directory / relative_path.parts[1]).resolve(strict=False)
    target = (chapter_directory / relative_path.parts[2]).resolve(strict=False)
    legacy_target = (course_directory / relative_path.parts[2]).resolve(strict=False)
    if (
        not course_directory.is_relative_to(vault)
        or not chapter_directory.is_relative_to(course_directory)
        or not target.is_relative_to(chapter_directory)
        or not legacy_target.is_relative_to(course_directory)
    ):
        raise NotePathError("笔记路径超出已配置的 Obsidian vault")
    return _filesystem_path(target), _filesystem_path(legacy_target), relative_path.as_posix()


def legacy_note_is_unambiguous(session: Session, section: Section) -> bool:
    course_id = section.chapter.course_id
    current_path = _stored_note_path(section)
    same_named_sections = session.scalars(
        select(Section)
        .join(Chapter)
        .where(Chapter.course_id == course_id, Section.id != section.id)
    )
    return not any(
        item.note_relative_path
        and PurePosixPath(item.note_relative_path).name.casefold()
        == current_path.name.casefold()
        for item in same_named_sections
    )


def note_source(session: Session, section: Section, target: Path, legacy_target: Path) -> Path:
    if target.exists() and legacy_target.exists():
        raise NotePathError("检测到新旧两份小节笔记，请先在 Obsidian 中确认保留哪一份")
    if target.exists():
        return target
    if legacy_target.exists():
        if not legacy_note_is_unambiguous(session, section):
            raise NotePathError("旧版笔记路径对应多个同名小节，无法自动迁移")
        return legacy_target
    return target


def read_section_note(session: Session, section: Section) -> tuple[str, str, int | None]:
    target, legacy_target, relative_path = section_note_paths(session, section)
    source = note_source(session, section, target, legacy_target)
    if not source.exists():
        return "", relative_path, None
    if not source.is_file():
        raise NotePathError("目标 Markdown 路径不是文件")
    try:
        metadata = source.stat()
        content = _cached_note_text(
            str(source),
            metadata.st_mtime_ns,
            metadata.st_size,
        )
        return content, relative_path, metadata.st_mtime_ns
    except OSError as error:
        raise NotePathError("无法读取 Obsidian Markdown 文件") from error


def write_section_note(
    session: Session,
    section: Section,
    content: str,
    expected_modified_at_ns: int | None,
    force_overwrite: bool,
) -> tuple[str, str, int]:
    target, legacy_target, relative_path = section_note_paths(session, section)
    source = note_source(session, section, target, legacy_target)
    current_modified_at_ns = source.stat().st_mtime_ns if source.exists() else None
    if current_modified_at_ns != expected_modified_at_ns and not force_overwrite:
        raise NoteConflictError("笔记在打开后被外部修改，请确认是否覆盖")

    temporary_name = ""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = target.parent.resolve(strict=True)
        vault = get_vault_path(session)
        if vault is None or not resolved_parent.is_relative_to(
            _filesystem_path(vault.resolve(strict=True))
        ):
            raise NotePathError("笔记目录超出已配置的 Obsidian vault")
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=resolved_parent,
            prefix=f".{target.stem}-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_name = temporary_file.name
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        Path(temporary_name).replace(target)
        _cached_note_text.cache_clear()
        if source == legacy_target:
            legacy_target.unlink(missing_ok=True)
    except NotePathError:
        raise
    except OSError as error:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise NotePathError("无法写入 Obsidian Markdown 文件") from error
    return content, relative_path, target.stat().st_mtime_ns
