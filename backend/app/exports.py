from datetime import date
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AiInteractionKind,
    Chapter,
    Course,
    DailyRecord,
    Exercise,
    MistakeStatus,
    MistakeType,
    Section,
    SectionStatus,
)
from app.notes import NotePathError, get_vault_path, read_section_note
from app.schemas import ExportContentType

SECTION_STATUS_LABELS = {
    SectionStatus.NOT_STARTED: "未开始",
    SectionStatus.IN_PROGRESS: "进行中",
    SectionStatus.COMPLETED: "已完成",
}
MISTAKE_TYPE_LABELS = {
    MistakeType.CONCEPT: "概念理解",
    MistakeType.FORMULA_CONDITION: "公式条件",
    MistakeType.DERIVATION: "推导步骤",
    MistakeType.CALCULATION: "计算",
    MistakeType.QUESTION_UNDERSTANDING: "题意理解",
    MistakeType.EXPRESSION: "表达",
    MistakeType.CANNOT_SOLVE: "不会做",
    MistakeType.OTHER: "其他",
}
MISTAKE_STATUS_LABELS = {
    MistakeStatus.UNRESOLVED: "未解决",
    MistakeStatus.UNDERSTOOD: "已理解",
}
AI_INTERACTION_LABELS = {
    AiInteractionKind.RECALL_REVIEW: "闭卷回顾评阅",
    AiInteractionKind.RECONSTRUCTION_REVIEW: "主动重构评阅",
}
CONTENT_LABELS: dict[ExportContentType, str] = {
    "outline": "课程大纲",
    "daily_records": "每日学习记录",
    "ai_reviews": "AI 评阅",
    "exercises": "练习与批改",
    "mistakes": "错题",
    "notes": "小节笔记",
}
CONTENT_ORDER: tuple[ExportContentType, ...] = (
    "outline",
    "daily_records",
    "ai_reviews",
    "exercises",
    "mistakes",
    "notes",
)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = "".join(
        "_" if character in '<>:"/\\|?*' or ord(character) < 32 else character
        for character in _one_line(value)
    ).strip(" .")
    if not cleaned:
        cleaned = fallback
    if cleaned.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned[:100]


def _append_text(lines: list[str], title: str, value: str) -> None:
    if value.strip():
        lines.extend((f"## {title}", "", value.strip(), ""))


def _course_overview(course: Course) -> str:
    lines = [f"# {course.name}", ""]
    _append_text(lines, "课程描述", course.description)
    _append_text(lines, "学习目标", course.learning_goal)
    lines.extend(("## 课程大纲", ""))
    if not course.chapters:
        lines.extend(("暂无章节。", ""))
    for chapter_index, chapter in enumerate(course.chapters, start=1):
        lines.append(f"- 第 {chapter_index} 章：{chapter.title}")
        for section_index, section in enumerate(chapter.sections, start=1):
            status = SECTION_STATUS_LABELS[section.status]
            lines.append(f"  - {chapter_index}.{section_index} {section.title}（{status}）")
    lines.append("")
    return "\n".join(lines)


def _daily_record_markdown(record: DailyRecord, section: Section) -> str:
    completion = "已完成" if record.is_completed else "未完成"
    lines = [
        f"# {record.study_date.isoformat()} 学习记录",
        "",
        f"- 小节：{section.title}",
        f"- 当日状态：{completion}",
        "",
    ]
    _append_text(lines, "上次学习", record.recall_last_learned)
    _append_text(lines, "核心概念", record.recall_core_concepts)
    _append_text(lines, "已经清楚", record.recall_clear_parts)
    _append_text(lines, "学习范围", record.study_material_scope)
    _append_text(lines, "核心问题", record.reconstruct_problem)
    _append_text(lines, "主要收获", record.reconstruct_main_learning)
    _append_text(lines, "定义与推导", record.reconstruct_math)
    questions = record.preview_question_set
    if questions is not None:
        values = [
            question.strip()
            for question in (
                questions.question_1,
                questions.question_2,
                questions.question_3,
            )
            if question.strip()
        ]
        if values:
            lines.extend(("## 明日预习问题", ""))
            lines.extend(f"- {question}" for question in values)
            lines.append("")
    return "\n".join(lines)


def _ai_reviews_markdown(record: DailyRecord, section: Section) -> str:
    lines = [
        f"# {record.study_date.isoformat()} AI 评阅",
        "",
        f"- 小节：{section.title}",
        "",
    ]
    for interaction_index, interaction in enumerate(record.ai_interactions, start=1):
        title = AI_INTERACTION_LABELS[interaction.kind]
        lines.extend((f"## {interaction_index}. {title}", ""))
        _append_text(lines, "提示词", interaction.prompt_text)
        _append_text(lines, "AI 反馈", interaction.feedback_text)
    return "\n".join(lines)


def _exercise_markdown(
    record: DailyRecord,
    section: Section,
    exercise: Exercise,
    exercise_index: int,
) -> str:
    lines = [
        f"# {record.study_date.isoformat()} 练习 {exercise_index}",
        "",
        f"- 小节：{section.title}",
        "",
    ]
    _append_text(lines, "出题提示词", exercise.generation_prompt)
    _append_text(lines, "AI 题目", exercise.ai_questions)
    _append_text(lines, "我的答案", exercise.user_answers)
    _append_text(lines, "批改提示词", exercise.grading_prompt)
    _append_text(lines, "AI 批改", exercise.ai_feedback)
    return "\n".join(lines)


def _mistakes_markdown(section: Section) -> str | None:
    lines = [f"# {section.title}错题", ""]
    mistake_count = 0
    for record in section.daily_records:
        for exercise_index, exercise in enumerate(record.exercises, start=1):
            for mistake_index, mistake in enumerate(exercise.mistakes, start=1):
                mistake_count += 1
                lines.extend(
                    (
                        f"## {record.study_date.isoformat()} · 练习 {exercise_index} · "
                        f"错题 {mistake_index}",
                        "",
                        f"- 错误类型：{MISTAKE_TYPE_LABELS[mistake.error_type]}",
                        f"- 状态：{MISTAKE_STATUS_LABELS[mistake.status]}",
                        "",
                    )
                )
                _append_text(lines, "原题", mistake.original_question)
                _append_text(lines, "我的答案", mistake.user_answer)
                _append_text(lines, "错误内容", mistake.error_content)
                _append_text(lines, "正确思路", mistake.correct_approach)
                _append_text(lines, "原因分析", mistake.cause_analysis)
    return "\n".join(lines) if mistake_count else None


def _load_courses(session: Session, course_ids: list[int]) -> list[Course]:
    return list(
        session.scalars(
            select(Course)
            .where(Course.id.in_(course_ids))
            .options(
                selectinload(Course.chapters)
                .selectinload(Chapter.sections)
                .selectinload(Section.daily_records)
                .selectinload(DailyRecord.ai_interactions),
                selectinload(Course.chapters)
                .selectinload(Chapter.sections)
                .selectinload(Section.daily_records)
                .selectinload(DailyRecord.exercises)
                .selectinload(Exercise.mistakes),
                selectinload(Course.chapters)
                .selectinload(Chapter.sections)
                .selectinload(Section.daily_records)
                .selectinload(DailyRecord.preview_question_set),
            )
            .order_by(Course.id)
        )
    )


def build_markdown_archive(
    session: Session,
    course_ids: list[int],
    content_types: set[ExportContentType],
) -> bytes:
    courses = _load_courses(session, course_ids)
    found_ids = {course.id for course in courses}
    missing_ids = [course_id for course_id in course_ids if course_id not in found_ids]
    if missing_ids:
        raise ValueError(f"课程不存在：{', '.join(str(course_id) for course_id in missing_ids)}")

    warnings: list[str] = []
    note_export_enabled = "notes" in content_types and get_vault_path(session) is not None
    if "notes" in content_types and not note_export_enabled:
        warnings.append("未配置 Obsidian Vault，小节笔记未导出。")

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for course_index, course in enumerate(courses, start=1):
            course_directory = (
                f"{course_index:02d}-{_safe_segment(course.name, f'课程-{course.id}')}"
            )
            if "outline" in content_types:
                archive.writestr(
                    f"{course_directory}/课程概览.md",
                    _course_overview(course),
                )

            for chapter_index, chapter in enumerate(course.chapters, start=1):
                chapter_directory = (
                    f"{course_directory}/"
                    f"{chapter_index:02d}-{_safe_segment(chapter.title, f'章节-{chapter.id}')}"
                )
                for section_index, section in enumerate(chapter.sections, start=1):
                    section_directory = (
                        f"{chapter_directory}/"
                        f"{section_index:02d}-{_safe_segment(section.title, f'小节-{section.id}')}"
                    )
                    for record in section.daily_records:
                        record_date = record.study_date.isoformat()
                        if "daily_records" in content_types:
                            archive.writestr(
                                f"{section_directory}/学习记录/{record_date}.md",
                                _daily_record_markdown(record, section),
                            )
                        if "ai_reviews" in content_types and record.ai_interactions:
                            archive.writestr(
                                f"{section_directory}/AI评阅/{record_date}.md",
                                _ai_reviews_markdown(record, section),
                            )
                        if "exercises" in content_types:
                            for exercise_index, exercise in enumerate(record.exercises, start=1):
                                archive.writestr(
                                    f"{section_directory}/练习与批改/"
                                    f"{record_date}-练习{exercise_index:02d}.md",
                                    _exercise_markdown(
                                        record,
                                        section,
                                        exercise,
                                        exercise_index,
                                    ),
                                )

                    if "mistakes" in content_types:
                        mistake_content = _mistakes_markdown(section)
                        if mistake_content is not None:
                            archive.writestr(
                                f"{section_directory}/错题.md",
                                mistake_content,
                            )

                    if note_export_enabled:
                        try:
                            note_content, _, modified_at_ns = read_section_note(session, section)
                        except NotePathError as error:
                            warnings.append(
                                f"{course.name} / {chapter.title} / {section.title}：{error}"
                            )
                        else:
                            if modified_at_ns is not None:
                                archive.writestr(
                                    f"{section_directory}/小节笔记.md",
                                    note_content,
                                )

        manifest_lines = [
            "# 导出说明",
            "",
            f"- 生成日期：{date.today().isoformat()}",
            f"- 课程：{'、'.join(course.name for course in courses)}",
            "- 内容："
            + "、".join(
                CONTENT_LABELS[content_type]
                for content_type in CONTENT_ORDER
                if content_type in content_types
            ),
            "",
            "目录按课程、章节和小节组织；未产生内容的分类不会创建空文件。",
            "",
        ]
        if warnings:
            manifest_lines.extend(("## 未导出的内容", ""))
            manifest_lines.extend(f"- {warning}" for warning in warnings)
            manifest_lines.append("")
        archive.writestr("导出说明.md", "\n".join(manifest_lines))

    return output.getvalue()
