from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    AiInteractionKind,
    AiProvider,
    AiRunStatus,
    AiRunTask,
    ExerciseDifficulty,
    ExerciseItemType,
    ExerciseResponseStatus,
    MaterialRefreshStatus,
    MaterialSourceType,
    MaterialStatus,
    MistakeStatus,
    MistakeType,
    SectionStatus,
    WorkflowNodeStatus,
)
from app.workflow import WorkflowNodeKey


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AiRunRead(ORMModel):
    id: int
    provider: AiProvider
    task: AiRunTask
    status: AiRunStatus
    course_id: int | None
    section_id: int | None
    daily_record_id: int | None
    exercise_id: int | None
    model: str
    reasoning_effort: str
    error_text: str
    created_at: datetime
    updated_at: datetime


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    learning_goal: str = Field(default="", max_length=5000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("课程名称不能为空")
        return value


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    learning_goal: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("课程名称不能为空")
        return value


class DailyRecordSummary(ORMModel):
    id: int
    study_date: date
    is_completed: bool
    recall_last_learned: str
    recall_core_concepts: str
    reconstruct_main_learning: str


class SectionRead(ORMModel):
    id: int
    chapter_id: int
    title: str
    position: int
    status: SectionStatus
    daily_records: list[DailyRecordSummary] = Field(default_factory=list)


class ChapterRead(ORMModel):
    id: int
    course_id: int
    title: str
    position: int
    sections: list[SectionRead] = Field(default_factory=list)


class CourseRead(ORMModel):
    id: int
    name: str
    description: str
    learning_goal: str
    completed_at: datetime | None
    completion_summary: str
    completion_summary_version: int


class CourseSummary(CourseRead):
    total_sections: int = 0
    completed_sections: int = 0
    in_progress_sections: int = 0


class CourseDetail(CourseRead):
    chapters: list[ChapterRead] = Field(default_factory=list)


class ChapterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("章节标题不能为空")
        return value


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("章节标题不能为空")
        return value


class SectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("小节标题不能为空")
        return value


class SectionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=0)
    status: SectionStatus | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("小节标题不能为空")
        return value


class WorkflowNodeRead(ORMModel):
    id: int
    node_key: WorkflowNodeKey
    title: str
    position: int
    status: WorkflowNodeStatus


class DailyRecordContentUpdate(BaseModel):
    recall_last_learned: str | None = Field(default=None, max_length=30000)
    recall_core_concepts: str | None = Field(default=None, max_length=30000)
    recall_clear_parts: str | None = Field(default=None, max_length=30000)
    recall_blocked_parts: str | None = Field(default=None, max_length=30000)
    study_material_scope: str | None = Field(default=None, max_length=30000)
    reconstruct_problem: str | None = Field(default=None, max_length=30000)
    reconstruct_main_learning: str | None = Field(default=None, max_length=30000)
    reconstruct_math: str | None = Field(default=None, max_length=30000)


class WorkflowNodeUpdate(BaseModel):
    status: WorkflowNodeStatus


class AiInteractionRead(ORMModel):
    id: int
    daily_record_id: int
    kind: AiInteractionKind
    prompt_text: str
    feedback_text: str


class AiInteractionUpdate(BaseModel):
    feedback_text: str = Field(max_length=50000)


class MistakeCreate(BaseModel):
    exercise_item_id: int | None = Field(default=None, gt=0)
    original_question: str = Field(min_length=1, max_length=50000)
    user_answer: str = Field(default="", max_length=50000)
    error_content: str = Field(min_length=1, max_length=50000)
    error_type: MistakeType
    correct_approach: str = Field(min_length=1, max_length=50000)
    cause_analysis: str = Field(min_length=1, max_length=50000)


class MistakeUpdate(BaseModel):
    exercise_item_id: int | None = Field(default=None, gt=0)
    original_question: str | None = Field(default=None, min_length=1, max_length=50000)
    user_answer: str | None = Field(default=None, max_length=50000)
    error_content: str | None = Field(default=None, min_length=1, max_length=50000)
    error_type: MistakeType | None = None
    correct_approach: str | None = Field(default=None, min_length=1, max_length=50000)
    cause_analysis: str | None = Field(default=None, min_length=1, max_length=50000)
    status: MistakeStatus | None = None


class MistakeRead(ORMModel):
    id: int
    exercise_id: int
    exercise_item_id: int | None
    original_question: str
    user_answer: str
    error_content: str
    error_type: MistakeType
    correct_approach: str
    cause_analysis: str
    status: MistakeStatus


class MistakeIndexItem(BaseModel):
    id: int
    exercise_id: int
    daily_record_id: int
    study_date: date
    course_id: int
    course_name: str
    chapter_id: int
    chapter_title: str
    section_id: int
    section_title: str
    original_question: str
    user_answer: str
    error_content: str
    error_type: MistakeType
    correct_approach: str
    cause_analysis: str
    status: MistakeStatus


class MistakeScopeSection(BaseModel):
    id: int
    title: str


class MistakeScopeChapter(BaseModel):
    id: int
    title: str
    sections: list[MistakeScopeSection]


class MistakeScopeCourse(BaseModel):
    id: int
    name: str
    chapters: list[MistakeScopeChapter]


class MistakeIndexRead(BaseModel):
    items: list[MistakeIndexItem]
    courses: list[MistakeScopeCourse]


ExportContentType = Literal[
    "outline",
    "daily_records",
    "ai_reviews",
    "exercises",
    "mistakes",
    "notes",
]


class MarkdownArchiveRequest(BaseModel):
    course_ids: list[int] = Field(min_length=1, max_length=1000)
    content_types: set[ExportContentType] = Field(min_length=1)

    @field_validator("course_ids")
    @classmethod
    def unique_course_ids(cls, value: list[int]) -> list[int]:
        if any(course_id <= 0 for course_id in value):
            raise ValueError("课程 ID 必须是正整数")
        return list(dict.fromkeys(value))


class ExerciseOption(BaseModel):
    id: str
    label: str


class ExerciseResponseRead(ORMModel):
    id: int
    exercise_item_id: int
    answer_markdown: str
    selected_options: list[str]
    status: ExerciseResponseStatus
    verdict: str
    feedback_markdown: str
    score: int | None


class ExerciseItemRead(ORMModel):
    id: int
    exercise_id: int
    position: int
    item_type: ExerciseItemType
    difficulty: ExerciseDifficulty
    stem_markdown: str
    options: list[ExerciseOption]
    source_refs: list[str]
    response: ExerciseResponseRead | None


class ExerciseRead(ORMModel):
    id: int
    daily_record_id: int
    generation_prompt: str
    ai_questions: str
    user_answers: str
    grading_prompt: str
    ai_feedback: str
    format_version: int
    status: str
    items: list[ExerciseItemRead]
    mistakes: list[MistakeRead]


class ExerciseUpdate(BaseModel):
    ai_questions: str | None = Field(default=None, max_length=100000)
    user_answers: str | None = Field(default=None, max_length=100000)
    ai_feedback: str | None = Field(default=None, max_length=100000)


class ExerciseResponseUpdate(BaseModel):
    answer_markdown: str = Field(default="", max_length=100000)
    selected_options: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("selected_options")
    @classmethod
    def unique_selected_options(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(normalized))


class PreviewQuestionSetRead(ORMModel):
    id: int
    daily_record_id: int
    prompt_text: str
    question_1: str
    question_2: str
    question_3: str


class PreviewQuestionsUpdate(BaseModel):
    question_1: str = Field(min_length=1, max_length=10000)
    question_2: str = Field(min_length=1, max_length=10000)
    question_3: str = Field(min_length=1, max_length=10000)

    @field_validator("question_1", "question_2", "question_3")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("预习问题不能为空")
        return value


class PreviousPreviewQuestions(BaseModel):
    study_date: date
    questions: list[str]


class LocalSettingsRead(BaseModel):
    obsidian_vault_path: str
    learner_profile: str
    desktop_launch: bool = False
    setup_pending: bool = False


class LearnerProfileUpdate(BaseModel):
    learner_profile: str = Field(default="", max_length=30000)


class AiProviderStatusRead(BaseModel):
    provider: Literal["codex", "gemini"]
    installed: bool
    connected: bool
    detail: str
    account: str = ""
    plan: str = ""
    version: str = ""
    state: Literal[
        "not_installed",
        "launch_blocked",
        "disconnected",
        "connected",
        "model_unavailable",
        "error",
    ] = "disconnected"
    preferred_model: str = ""
    model_available: bool | None = None
    reasoning_effort: str = ""
    active_model: str = ""
    executable: str = ""
    service_mode: str = ""


class AiModelOptionRead(BaseModel):
    model: str
    display_name: str
    reasoning_efforts: list[str]
    default_reasoning_effort: str = ""


class AiProviderOptionsRead(BaseModel):
    provider: Literal["codex", "gemini"]
    selected_model: str
    selected_reasoning_effort: str
    default_model: str
    default_reasoning_effort: str
    models: list[AiModelOptionRead] = Field(default_factory=list)
    error: str = ""


class AiProviderSnapshotRead(BaseModel):
    providers: list[AiProviderStatusRead]
    options: list[AiProviderOptionsRead]


class AiProviderPreferenceUpdate(BaseModel):
    model: str = Field(min_length=1, max_length=100)
    reasoning_effort: str = Field(min_length=1, max_length=30)

    @field_validator("model", "reasoning_effort")
    @classmethod
    def strip_ai_preference(cls, value: str) -> str:
        return value.strip()


class MaterialUrlCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=4000)
    course_id: int = Field(gt=0)
    chapter_id: int | None = Field(default=None, gt=0)
    section_id: int | None = Field(default=None, gt=0)
    is_primary: bool = False

    @field_validator("title", "url")
    @classmethod
    def strip_material_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("材料信息不能为空")
        return value


class MaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    course_id: int | None = Field(default=None, gt=0)
    chapter_id: int | None = Field(default=None, gt=0)
    section_id: int | None = Field(default=None, gt=0)
    is_primary: bool | None = None

    @field_validator("title")
    @classmethod
    def strip_material_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("材料名称不能为空")
        return value


class MaterialRead(BaseModel):
    id: int
    course_id: int
    course_name: str
    chapter_id: int | None
    chapter_title: str
    section_id: int | None
    section_title: str
    title: str
    source_type: MaterialSourceType
    source_url: str
    original_name: str
    status: MaterialStatus
    error_text: str
    last_refresh_status: MaterialRefreshStatus
    last_refresh_error: str
    last_refresh_at: datetime | None
    last_success_at: datetime | None
    is_primary: bool
    chunk_count: int


class MaterialRefreshRead(BaseModel):
    refresh_status: MaterialRefreshStatus
    using_previous_revision: bool
    error: str
    material: MaterialRead


class DailyRecordMaterialRead(MaterialRead):
    selected: bool
    range_note: str


class DailyRecordMaterialUpdate(BaseModel):
    selected: bool
    range_note: str = Field(default="", max_length=1000)


class AiProviderLoginRead(BaseModel):
    auth_url: str
    login_id: str


class GeminiProviderLoginRead(BaseModel):
    login_id: str


class AiProviderLoginStatusRead(BaseModel):
    status: Literal["pending", "succeeded", "failed", "not_found"]
    error: str = ""
    detail: str = ""


class AiGeneratedTextRead(BaseModel):
    text: str
    provider: Literal["codex", "gemini"]
    model: str = ""
    context_snapshot: str
    source_refs: list["AiSourceReferenceRead"] = Field(default_factory=list)
    material_revision: int = 0
    material_manifest_hash: str = ""


class AiRunResultRead(BaseModel):
    run: AiRunRead
    result: AiGeneratedTextRead | None = None


class AiSourceReferenceRead(BaseModel):
    task: str
    material_id: int
    material_title: str
    source_type: MaterialSourceType
    location: str
    content_hash: str
    chunk_position: int | None = None


class SectionNoteGenerateRequest(BaseModel):
    existing_content: str = Field(default="", max_length=2000000)
    mode: Literal["create", "revise"] = "create"


class NotePolishRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000000)
    context: str = Field(default="", max_length=100000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("笔记正文不能为空")
        return value


class CourseMemoryUpdate(BaseModel):
    overview: str = Field(default="", max_length=30000)
    core_concepts: str = Field(default="", max_length=30000)
    key_methods: str = Field(default="", max_length=30000)
    unresolved_questions: str = Field(default="", max_length=30000)
    error_patterns: str = Field(default="", max_length=30000)


class SectionMemoryRead(ORMModel):
    id: int
    section_id: int
    summary: str
    core_concepts: str
    key_methods: str
    unresolved_questions: str
    error_patterns: str
    version: int


class ChapterMemoryRead(ORMModel):
    id: int
    chapter_id: int
    summary: str
    core_concepts: str
    key_methods: str
    unresolved_questions: str
    error_patterns: str
    version: int


class CourseMemoryRead(ORMModel):
    id: int
    course_id: int
    overview: str
    generated_outline: str
    core_concepts: str
    key_methods: str
    unresolved_questions: str
    error_patterns: str
    version: int


class CourseLearningMemoryRead(BaseModel):
    course: CourseMemoryRead
    chapters: list[ChapterMemoryRead]
    sections: list[SectionMemoryRead]


class ObsidianVaultUpdate(BaseModel):
    obsidian_vault_path: str = Field(min_length=1, max_length=2000)

    @field_validator("obsidian_vault_path")
    @classmethod
    def strip_vault_path(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Obsidian vault 路径不能为空")
        return value


class ObsidianVaultCandidateRead(BaseModel):
    name: str
    path: str
    has_obsidian_directory: bool
    writable: bool


class ObsidianVaultDiscoveryRead(BaseModel):
    vaults: list[ObsidianVaultCandidateRead]
    browse_supported: bool


class ObsidianVaultBrowseRead(BaseModel):
    vault: ObsidianVaultCandidateRead | None


class SectionNoteRead(BaseModel):
    section_id: int
    file_name: str
    relative_path: str
    content: str
    modified_at_ns: int | None


class NoteIndexItem(BaseModel):
    section_id: int
    course_id: int
    course_name: str
    chapter_id: int
    chapter_title: str
    section_title: str
    relative_path: str
    content: str
    modified_at_ns: int


class NoteIndexIssue(BaseModel):
    section_id: int
    section_title: str
    detail: str


class NoteIndexRead(BaseModel):
    items: list[NoteIndexItem]
    issues: list[NoteIndexIssue]


class SectionNoteWrite(BaseModel):
    content: str = Field(max_length=2000000)
    expected_modified_at_ns: int | None
    force_overwrite: bool = False


class MarkdownValidationRequest(BaseModel):
    content: str = Field(max_length=2000000)


class MarkdownValidationIssueRead(BaseModel):
    code: str
    message: str
    line: int | None = None


class MarkdownValidationRead(BaseModel):
    normalized_content: str
    issues: list[MarkdownValidationIssueRead]


class SectionNotePromptRead(ORMModel):
    id: int
    daily_record_id: int
    prompt_text: str


class DailyRecordRead(BaseModel):
    id: int
    section_id: int
    section_title: str
    chapter_id: int
    course_id: int
    study_date: date
    is_completed: bool
    recall_last_learned: str
    recall_core_concepts: str
    recall_clear_parts: str
    recall_blocked_parts: str
    study_material_scope: str
    reconstruct_problem: str
    reconstruct_main_learning: str
    reconstruct_math: str
    context_summary: str
    active_ai_runs: list[AiRunRead] = Field(default_factory=list)
    ai_source_refs: list[AiSourceReferenceRead] = Field(default_factory=list)
    workflow_nodes: list[WorkflowNodeRead]
    previous_records: list[DailyRecordSummary]
    ai_interactions: list[AiInteractionRead]
    exercises: list[ExerciseRead]
    preview_question_set: PreviewQuestionSetRead | None
    previous_preview_questions: PreviousPreviewQuestions | None
    section_note_prompt: SectionNotePromptRead | None
    materials: list[DailyRecordMaterialRead] = Field(default_factory=list)


class CourseCompletionRead(BaseModel):
    course_id: int
    completed_at: datetime
    completion_summary: str
    completion_summary_version: int
