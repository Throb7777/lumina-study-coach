import os
import tempfile
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, Chapter, Section

OBSIDIAN_VAULT_KEY = "obsidian_vault_path"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class NotePathError(ValueError):
    pass


class NoteConflictError(RuntimeError):
    pass


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


def validate_path_segment(value: str, label: str) -> None:
    if value in {"", ".", ".."}:
        raise NotePathError(f"{label}不能作为 Markdown 文件名")
    if value.endswith((" ", ".")):
        raise NotePathError(f"{label}不能以空格或句点结尾")
    if any(character in '<>:"/\\|?*' or ord(character) < 32 for character in value):
        raise NotePathError(f"{label}包含 Windows 文件名不支持的字符")
    if value.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise NotePathError(f"{label}是 Windows 保留文件名")


def section_note_paths(session: Session, section: Section) -> tuple[Path, Path, str]:
    vault = get_vault_path(session)
    if vault is None:
        raise NotePathError("请先在设置中配置 Obsidian vault 路径")
    try:
        vault = vault.resolve(strict=True)
    except OSError as error:
        raise NotePathError("已配置的 Obsidian vault 路径不存在或无法访问") from error

    course = section.chapter.course
    validate_path_segment(course.name, "课程名称")
    validate_path_segment(section.chapter.title, "章节标题")
    validate_path_segment(section.title, "小节标题")

    sibling_sections = session.scalars(
        select(Section).where(Section.chapter_id == section.chapter_id, Section.id != section.id)
    )
    if any(item.title.casefold() == section.title.casefold() for item in sibling_sections):
        raise NotePathError("同一章节存在同名小节，无法确定唯一 Markdown 文件")

    course_directory = (vault / course.name).resolve(strict=False)
    chapter_directory = (course_directory / section.chapter.title).resolve(strict=False)
    target = (chapter_directory / f"{section.title}.md").resolve(strict=False)
    legacy_target = (course_directory / f"{section.title}.md").resolve(strict=False)
    if (
        not course_directory.is_relative_to(vault)
        or not chapter_directory.is_relative_to(course_directory)
        or not target.is_relative_to(chapter_directory)
        or not legacy_target.is_relative_to(course_directory)
    ):
        raise NotePathError("笔记路径超出已配置的 Obsidian vault")
    return target, legacy_target, f"{course.name}/{section.chapter.title}/{section.title}.md"


def legacy_note_is_unambiguous(session: Session, section: Section) -> bool:
    course_id = section.chapter.course_id
    same_named_sections = session.scalars(
        select(Section)
        .join(Chapter)
        .where(Chapter.course_id == course_id, Section.id != section.id)
    )
    return not any(
        item.title.casefold() == section.title.casefold() for item in same_named_sections
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
        if vault is None or not resolved_parent.is_relative_to(vault.resolve(strict=True)):
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
