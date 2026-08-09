import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.ai_output_validation import AiOutputValidationError
from app.ai_preferences import codex_preference, gemini_cli_model, gemini_preference
from app.ai_providers import AiProviderError, AiProviderResult, AiService
from app.markdown import normalize_ai_markdown
from app.materials import MaterialEvidence, MaterialReference, retrieve_material_evidence
from app.models import (
    AiProvider,
    AiRun,
    AiRunStatus,
    AiRunTask,
    AppSetting,
    Chapter,
    ChapterMemory,
    Course,
    CourseMemory,
    DailyRecord,
    Exercise,
    MaterialContextSession,
    Section,
    SectionMemory,
    SectionStatus,
)
from app.notes import NotePathError, read_section_note

HANDOFF_FIELDS = (
    "confirmed_points",
    "corrections",
    "key_concepts",
    "key_formulas",
    "unresolved_points",
    "error_patterns",
    "source_refs",
)

ACTIVE_AI_TASKS: dict[int, asyncio.Task[Any]] = {}


def cancel_active_ai_run(run_id: int) -> bool:
    task = ACTIVE_AI_TASKS.get(run_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True

SOURCE_REFERENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "material_id": {"type": "integer", "minimum": 1},
        "chunk_positions": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "integer", "minimum": 1},
        },
        "evidence_summary": {"type": "string"},
    },
    "required": ["material_id", "chunk_positions", "evidence_summary"],
    "additionalProperties": False,
}

HANDOFF_SCHEMA = {
    "type": "object",
    "properties": {
        **{
            field: {"type": "array", "items": {"type": "string"}}
            for field in HANDOFF_FIELDS
            if field != "source_refs"
        },
        "source_refs": {"type": "array", "items": SOURCE_REFERENCE_SCHEMA},
    },
    "required": list(HANDOFF_FIELDS),
    "additionalProperties": False,
}

TEXT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "display_markdown": {"type": "string"},
        "handoff": HANDOFF_SCHEMA,
    },
    "required": ["display_markdown", "handoff"],
    "additionalProperties": False,
}

GUIDED_QUESTIONS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": ["q1", "q2", "q3"]},
                    "question_markdown": {"type": "string"},
                    "focus": {"type": "string"},
                },
                "required": ["id", "question_markdown", "focus"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["questions"],
    "additionalProperties": False,
}

GUIDED_REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": ["q1", "q2", "q3"]},
                    "verdict": {
                        "type": "string",
                        "enum": ["correct", "partial", "incorrect"],
                    },
                    "feedback_markdown": {"type": "string"},
                },
                "required": ["id", "verdict", "feedback_markdown"],
                "additionalProperties": False,
            },
        },
        "display_markdown": {"type": "string"},
        "handoff": HANDOFF_SCHEMA,
    },
    "required": ["reviews", "display_markdown", "handoff"],
    "additionalProperties": False,
}

PREVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "handoff": HANDOFF_SCHEMA,
    },
    "required": ["questions", "handoff"],
    "additionalProperties": False,
}

EXERCISE_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
    },
    "required": ["id", "label"],
    "additionalProperties": False,
}

PRACTICE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "minItems": 12,
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "position": {"type": "integer", "minimum": 1, "maximum": 12},
                    "item_type": {
                        "type": "string",
                        "enum": [
                            "single_choice",
                            "multiple_choice",
                            "short_answer",
                            "derivation",
                            "proof",
                            "calculation",
                            "application",
                            "extension",
                        ],
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["basic", "intermediate", "challenge"],
                    },
                    "stem_markdown": {"type": "string"},
                    "options": {"type": "array", "items": EXERCISE_OPTION_SCHEMA},
                    "answer_key": {
                        "type": "object",
                        "properties": {
                            "selected_options": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "answer_markdown": {"type": "string"},
                        },
                        "required": ["selected_options", "answer_markdown"],
                        "additionalProperties": False,
                    },
                    "rubric_markdown": {"type": "string"},
                    "source_refs": {"type": "array", "items": SOURCE_REFERENCE_SCHEMA},
                },
                "required": [
                    "position",
                    "item_type",
                    "difficulty",
                    "stem_markdown",
                    "options",
                    "answer_key",
                    "rubric_markdown",
                    "source_refs",
                ],
                "additionalProperties": False,
            },
        },
        "handoff": HANDOFF_SCHEMA,
    },
    "required": ["items", "handoff"],
    "additionalProperties": False,
}

GRADING_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "minItems": 12,
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "position": {"type": "integer", "minimum": 1, "maximum": 12},
                    "verdict": {
                        "type": "string",
                        "enum": ["correct", "partial", "incorrect"],
                    },
                    "feedback_markdown": {"type": "string"},
                },
                "required": ["position", "verdict", "feedback_markdown"],
                "additionalProperties": False,
            },
        },
        "handoff": HANDOFF_SCHEMA,
    },
    "required": ["results", "handoff"],
    "additionalProperties": False,
}

MEMORY_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "core_concepts": {"type": "array", "items": {"type": "string"}},
        "key_methods": {"type": "array", "items": {"type": "string"}},
        "unresolved_questions": {"type": "array", "items": {"type": "string"}},
        "error_patterns": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "core_concepts",
        "key_methods",
        "unresolved_questions",
        "error_patterns",
    ],
    "additionalProperties": False,
}

MEMORY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "section_memory": MEMORY_ITEM_SCHEMA,
        "chapter_memory": MEMORY_ITEM_SCHEMA,
    },
    "required": ["section_memory", "chapter_memory"],
    "additionalProperties": False,
}

DAILY_SUMMARY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "display_markdown": {"type": "string"},
        "handoff": HANDOFF_SCHEMA,
        "section_memory": MEMORY_ITEM_SCHEMA,
        "chapter_memory": MEMORY_ITEM_SCHEMA,
    },
    "required": ["display_markdown", "handoff", "section_memory", "chapter_memory"],
    "additionalProperties": False,
}

RAW_MATERIAL_LIMITS = {
    AiRunTask.RECALL_QUESTIONS: 5,
    AiRunTask.RECALL_REVIEW: 5,
    AiRunTask.RECONSTRUCTION_QUESTIONS: 6,
    AiRunTask.RECONSTRUCTION_REVIEW: 6,
    AiRunTask.PRACTICE_GENERATION: 5,
    AiRunTask.EXERCISE_GRADING: 3,
    AiRunTask.PREVIEW_QUESTIONS: 3,
    AiRunTask.SECTION_NOTE_DRAFT: 10,
    AiRunTask.DAILY_SUMMARY: 3,
    AiRunTask.SECTION_MEMORY: 0,
}

CODEX_TASK_TIMEOUTS = {
    AiRunTask.PRACTICE_GENERATION: 480,
    AiRunTask.EXERCISE_GRADING: 480,
    AiRunTask.SECTION_NOTE_DRAFT: 720,
    AiRunTask.SECTION_MEMORY: 480,
    AiRunTask.DAILY_SUMMARY: 480,
}

TASK_LABELS = {
    AiRunTask.RECALL_QUESTIONS: "回顾定向问题",
    AiRunTask.RECALL_REVIEW: "回顾评阅",
    AiRunTask.RECONSTRUCTION_QUESTIONS: "重构定向问题",
    AiRunTask.RECONSTRUCTION_REVIEW: "重构检查",
    AiRunTask.PRACTICE_GENERATION: "练习生成",
    AiRunTask.EXERCISE_GRADING: "练习批改",
    AiRunTask.PREVIEW_QUESTIONS: "下次回顾问题",
    AiRunTask.SECTION_NOTE_DRAFT: "笔记整理",
    AiRunTask.SECTION_MEMORY: "记忆整理",
    AiRunTask.DAILY_SUMMARY: "今日摘要",
    AiRunTask.MATERIAL_CONTEXT: "材料读取",
    AiRunTask.COURSE_COMPLETION: "课程完成摘要",
}

UPSTREAM_TASKS = {
    AiRunTask.RECALL_QUESTIONS: set(),
    AiRunTask.RECALL_REVIEW: {AiRunTask.RECALL_QUESTIONS},
    AiRunTask.RECONSTRUCTION_QUESTIONS: {AiRunTask.RECALL_REVIEW},
    AiRunTask.RECONSTRUCTION_REVIEW: {
        AiRunTask.RECALL_REVIEW,
        AiRunTask.RECONSTRUCTION_QUESTIONS,
    },
    AiRunTask.PRACTICE_GENERATION: {
        AiRunTask.RECALL_REVIEW,
        AiRunTask.RECONSTRUCTION_REVIEW,
    },
    AiRunTask.EXERCISE_GRADING: {
        AiRunTask.RECALL_REVIEW,
        AiRunTask.RECONSTRUCTION_REVIEW,
        AiRunTask.PRACTICE_GENERATION,
    },
    AiRunTask.PREVIEW_QUESTIONS: {
        AiRunTask.RECALL_REVIEW,
        AiRunTask.RECONSTRUCTION_REVIEW,
        AiRunTask.PRACTICE_GENERATION,
        AiRunTask.EXERCISE_GRADING,
    },
    AiRunTask.SECTION_NOTE_DRAFT: set(),
    AiRunTask.DAILY_SUMMARY: {
        AiRunTask.RECALL_REVIEW,
        AiRunTask.RECONSTRUCTION_REVIEW,
        AiRunTask.PRACTICE_GENERATION,
        AiRunTask.EXERCISE_GRADING,
        AiRunTask.PREVIEW_QUESTIONS,
    },
}


@dataclass(frozen=True)
class TaskContext:
    text: str
    source_refs: list[MaterialReference]


def compact(value: str, limit: int = 1600) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return f"{value[:limit].rstrip()}…"


def list_text(values: list[str]) -> str:
    return "\n".join(f"- {value.strip()}" for value in values if value.strip())


def used_source_references(
    candidates: list[MaterialReference],
    payload: dict[str, Any],
) -> list[MaterialReference]:
    declared: list[Any] = []
    handoff = payload.get("handoff")
    if isinstance(handoff, dict):
        declared.extend(handoff.get("source_refs", []))
    for item in payload.get("items", []):
        if isinstance(item, dict):
            declared.extend(item.get("source_refs", []))
    if not declared:
        return []
    structured: set[tuple[int, int]] = set()
    legacy: list[str] = []
    for value in declared:
        if isinstance(value, dict):
            try:
                material_id = int(value.get("material_id"))
                positions = {int(position) for position in value.get("chunk_positions", [])}
            except (TypeError, ValueError):
                continue
            structured.update((material_id, position) for position in positions if position > 0)
        elif str(value).strip():
            legacy.append(str(value).lower())

    matched: list[MaterialReference] = []
    seen: set[tuple[int, str, int | None]] = set()
    for candidate in candidates:
        exact = (
            candidate.chunk_position is not None
            and (candidate.material_id, candidate.chunk_position) in structured
        )
        compatible = any(
            candidate.material_title.lower() in value
            or candidate.location.lower() in value
            for value in legacy
        )
        key = (candidate.material_id, candidate.content_hash, candidate.chunk_position)
        if (exact or compatible) and key not in seen:
            matched.append(candidate)
            seen.add(key)
    return matched


def ensure_course_memory(session: Session, course_id: int) -> CourseMemory:
    memory = session.scalar(select(CourseMemory).where(CourseMemory.course_id == course_id))
    if memory is None:
        memory = CourseMemory(course_id=course_id)
        session.add(memory)
        session.flush()
    return memory


def ensure_chapter_memory(session: Session, chapter_id: int) -> ChapterMemory:
    memory = session.scalar(select(ChapterMemory).where(ChapterMemory.chapter_id == chapter_id))
    if memory is None:
        memory = ChapterMemory(chapter_id=chapter_id)
        session.add(memory)
        session.flush()
    return memory


def ensure_section_memory(session: Session, section_id: int) -> SectionMemory:
    memory = session.scalar(select(SectionMemory).where(SectionMemory.section_id == section_id))
    if memory is None:
        memory = SectionMemory(section_id=section_id)
        session.add(memory)
        session.flush()
    return memory


def memory_block(title: str, memory: CourseMemory | ChapterMemory | SectionMemory) -> str:
    summary = memory.overview if isinstance(memory, CourseMemory) else memory.summary
    lines = [
        f"【{title}】",
        f"摘要：{summary or '暂无'}",
        f"核心概念：{memory.core_concepts or '暂无'}",
        f"关键方法：{memory.key_methods or '暂无'}",
        f"未解决问题：{memory.unresolved_questions or '暂无'}",
        f"常见错误：{memory.error_patterns or '暂无'}",
    ]
    if isinstance(memory, CourseMemory):
        lines.insert(2, f"自动课程脉络：{memory.generated_outline or '暂无'}")
    return "\n".join(lines)


def app_setting(session: Session, key: str) -> str:
    value = session.scalar(select(AppSetting.value).where(AppSetting.key == key))
    return value.strip() if value else ""


def completed_courses_context(session: Session, current_course_id: int) -> str:
    courses = list(
        session.scalars(
            select(Course)
            .where(Course.completed_at.is_not(None), Course.id != current_course_id)
            .order_by(Course.completed_at.desc(), Course.id.desc())
        )
    )
    if not courses:
        return "暂无"
    return "\n".join(
        f"- {course.name}：{compact(course.completion_summary or '已完成，尚未形成摘要', 700)}"
        for course in courses
    )


def previous_section_context(session: Session, record: DailyRecord) -> str:
    section = record.section
    rows = session.execute(
        select(Section.title, SectionMemory.summary)
        .join(SectionMemory, SectionMemory.section_id == Section.id)
        .where(
            Section.chapter_id == section.chapter_id,
            Section.status == SectionStatus.COMPLETED,
            or_(
                Section.position < section.position,
                and_(Section.position == section.position, Section.id < section.id),
            ),
            SectionMemory.summary != "",
        )
        .order_by(Section.position.desc(), Section.id.desc())
        .limit(3)
    ).all()
    if not rows:
        return "暂无"
    return "\n".join(f"- {title}：{compact(summary, 500)}" for title, summary in rows)


def previous_daily_context(session: Session, record: DailyRecord) -> str:
    records = list(
        session.scalars(
            select(DailyRecord)
            .where(
                DailyRecord.section_id == record.section_id,
                DailyRecord.study_date < record.study_date,
            )
            .order_by(DailyRecord.study_date.desc(), DailyRecord.id.desc())
            .limit(2)
        )
    )
    if not records:
        return "暂无"
    items: list[str] = []
    for item in records:
        summary = item.context_summary or "；".join(
            value
            for value in [
                item.recall_last_learned,
                item.recall_core_concepts,
                item.reconstruct_main_learning,
                item.reconstruct_math,
            ]
            if value.strip()
        )
        items.append(f"- {item.study_date}：{compact(summary or '未形成摘要', 900)}")
    return "\n".join(items)


def previous_preview_context(session: Session, record: DailyRecord) -> str:
    previous = previous_learning_record(session, record)
    if previous is None:
        return "暂无"
    heading = f"{previous.study_date} · {previous.section.title}"
    if previous.preview_question_set is None:
        return f"{heading}\n- 上次学习未生成衔接问题"
    questions = previous.preview_question_set
    values = [
        normalize_ai_markdown(value)
        for value in [questions.question_1, questions.question_2, questions.question_3]
    ]
    question_lines = "\n".join(f"- {value}" for value in values if value.strip())
    return f"{heading}\n{question_lines or '- 上次学习未生成衔接问题'}"


def previous_learning_record(session: Session, record: DailyRecord) -> DailyRecord | None:
    """Return the immediately preceding completed study in the same course."""
    return session.scalar(
        select(DailyRecord)
        .join(Section, DailyRecord.section_id == Section.id)
        .join(Chapter, Section.chapter_id == Chapter.id)
        .where(
            Chapter.course_id == record.section.chapter.course_id,
            DailyRecord.is_completed.is_(True),
            or_(
                DailyRecord.study_date < record.study_date,
                and_(
                    DailyRecord.study_date == record.study_date,
                    DailyRecord.id < record.id,
                ),
            ),
        )
        .options(
            joinedload(DailyRecord.preview_question_set),
            joinedload(DailyRecord.section),
        )
        .order_by(DailyRecord.study_date.desc(), DailyRecord.id.desc())
        .limit(1)
    )


def handoff_context(
    session: Session,
    record: DailyRecord,
    task: AiRunTask | None = None,
) -> str:
    allowed_tasks = UPSTREAM_TASKS.get(task) if task is not None else None
    runs = list(
        session.scalars(
            select(AiRun)
            .where(
                AiRun.daily_record_id == record.id,
                AiRun.status == AiRunStatus.COMPLETED,
                AiRun.handoff_json != "",
            )
            .order_by(AiRun.id)
        )
    )
    blocks: list[str] = []
    for run in runs:
        if allowed_tasks is not None and run.task not in allowed_tasks:
            continue
        try:
            payload = json.loads(run.handoff_json)
        except json.JSONDecodeError:
            continue
        lines: list[str] = []
        for field in HANDOFF_FIELDS:
            values = payload.get(field, [])
            if values:
                lines.append(f"{field}: {'；'.join(compact(str(value), 260) for value in values)}")
        if lines:
            blocks.append(f"[{TASK_LABELS.get(run.task, run.task.value)}]\n" + "\n".join(lines))
    include_manual = allowed_tasks is None or bool(
        {AiRunTask.RECALL_REVIEW, AiRunTask.RECONSTRUCTION_REVIEW} & allowed_tasks
    )
    for interaction in record.ai_interactions if include_manual else []:
        if interaction.feedback_text.strip():
            blocks.append(
                f"[手动{interaction.kind.value}]\n"
                f"feedback: {compact(interaction.feedback_text, 900)}"
            )
    include_exercises = allowed_tasks is None or bool(
        {AiRunTask.EXERCISE_GRADING, AiRunTask.PRACTICE_GENERATION} & allowed_tasks
    )
    for index, exercise in enumerate(record.exercises if include_exercises else [], start=1):
        details: list[str] = []
        if exercise.ai_feedback.strip():
            details.append(f"批改：{compact(exercise.ai_feedback, 1000)}")
        for mistake in exercise.mistakes:
            details.append(
                f"错题：{compact(mistake.error_content, 260)}；"
                f"原因：{compact(mistake.cause_analysis, 260)}；"
                f"正确思路：{compact(mistake.correct_approach, 260)}"
            )
        if details:
            blocks.append(f"[练习组 {index}]\n" + "\n".join(details))
    return "\n\n".join(blocks) or "暂无"


def previous_material_records(session: Session, record: DailyRecord) -> list[DailyRecord]:
    return list(
        session.scalars(
            select(DailyRecord)
            .where(
                DailyRecord.section_id == record.section_id,
                DailyRecord.study_date < record.study_date,
            )
            .order_by(DailyRecord.study_date.desc(), DailyRecord.id.desc())
            .limit(2)
        )
    )


def upstream_source_reference_keys(
    session: Session,
    record: DailyRecord,
    task: AiRunTask,
) -> set[tuple[int, str, str]]:
    allowed_tasks = UPSTREAM_TASKS.get(task, set())
    if not allowed_tasks:
        return set()
    keys: set[tuple[int, str, str]] = set()
    runs = session.scalars(
        select(AiRun).where(
            AiRun.daily_record_id == record.id,
            AiRun.status == AiRunStatus.COMPLETED,
            AiRun.task.in_(allowed_tasks),
            AiRun.source_refs_json != "",
        )
    )
    for run in runs:
        try:
            references = json.loads(run.source_refs_json)
        except json.JSONDecodeError:
            continue
        for reference in references:
            keys.add(
                (
                    int(reference["material_id"]),
                    str(reference["content_hash"]),
                    str(reference["location"]),
                )
            )
    return keys


def material_query_for_task(record: DailyRecord, task: AiRunTask) -> str:
    task_fields = {
        AiRunTask.RECALL_QUESTIONS: [record.recall_last_learned],
        AiRunTask.RECALL_REVIEW: [record.recall_last_learned, record.recall_core_concepts],
        AiRunTask.RECONSTRUCTION_QUESTIONS: [record.reconstruct_main_learning],
        AiRunTask.RECONSTRUCTION_REVIEW: [
            record.reconstruct_problem,
            record.reconstruct_main_learning,
            record.reconstruct_math,
        ],
        AiRunTask.PRACTICE_GENERATION: [
            record.reconstruct_main_learning,
            record.reconstruct_math,
            record.reconstruct_problem,
            "例题 练习题 思考题 示例 exercise problem example",
        ],
        AiRunTask.EXERCISE_GRADING: [
            record.reconstruct_main_learning,
            record.reconstruct_math,
            *[exercise.ai_questions for exercise in record.exercises],
        ],
        AiRunTask.PREVIEW_QUESTIONS: [
            record.reconstruct_main_learning,
            record.reconstruct_math,
            *[exercise.ai_feedback for exercise in record.exercises],
        ],
        AiRunTask.SECTION_NOTE_DRAFT: [
            record.reconstruct_problem,
            record.reconstruct_main_learning,
            record.reconstruct_math,
        ],
        AiRunTask.DAILY_SUMMARY: [record.reconstruct_main_learning, record.reconstruct_math],
    }
    return "\n".join([record.study_material_scope, *task_fields.get(task, [])])


def build_task_context(
    session: Session,
    record: DailyRecord,
    task: AiRunTask = AiRunTask.RECALL_REVIEW,
    *,
    include_material_evidence: bool = True,
) -> TaskContext:
    course = record.section.chapter.course
    chapter = record.section.chapter
    course_memory = ensure_course_memory(session, course.id)
    chapter_memory = ensure_chapter_memory(session, chapter.id)
    section_memory = ensure_section_memory(session, record.section_id)
    if task in {AiRunTask.RECALL_QUESTIONS, AiRunTask.RECALL_REVIEW}:
        previous = previous_learning_record(session, record)
        source_records = [previous] if previous is not None else []
    else:
        source_records = None
    upstream_refs = upstream_source_reference_keys(session, record, task)
    material_limit = RAW_MATERIAL_LIMITS.get(task, 0)
    if upstream_refs:
        material_limit = (
            0
            if task == AiRunTask.DAILY_SUMMARY
            else max(1, material_limit - len(upstream_refs))
        )
    evidence = (
        retrieve_material_evidence(
            session,
            record,
            material_query_for_task(record, task),
            max_chunks=material_limit,
            source_records=source_records,
            excluded_refs=upstream_refs,
        )
        if include_material_evidence
        else MaterialEvidence("", [])
    )
    sections = [
        "【层级定位】",
        f"课程：{course.name}",
        f"章节：{chapter.title}",
        f"小节：{record.section.title}",
        f"长期学习目标：{course.learning_goal or '暂无'}",
        "",
        "【学习者背景】",
        app_setting(session, "learner_profile") or "暂无",
        "",
        "【已完成课程与知识背景】",
        completed_courses_context(session, course.id),
        "",
        memory_block("课程记忆（用户维护内容不会被自动覆盖）", course_memory),
        "",
        memory_block("章节记忆", chapter_memory),
        "",
        memory_block("当前小节记忆", section_memory),
        "",
        "【同章已完成的前置小节】",
        previous_section_context(session, record),
        "",
        "【最近两次学习摘要】",
        previous_daily_context(session, record),
        "",
        "【上次学习留下的回顾问题】",
        previous_preview_context(session, record),
        "",
        "【本次流程上游交接】",
        handoff_context(session, record, task),
    ]
    if evidence.text:
        sections.extend(["", evidence.text])
    return TaskContext("\n".join(sections).strip(), evidence.references)


def course_context(
    session: Session,
    record: DailyRecord,
    task: AiRunTask = AiRunTask.RECALL_REVIEW,
) -> str:
    return build_task_context(session, record, task).text


async def run_codex(
    session: Session,
    ai_service: AiService,
    *,
    task: AiRunTask,
    prompt: str,
    context_snapshot: str,
    course_id: int,
    section_id: int | None,
    daily_record_id: int | None = None,
    exercise_id: int | None = None,
    output_schema: dict[str, Any] | None = None,
    source_refs: list[MaterialReference] | None = None,
    material_context_session: MaterialContextSession | None = None,
    existing_run: AiRun | None = None,
    payload_validator: Callable[[dict[str, Any]], None] | None = None,
) -> AiProviderResult:
    preference = codex_preference(session)
    if existing_run is None:
        conditions = [
            AiRun.task == task,
            AiRun.status == AiRunStatus.RUNNING,
        ]
        for column, value in (
            (AiRun.course_id, course_id),
            (AiRun.section_id, section_id),
            (AiRun.daily_record_id, daily_record_id),
            (AiRun.exercise_id, exercise_id),
        ):
            if value is not None:
                conditions.append(column == value)
        duplicate = session.scalar(select(AiRun).where(*conditions).limit(1))
        if duplicate is not None:
            raise AiProviderError("同一生成任务仍在运行，请等待完成或先取消")
    run = existing_run or AiRun(provider=AiProvider.CODEX, task=task)
    run.status = AiRunStatus.RUNNING
    run.course_id = course_id
    run.section_id = section_id
    run.daily_record_id = daily_record_id
    run.exercise_id = exercise_id
    run.material_context_session_id = (
        material_context_session.id if material_context_session is not None else None
    )
    run.material_revision = (
        material_context_session.revision if material_context_session is not None else 0
    )
    run.material_manifest_hash = (
        material_context_session.manifest_hash if material_context_session is not None else ""
    )
    run.model = preference.model
    run.reasoning_effort = preference.reasoning_effort
    run.context_snapshot = context_snapshot
    run.prompt_text = prompt
    run.source_refs_json = "[]"
    if existing_run is None:
        session.add(run)
    session.commit()
    current_task = asyncio.current_task()
    if current_task is not None:
        ACTIVE_AI_TASKS[run.id] = current_task
    try:
        provider_options: dict[str, Any] = {}
        if material_context_session is not None:
            provider_options["persistent"] = True
            provider_options["readable_roots"] = [Path(material_context_session.workspace_path)]
            if material_context_session.thread_id:
                provider_options.update(
                    {
                        "fork_thread_id": material_context_session.thread_id,
                        "fork_last_turn_id": material_context_session.anchor_turn_id,
                    }
                )
        try:
            result = await ai_service.codex.generate(
                prompt,
                output_schema,
                model=preference.model,
                reasoning_effort=preference.reasoning_effort,
                timeout_seconds=CODEX_TASK_TIMEOUTS.get(task, 300),
                **provider_options,
            )
        except AiProviderError as error:
            stale_material_thread = (
                material_context_session is not None
                and bool(material_context_session.thread_id)
                and "no rollout found for thread id" in str(error).lower()
            )
            if not stale_material_thread:
                raise
            material_context_session.thread_id = ""
            material_context_session.anchor_turn_id = ""
            material_context_session.change_kind = "recovery_pending"
            session.commit()
            provider_options.pop("fork_thread_id", None)
            provider_options.pop("fork_last_turn_id", None)
            result = await ai_service.codex.generate(
                prompt,
                output_schema,
                model=preference.model,
                reasoning_effort=preference.reasoning_effort,
                timeout_seconds=CODEX_TASK_TIMEOUTS.get(task, 300),
                **provider_options,
            )
        if output_schema is not None:
            payload = parse_structured_output(result.text)
            if payload_validator is not None:
                payload_validator(payload)
            result.payload = payload
            handoff = payload.get("handoff")
            if isinstance(handoff, dict):
                result.handoff = handoff
                run.handoff_json = json.dumps(handoff, ensure_ascii=False)
                used_references = used_source_references(source_refs or [], payload)
                result.source_refs = [reference.__dict__ for reference in used_references]
                run.source_refs_json = json.dumps(
                    result.source_refs,
                    ensure_ascii=False,
                )
            display_markdown = payload.get("display_markdown")
            if isinstance(display_markdown, str):
                result.text = display_markdown
    except asyncio.CancelledError:
        run.status = AiRunStatus.FAILED
        run.error_text = "生成任务已取消，可从原操作重新生成。"
        session.commit()
        raise
    except Exception as error:
        run.status = AiRunStatus.FAILED
        run.error_text = str(error)
        session.commit()
        raise
    finally:
        if current_task is not None and ACTIVE_AI_TASKS.get(run.id) is current_task:
            ACTIVE_AI_TASKS.pop(run.id, None)
    run.status = AiRunStatus.COMPLETED
    run.output_text = result.text
    run.model = result.model
    run.thread_id = result.thread_id
    if (
        material_context_session is not None
        and material_context_session.change_kind.endswith("_pending")
    ):
        material_context_session.thread_id = result.thread_id
        material_context_session.anchor_turn_id = result.turn_id
        material_context_session.change_kind = "ready"
    session.commit()
    return result


async def run_gemini(
    session: Session,
    ai_service: AiService,
    *,
    prompt: str,
    context_snapshot: str,
    course_id: int,
    section_id: int,
) -> AiProviderResult:
    preference = gemini_preference(session)
    selected_model = gemini_cli_model(preference.model, preference.reasoning_effort)
    run = AiRun(
        provider=AiProvider.GEMINI,
        task=AiRunTask.SECTION_NOTE_POLISH,
        status=AiRunStatus.RUNNING,
        course_id=course_id,
        section_id=section_id,
        model=selected_model,
        reasoning_effort=preference.reasoning_effort,
        context_snapshot=context_snapshot,
        prompt_text=prompt,
    )
    session.add(run)
    session.commit()
    current_task = asyncio.current_task()
    if current_task is not None:
        ACTIVE_AI_TASKS[run.id] = current_task
    try:
        result = await ai_service.gemini.generate(prompt, selected_model)
    except asyncio.CancelledError:
        run.status = AiRunStatus.FAILED
        run.error_text = "生成任务已取消，可从原操作重新生成。"
        session.commit()
        raise
    except AiProviderError as error:
        run.status = AiRunStatus.FAILED
        run.error_text = str(error)
        session.commit()
        raise
    finally:
        if current_task is not None and ACTIVE_AI_TASKS.get(run.id) is current_task:
            ACTIVE_AI_TASKS.pop(run.id, None)
    run.status = AiRunStatus.COMPLETED
    run.output_text = result.text
    run.model = result.model
    session.commit()
    return result


def parse_structured_output(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise AiOutputValidationError("AI 返回内容不符合约定的结构") from error
    if not isinstance(payload, dict):
        raise AiOutputValidationError("AI 返回内容不符合约定的结构")
    return payload


def daily_summary_source(session: Session, record: DailyRecord) -> str:
    sections: list[str] = []
    fields = [
        ("回顾", record.recall_last_learned),
        ("核心概念", record.recall_core_concepts),
        ("学习范围", record.study_material_scope),
        ("问题与目标", record.reconstruct_problem),
        ("主要内容", record.reconstruct_main_learning),
        ("定义与推导", record.reconstruct_math),
    ]
    sections.extend(f"{label}：{compact(value, 700)}" for label, value in fields if value.strip())
    for index, exercise in enumerate(record.exercises, start=1):
        if exercise.user_answers.strip() or exercise.ai_feedback.strip():
            sections.append(
                f"练习 {index}：题目 {compact(exercise.ai_questions, 500) or '未填写'}；"
                f"答案 {compact(exercise.user_answers, 500) or '未填写'}；"
                f"批改 {compact(exercise.ai_feedback, 500) or '暂无'}"
            )
        for mistake in exercise.mistakes:
            sections.append(
                "错题："
                f"{compact(mistake.error_content, 300)}；"
                f"原因 {compact(mistake.cause_analysis, 300)}；"
                f"正确思路 {compact(mistake.correct_approach, 300)}"
            )
    if record.preview_question_set is not None:
        questions = [
            record.preview_question_set.question_1,
            record.preview_question_set.question_2,
            record.preview_question_set.question_3,
        ]
        sections.append("下次回顾问题：" + "；".join(value for value in questions if value.strip()))
    handoffs = handoff_context(session, record)
    if handoffs != "暂无":
        sections.append(f"评阅交接：{compact(handoffs, 1600)}")
    return "\n".join(sections) or "本次学习未形成可摘要内容。"


def load_section_for_memory(session: Session, section_id: int) -> Section | None:
    return session.scalar(
        select(Section)
        .where(Section.id == section_id)
        .options(
            joinedload(Section.chapter).joinedload(Chapter.course),
            selectinload(Section.daily_records)
            .selectinload(DailyRecord.exercises)
            .selectinload(Exercise.mistakes),
            selectinload(Section.daily_records).selectinload(DailyRecord.ai_interactions),
            selectinload(Section.daily_records).joinedload(DailyRecord.preview_question_set),
        )
    )


def section_memory_source(session: Session, section: Section) -> str:
    records: list[str] = []
    for record in sorted(section.daily_records, key=lambda item: (item.study_date, item.id)):
        details = [
            record.context_summary
            or f"AI 摘要尚未生成，以下为原始记录：\n{daily_summary_source(session, record)}"
        ]
        for interaction in record.ai_interactions:
            if interaction.prompt_text.strip() or interaction.feedback_text.strip():
                details.append(
                    f"评阅：{compact(interaction.feedback_text or interaction.prompt_text, 1000)}"
                )
        records.append(f"日期：{record.study_date}\n" + "\n".join(details))
    try:
        note_content, _, _ = read_section_note(session, section)
    except NotePathError:
        note_content = ""
    note_block = compact(note_content, 50000) if note_content.strip() else "暂无最终笔记"
    records_block = "\n\n".join(records) or "暂无"
    return f"【全部学习记录】\n{records_block}\n\n【最终 Obsidian 笔记】\n{note_block}"


def apply_memory_payload(
    memory: ChapterMemory | SectionMemory,
    payload: dict[str, Any],
) -> None:
    memory.summary = normalize_ai_markdown(str(payload["summary"]))
    memory.core_concepts = normalize_ai_markdown(list_text(payload["core_concepts"]))
    memory.key_methods = normalize_ai_markdown(list_text(payload["key_methods"]))
    memory.unresolved_questions = normalize_ai_markdown(
        list_text(payload["unresolved_questions"])
    )
    memory.error_patterns = normalize_ai_markdown(list_text(payload["error_patterns"]))
    memory.version += 1


def rebuild_course_outline(session: Session, course: Course) -> str:
    lines: list[str] = []
    chapters = list(
        session.scalars(
            select(Chapter)
            .where(Chapter.course_id == course.id)
            .options(
                joinedload(Chapter.memory),
                selectinload(Chapter.sections).joinedload(Section.memory),
            )
            .order_by(Chapter.position, Chapter.id)
        ).unique()
    )
    for chapter in chapters:
        chapter_summary = chapter.memory.summary if chapter.memory is not None else ""
        heading = f"## {chapter.title}"
        lines.append(f"{heading}\n{compact(chapter_summary, 900)}" if chapter_summary else heading)
        for section in chapter.sections:
            if section.memory is not None and section.memory.summary:
                lines.append(f"- {section.title}：{compact(section.memory.summary, 500)}")
    return "\n".join(lines)


def apply_daily_summary_memory(
    session: Session,
    record: DailyRecord,
    payload: dict[str, Any],
) -> None:
    section_memory = ensure_section_memory(session, record.section_id)
    chapter_memory = ensure_chapter_memory(session, record.section.chapter_id)
    apply_memory_payload(section_memory, payload["section_memory"])
    apply_memory_payload(chapter_memory, payload["chapter_memory"])
    course_memory = ensure_course_memory(session, record.section.chapter.course_id)
    course_memory.generated_outline = rebuild_course_outline(session, record.section.chapter.course)
    course_memory.version += 1


async def refresh_section_memory(
    session: Session,
    ai_service: AiService,
    section_id: int,
) -> SectionMemory:
    section = load_section_for_memory(session, section_id)
    if section is None:
        raise ValueError("小节不存在")
    current = ensure_section_memory(session, section_id)
    chapter_memory = ensure_chapter_memory(session, section.chapter_id)
    source = section_memory_source(session, section)
    context = f"""课程：{section.chapter.course.name}
章节：{section.chapter.title}
小节：{section.title}
当前小节记忆：{current.summary or "暂无"}
当前章节记忆：{chapter_memory.summary or "暂无"}

{source}"""
    prompt = f"""请把以下学习成果压缩为可长期复用的小节记忆和章节记忆。
只使用提供的内容，不补充未经确认的事实。保留尚未解决的问题、错误模式、关键公式的成立条件。
章节记忆需要体现本小节对本章知识结构的增量，不要只重复小节摘要。
输出必须符合指定 JSON 结构。

{context}"""
    result = await run_codex(
        session,
        ai_service,
        task=AiRunTask.SECTION_MEMORY,
        prompt=prompt,
        context_snapshot=context,
        course_id=section.chapter.course_id,
        section_id=section.id,
        output_schema=MEMORY_OUTPUT_SCHEMA,
    )
    payload = result.payload or parse_structured_output(result.text)
    apply_memory_payload(current, payload["section_memory"])
    apply_memory_payload(chapter_memory, payload["chapter_memory"])

    course_memory = ensure_course_memory(session, section.chapter.course_id)
    course_memory.generated_outline = rebuild_course_outline(session, section.chapter.course)
    course_memory.version += 1
    session.commit()
    session.refresh(current)
    return current


def load_course_with_memories(session: Session, course_id: int) -> Course | None:
    return session.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            joinedload(Course.memory),
            selectinload(Course.chapters).joinedload(Chapter.memory),
            selectinload(Course.chapters).selectinload(Chapter.sections).joinedload(Section.memory),
        )
    )
