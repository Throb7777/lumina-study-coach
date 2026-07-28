import json
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.workflow import WORKFLOW_NODE_TITLES, WorkflowNodeKey


class Base(DeclarativeBase):
    pass


class SectionStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class WorkflowNodeStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class AiInteractionKind(StrEnum):
    RECALL_REVIEW = "recall_review"
    RECONSTRUCTION_REVIEW = "reconstruction_review"


class AiProvider(StrEnum):
    CODEX = "codex"
    GEMINI = "gemini"


class AiRunTask(StrEnum):
    RECALL_REVIEW = "recall_review"
    RECONSTRUCTION_REVIEW = "reconstruction_review"
    PRACTICE_GENERATION = "practice_generation"
    EXERCISE_GRADING = "exercise_grading"
    PREVIEW_QUESTIONS = "preview_questions"
    SECTION_NOTE_DRAFT = "section_note_draft"
    SECTION_NOTE_POLISH = "section_note_polish"
    SECTION_MEMORY = "section_memory"
    DAILY_SUMMARY = "daily_summary"
    MATERIAL_CONTEXT = "material_context"
    COURSE_COMPLETION = "course_completion"


class AiRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MaterialSourceType(StrEnum):
    PDF = "pdf"
    URL = "url"
    VIDEO = "video"


class MaterialStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"


class MaterialRefreshStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MaterialSessionStatus(StrEnum):
    PREPARING = "preparing"
    READY = "ready"
    FAILED = "failed"


class MistakeType(StrEnum):
    CONCEPT = "concept"
    FORMULA_CONDITION = "formula_condition"
    DERIVATION = "derivation"
    CALCULATION = "calculation"
    QUESTION_UNDERSTANDING = "question_understanding"
    EXPRESSION = "expression"
    CANNOT_SOLVE = "cannot_solve"
    OTHER = "other"


class MistakeStatus(StrEnum):
    UNRESOLVED = "unresolved"
    UNDERSTOOD = "understood"


class ExerciseItemType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    DERIVATION = "derivation"
    PROOF = "proof"
    CALCULATION = "calculation"
    APPLICATION = "application"
    EXTENSION = "extension"


class ExerciseDifficulty(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    CHALLENGE = "challenge"


class ExerciseResponseStatus(StrEnum):
    UNANSWERED = "unanswered"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    GRADED = "graded"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    learning_goal: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())
    completion_summary: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    completion_summary_version: Mapped[int] = mapped_column(
        Integer(), default=0, server_default="0", nullable=False
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Chapter.position, Chapter.id",
    )
    memory: Mapped["CourseMemory | None"] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        uselist=False,
    )
    materials: Mapped[list["LearningMaterial"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        foreign_keys="LearningMaterial.course_id",
    )


class Chapter(TimestampMixin, Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)

    course: Mapped[Course] = relationship(back_populates="chapters")
    sections: Mapped[list["Section"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Section.position, Section.id",
    )
    materials: Mapped[list["LearningMaterial"]] = relationship(
        back_populates="chapter",
        foreign_keys="LearningMaterial.chapter_id",
    )
    memory: Mapped["ChapterMemory | None"] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Section(TimestampMixin, Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    note_relative_path: Mapped[str | None] = mapped_column(
        String(1000), unique=True, nullable=True
    )
    position: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    status: Mapped[SectionStatus] = mapped_column(
        Enum(
            SectionStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="section_status",
        ),
        default=SectionStatus.NOT_STARTED,
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship(back_populates="sections")
    daily_records: Mapped[list["DailyRecord"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="DailyRecord.study_date.desc()",
    )
    memory: Mapped["SectionMemory | None"] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        uselist=False,
    )
    materials: Mapped[list["LearningMaterial"]] = relationship(
        back_populates="section",
        foreign_keys="LearningMaterial.section_id",
    )
    material_context_sessions: Mapped[list["MaterialContextSession"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="MaterialContextSession.revision",
    )


class DailyRecord(TimestampMixin, Base):
    __tablename__ = "daily_records"
    __table_args__ = (UniqueConstraint("section_id", "study_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    study_date: Mapped[date] = mapped_column(Date(), nullable=False)
    is_completed: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="0", nullable=False
    )
    recall_last_learned: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    recall_core_concepts: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    recall_clear_parts: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    recall_blocked_parts: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    study_material_scope: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    reconstruct_problem: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    reconstruct_main_learning: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    reconstruct_math: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    reconstruct_explanation: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    context_summary: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    material_brief: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    material_context_signature: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )

    section: Mapped[Section] = relationship(back_populates="daily_records")
    workflow_nodes: Mapped[list["WorkflowNodeState"]] = relationship(
        back_populates="daily_record",
        cascade="all, delete-orphan",
        order_by="WorkflowNodeState.position",
    )
    ai_interactions: Mapped[list["AiInteraction"]] = relationship(
        back_populates="daily_record",
        cascade="all, delete-orphan",
        order_by="AiInteraction.id",
    )
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="daily_record",
        cascade="all, delete-orphan",
        order_by="Exercise.id",
    )
    preview_question_set: Mapped["PreviewQuestionSet | None"] = relationship(
        back_populates="daily_record",
        cascade="all, delete-orphan",
        uselist=False,
    )
    section_note_prompt: Mapped["SectionNotePrompt | None"] = relationship(
        back_populates="daily_record",
        cascade="all, delete-orphan",
        uselist=False,
    )
    material_selections: Mapped[list["DailyRecordMaterial"]] = relationship(
        back_populates="daily_record",
        cascade="all, delete-orphan",
    )


class LearningMaterial(TimestampMixin, Base):
    __tablename__ = "learning_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[MaterialSourceType] = mapped_column(
        Enum(
            MaterialSourceType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="material_source_type",
        ),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    original_name: Mapped[str] = mapped_column(
        String(500), default="", server_default="", nullable=False
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000), default="", server_default="", nullable=False
    )
    source_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", index=True, nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    parser_version: Mapped[str] = mapped_column(
        String(60), default="legacy-v1", server_default="legacy-v1", nullable=False
    )
    status: Mapped[MaterialStatus] = mapped_column(
        Enum(
            MaterialStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="material_status",
        ),
        default=MaterialStatus.READY,
        nullable=False,
    )
    error_text: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    last_refresh_status: Mapped[MaterialRefreshStatus] = mapped_column(
        Enum(
            MaterialRefreshStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="material_refresh_status",
        ),
        default=MaterialRefreshStatus.IDLE,
        server_default=MaterialRefreshStatus.IDLE.value,
        nullable=False,
    )
    last_refresh_error: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime())
    is_primary: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="0", nullable=False
    )

    course: Mapped[Course] = relationship(
        back_populates="materials",
        foreign_keys=[course_id],
    )
    chapter: Mapped[Chapter | None] = relationship(
        back_populates="materials",
        foreign_keys=[chapter_id],
    )
    section: Mapped[Section | None] = relationship(
        back_populates="materials",
        foreign_keys=[section_id],
    )
    chunks: Mapped[list["MaterialChunk"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="MaterialChunk.position",
    )
    daily_record_selections: Mapped[list["DailyRecordMaterial"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
    )


class MaterialChunk(Base):
    __tablename__ = "material_chunks"
    __table_args__ = (UniqueConstraint("material_id", "version_hash", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    version_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    heading: Mapped[str] = mapped_column(String(500), default="", server_default="", nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer())
    content: Mapped[str] = mapped_column(Text(), nullable=False)

    material: Mapped[LearningMaterial] = relationship(back_populates="chunks")


class DailyRecordMaterial(TimestampMixin, Base):
    __tablename__ = "daily_record_materials"
    __table_args__ = (UniqueConstraint("daily_record_id", "material_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="1", nullable=False
    )
    range_note: Mapped[str] = mapped_column(
        String(1000), default="", server_default="", nullable=False
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )

    daily_record: Mapped[DailyRecord] = relationship(back_populates="material_selections")
    material: Mapped[LearningMaterial] = relationship(back_populates="daily_record_selections")


class WorkflowNodeState(TimestampMixin, Base):
    __tablename__ = "workflow_node_states"
    __table_args__ = (UniqueConstraint("daily_record_id", "node_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    node_key: Mapped[WorkflowNodeKey] = mapped_column(
        Enum(
            WorkflowNodeKey,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="workflow_node_key",
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[WorkflowNodeStatus] = mapped_column(
        Enum(
            WorkflowNodeStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="workflow_node_status",
        ),
        default=WorkflowNodeStatus.PENDING,
        nullable=False,
    )

    daily_record: Mapped[DailyRecord] = relationship(back_populates="workflow_nodes")

    @property
    def title(self) -> str:
        return WORKFLOW_NODE_TITLES[self.node_key]


class AiInteraction(TimestampMixin, Base):
    __tablename__ = "ai_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[AiInteractionKind] = mapped_column(
        Enum(
            AiInteractionKind,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="ai_interaction_kind",
        ),
        nullable=False,
    )
    prompt_text: Mapped[str] = mapped_column(Text(), nullable=False)
    feedback_text: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )

    daily_record: Mapped[DailyRecord] = relationship(back_populates="ai_interactions")


class Exercise(TimestampMixin, Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    generation_prompt: Mapped[str] = mapped_column(Text(), nullable=False)
    ai_questions: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    user_answers: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    grading_prompt: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    ai_feedback: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    format_version: Mapped[int] = mapped_column(
        Integer(), default=1, server_default="1", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="draft", server_default="draft", nullable=False
    )

    daily_record: Mapped[DailyRecord] = relationship(back_populates="exercises")
    items: Mapped[list["ExerciseItem"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        order_by="ExerciseItem.position",
    )
    mistakes: Mapped[list["Mistake"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        order_by="Mistake.id",
    )


class ExerciseItem(TimestampMixin, Base):
    __tablename__ = "exercise_items"
    __table_args__ = (UniqueConstraint("exercise_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    item_type: Mapped[ExerciseItemType] = mapped_column(
        Enum(
            ExerciseItemType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="exercise_item_type",
        ),
        nullable=False,
    )
    difficulty: Mapped[ExerciseDifficulty] = mapped_column(
        Enum(
            ExerciseDifficulty,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="exercise_difficulty",
        ),
        nullable=False,
    )
    stem_markdown: Mapped[str] = mapped_column(Text(), nullable=False)
    options_json: Mapped[str] = mapped_column(
        Text(), default="[]", server_default="[]", nullable=False
    )
    answer_key_json: Mapped[str] = mapped_column(
        Text(), default="{}", server_default="{}", nullable=False
    )
    rubric_markdown: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    source_refs_json: Mapped[str] = mapped_column(
        Text(), default="[]", server_default="[]", nullable=False
    )

    exercise: Mapped[Exercise] = relationship(back_populates="items")
    response: Mapped["ExerciseResponse | None"] = relationship(
        back_populates="exercise_item",
        cascade="all, delete-orphan",
        uselist=False,
    )
    mistakes: Mapped[list["Mistake"]] = relationship(back_populates="exercise_item")

    @property
    def options(self) -> list[dict[str, str]]:
        try:
            value = json.loads(self.options_json)
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []

    @property
    def source_refs(self) -> list[str]:
        try:
            value = json.loads(self.source_refs_json)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def answer_key(self) -> dict[str, object]:
        try:
            value = json.loads(self.answer_key_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


class ExerciseResponse(TimestampMixin, Base):
    __tablename__ = "exercise_responses"
    __table_args__ = (UniqueConstraint("exercise_item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_item_id: Mapped[int] = mapped_column(
        ForeignKey("exercise_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    answer_markdown: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    selected_options_json: Mapped[str] = mapped_column(
        Text(), default="[]", server_default="[]", nullable=False
    )
    status: Mapped[ExerciseResponseStatus] = mapped_column(
        Enum(
            ExerciseResponseStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="exercise_response_status",
        ),
        default=ExerciseResponseStatus.UNANSWERED,
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    feedback_markdown: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    score: Mapped[int | None] = mapped_column(Integer())

    exercise_item: Mapped[ExerciseItem] = relationship(back_populates="response")

    @property
    def selected_options(self) -> list[str]:
        try:
            value = json.loads(self.selected_options_json)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in value] if isinstance(value, list) else []


class Mistake(TimestampMixin, Base):
    __tablename__ = "mistakes"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exercise_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercise_items.id", ondelete="SET NULL"), index=True
    )
    original_question: Mapped[str] = mapped_column(Text(), nullable=False)
    user_answer: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    error_content: Mapped[str] = mapped_column(Text(), nullable=False)
    error_type: Mapped[MistakeType] = mapped_column(
        Enum(
            MistakeType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="mistake_type",
        ),
        nullable=False,
    )
    correct_approach: Mapped[str] = mapped_column(Text(), nullable=False)
    cause_analysis: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[MistakeStatus] = mapped_column(
        Enum(
            MistakeStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="mistake_status",
        ),
        default=MistakeStatus.UNRESOLVED,
        nullable=False,
    )

    exercise: Mapped[Exercise] = relationship(back_populates="mistakes")
    exercise_item: Mapped[ExerciseItem | None] = relationship(back_populates="mistakes")


class PreviewQuestionSet(TimestampMixin, Base):
    __tablename__ = "preview_question_sets"
    __table_args__ = (UniqueConstraint("daily_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text(), nullable=False)
    question_1: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    question_2: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    question_3: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)

    daily_record: Mapped[DailyRecord] = relationship(back_populates="preview_question_set")


class SectionNotePrompt(TimestampMixin, Base):
    __tablename__ = "section_note_prompts"
    __table_args__ = (UniqueConstraint("daily_record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text(), nullable=False)

    daily_record: Mapped[DailyRecord] = relationship(back_populates="section_note_prompt")


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text(), nullable=False)


class MaterialContextSession(TimestampMixin, Base):
    __tablename__ = "material_context_sessions"
    __table_args__ = (UniqueConstraint("section_id", "revision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[MaterialSessionStatus] = mapped_column(
        Enum(
            MaterialSessionStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="material_session_status",
        ),
        default=MaterialSessionStatus.PREPARING,
        nullable=False,
    )
    thread_id: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    anchor_turn_id: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    manifest_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", server_default="", nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text(), nullable=False)
    workspace_path: Mapped[str] = mapped_column(Text(), nullable=False)
    change_kind: Mapped[str] = mapped_column(
        String(40), default="rebuild", server_default="rebuild", nullable=False
    )
    error_text: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )

    section: Mapped[Section] = relationship(back_populates="material_context_sessions")


class CourseMemory(TimestampMixin, Base):
    __tablename__ = "course_memories"
    __table_args__ = (UniqueConstraint("course_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    overview: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    generated_outline: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    core_concepts: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    key_methods: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    unresolved_questions: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    error_patterns: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    version: Mapped[int] = mapped_column(Integer(), default=1, server_default="1", nullable=False)

    course: Mapped[Course] = relationship(back_populates="memory")


class ChapterMemory(TimestampMixin, Base):
    __tablename__ = "chapter_memories"
    __table_args__ = (UniqueConstraint("chapter_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    core_concepts: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    key_methods: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    unresolved_questions: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    error_patterns: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    version: Mapped[int] = mapped_column(Integer(), default=1, server_default="1", nullable=False)

    chapter: Mapped[Chapter] = relationship(back_populates="memory")


class SectionMemory(TimestampMixin, Base):
    __tablename__ = "section_memories"
    __table_args__ = (UniqueConstraint("section_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    core_concepts: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    key_methods: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    unresolved_questions: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    error_patterns: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    version: Mapped[int] = mapped_column(Integer(), default=1, server_default="1", nullable=False)

    section: Mapped[Section] = relationship(back_populates="memory")


class AiRun(TimestampMixin, Base):
    __tablename__ = "ai_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[AiProvider] = mapped_column(
        Enum(
            AiProvider,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="ai_provider",
        ),
        nullable=False,
    )
    task: Mapped[AiRunTask] = mapped_column(
        Enum(
            AiRunTask,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="ai_run_task",
        ),
        nullable=False,
    )
    status: Mapped[AiRunStatus] = mapped_column(
        Enum(
            AiRunStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="ai_run_status",
        ),
        default=AiRunStatus.RUNNING,
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL"), index=True
    )
    daily_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_records.id", ondelete="SET NULL"), index=True
    )
    exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), index=True
    )
    material_context_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_context_sessions.id", ondelete="SET NULL"), index=True
    )
    material_revision: Mapped[int] = mapped_column(
        Integer(), default=0, server_default="0", nullable=False
    )
    material_manifest_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False
    )
    model: Mapped[str] = mapped_column(String(100), default="", server_default="", nullable=False)
    reasoning_effort: Mapped[str] = mapped_column(
        String(30), default="", server_default="", nullable=False
    )
    thread_id: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    context_snapshot: Mapped[str] = mapped_column(Text(), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text(), nullable=False)
    output_text: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    handoff_json: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
    source_refs_json: Mapped[str] = mapped_column(
        Text(), default="", server_default="", nullable=False
    )
    error_text: Mapped[str] = mapped_column(Text(), default="", server_default="", nullable=False)
