import asyncio
import json
from contextlib import suppress
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload, selectinload
from starlette.concurrency import run_in_threadpool

from app.ai_output_validation import (
    AiOutputValidationError,
    grading_output_validator,
    validate_practice_output,
    validate_preview_output,
)
from app.ai_preferences import (
    CODEX_DEFAULT_MODEL,
    CODEX_DEFAULT_REASONING_EFFORT,
    GEMINI_DEFAULT_MODEL,
    GEMINI_DEFAULT_REASONING_EFFORT,
    codex_preference,
    gemini_preference,
    save_preference,
)
from app.ai_providers import AiModelOption, AiProviderError, AiService
from app.ai_workflows import (
    DAILY_SUMMARY_OUTPUT_SCHEMA,
    GRADING_OUTPUT_SCHEMA,
    PRACTICE_OUTPUT_SCHEMA,
    PREVIEW_OUTPUT_SCHEMA,
    TEXT_OUTPUT_SCHEMA,
    apply_daily_summary_memory,
    build_task_context,
    cancel_active_ai_run,
    course_context,
    daily_summary_source,
    ensure_chapter_memory,
    ensure_course_memory,
    ensure_section_memory,
    load_course_with_memories,
    parse_structured_output,
    refresh_section_memory,
    run_codex,
    run_gemini,
)
from app.database import get_session
from app.exports import build_markdown_archive
from app.markdown import normalize_ai_markdown, validate_note_markdown
from app.material_sessions import (
    ensure_material_context,
    inline_material_context,
    material_references,
    material_session_context,
    parse_manifest,
)
from app.materials import (
    MATERIAL_PARSER_VERSION,
    MAX_PDF_BYTES,
    MaterialError,
    MaterialReference,
    content_hash,
    extract_pdf,
    fetch_url,
    fetch_video_transcript,
    html_chunks,
    looks_like_video_url,
    material_query,
    remove_storage,
    revision_hash,
    save_chunks,
    scoped_materials,
    set_primary,
    storage_directory,
    validate_scope,
)
from app.models import (
    AiInteraction,
    AiInteractionKind,
    AiProvider,
    AiRun,
    AiRunStatus,
    AiRunTask,
    AppSetting,
    Chapter,
    Course,
    CourseMemory,
    DailyRecord,
    DailyRecordMaterial,
    Exercise,
    ExerciseDifficulty,
    ExerciseItem,
    ExerciseItemType,
    ExerciseResponse,
    ExerciseResponseStatus,
    LearningMaterial,
    MaterialContextSession,
    MaterialRefreshStatus,
    MaterialSourceType,
    MaterialStatus,
    Mistake,
    PreviewQuestionSet,
    Section,
    SectionMemory,
    SectionNotePrompt,
    SectionStatus,
    WorkflowNodeState,
    WorkflowNodeStatus,
)
from app.notes import (
    NoteConflictError,
    NotePathError,
    get_vault_path,
    read_section_note,
    save_vault_path,
    write_section_note,
)
from app.prompts import (
    course_completion_prompt,
    daily_summary_prompt,
    deterministic_choice_verdict,
    grading_prompt,
    practice_generation_prompt,
    preview_questions_prompt,
    recall_review_prompt,
    reconstruction_review_prompt,
    section_note_prompt,
)
from app.schemas import (
    AiGeneratedTextRead,
    AiInteractionRead,
    AiInteractionUpdate,
    AiModelOptionRead,
    AiProviderLoginRead,
    AiProviderLoginStatusRead,
    AiProviderOptionsRead,
    AiProviderPreferenceUpdate,
    AiProviderSnapshotRead,
    AiProviderStatusRead,
    AiRunRead,
    AiRunResultRead,
    AiSourceReferenceRead,
    ChapterCreate,
    ChapterMemoryRead,
    ChapterRead,
    ChapterUpdate,
    CourseCompletionRead,
    CourseCreate,
    CourseDetail,
    CourseLearningMemoryRead,
    CourseMemoryRead,
    CourseMemoryUpdate,
    CourseRead,
    CourseSummary,
    CourseUpdate,
    DailyRecordContentUpdate,
    DailyRecordMaterialRead,
    DailyRecordMaterialUpdate,
    DailyRecordRead,
    DailyRecordSummary,
    ExerciseRead,
    ExerciseResponseUpdate,
    ExerciseUpdate,
    GeminiProviderLoginRead,
    LearnerProfileUpdate,
    LocalSettingsRead,
    MarkdownArchiveRequest,
    MarkdownValidationRead,
    MarkdownValidationRequest,
    MaterialRead,
    MaterialRefreshRead,
    MaterialSearchSettingsRead,
    MaterialUpdate,
    MaterialUrlCreate,
    MistakeCreate,
    MistakeIndexItem,
    MistakeIndexRead,
    MistakeRead,
    MistakeScopeChapter,
    MistakeScopeCourse,
    MistakeScopeSection,
    MistakeUpdate,
    NoteIndexIssue,
    NoteIndexItem,
    NoteIndexRead,
    NotePolishRequest,
    ObsidianVaultBrowseRead,
    ObsidianVaultCandidateRead,
    ObsidianVaultDiscoveryRead,
    ObsidianVaultUpdate,
    OnboardingStatusRead,
    PreviewQuestionSetRead,
    PreviewQuestionsUpdate,
    PreviousPreviewQuestions,
    SectionCreate,
    SectionMemoryRead,
    SectionNoteGenerateRequest,
    SectionNotePromptRead,
    SectionNoteRead,
    SectionNoteWrite,
    SectionRead,
    SectionUpdate,
    WorkflowNodeRead,
    WorkflowNodeUpdate,
)
from app.search_index import (
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_SIZE,
    index_path,
    model_cache_path,
    model_ready,
    prepare_semantic_model_paths,
    semantic_enabled,
    set_semantic_enabled,
)
from app.vaults import (
    VaultBrowserError,
    VaultBrowserUnavailableError,
    VaultCandidate,
    browse_for_vault,
    discover_obsidian_vaults,
    vault_browser_supported,
)
from app.workflow import WORKFLOW_NODES, WorkflowNodeKey

router = APIRouter(prefix="/api")
SessionDependency = Annotated[Session, Depends(get_session)]


def get_current_date(request: Request) -> date:
    return request.app.state.today_provider()


CurrentDateDependency = Annotated[date, Depends(get_current_date)]


def get_ai_service(request: Request) -> AiService:
    return request.app.state.ai_service


AiServiceDependency = Annotated[AiService, Depends(get_ai_service)]
GEMINI_ENABLED_SETTING = "gemini_enabled"


def setting_value(session: Session, key: str) -> str:
    value = session.get(AppSetting, key)
    return value.value if value is not None else ""


def save_setting(session: Session, key: str, value: str) -> str:
    setting = session.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
    session.commit()
    return value


def gemini_enabled(session: Session) -> bool:
    return setting_value(session, GEMINI_ENABLED_SETTING) != "0"


async def grounded_task_context(
    session: Session,
    ai_service: AiService,
    record: DailyRecord,
    task: AiRunTask,
) -> tuple[str, list[MaterialReference], MaterialContextSession | None]:
    material_record = record
    if task == AiRunTask.RECALL_REVIEW:
        previous_records = load_previous_records(session, record)
        if previous_records:
            material_record = previous_records[0]
    material_context = await ensure_material_context(session, ai_service, material_record)
    material_pending = bool(
        material_context is not None and material_context.change_kind.endswith("_pending")
    )
    task_context = build_task_context(
        session,
        record,
        task,
        include_material_evidence=material_context is None or material_pending,
    )
    if material_context is None:
        return task_context.text, task_context.source_refs, None
    text = f"{task_context.text}\n\n{material_session_context(material_context)}"
    references = material_references(session, parse_manifest(material_context.manifest_json))
    return text, references, material_context


def require_course(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


def require_chapter(session: Session, chapter_id: int) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


def require_section(session: Session, section_id: int) -> Section:
    section = session.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="小节不存在")
    return section


def load_course_detail(session: Session, course_id: int) -> Course:
    course = session.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.chapters)
            .selectinload(Chapter.sections)
            .selectinload(Section.daily_records)
            .load_only(
                DailyRecord.id,
                DailyRecord.study_date,
                DailyRecord.is_completed,
                DailyRecord.recall_last_learned,
                DailyRecord.recall_core_concepts,
                DailyRecord.reconstruct_main_learning,
            )
        )
    )
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


def load_daily_record(session: Session, record_id: int) -> DailyRecord:
    record = session.scalar(
        select(DailyRecord)
        .where(DailyRecord.id == record_id)
        .options(
            selectinload(DailyRecord.workflow_nodes),
            selectinload(DailyRecord.ai_interactions),
            selectinload(DailyRecord.exercises).selectinload(Exercise.mistakes),
            selectinload(DailyRecord.exercises)
            .selectinload(Exercise.items)
            .joinedload(ExerciseItem.response),
            joinedload(DailyRecord.preview_question_set),
            joinedload(DailyRecord.section_note_prompt),
            joinedload(DailyRecord.section).joinedload(Section.chapter).joinedload(Chapter.course),
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="学习记录不存在")
    return record


def load_previous_records(session: Session, record: DailyRecord) -> list[DailyRecord]:
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


def load_all_section_records(session: Session, record: DailyRecord) -> list[DailyRecord]:
    return list(
        session.scalars(
            select(DailyRecord)
            .where(
                DailyRecord.section_id == record.section_id,
                DailyRecord.id != record.id,
            )
            .order_by(DailyRecord.study_date, DailyRecord.id)
        )
    )


def load_previous_preview_questions(
    session: Session, record: DailyRecord
) -> PreviousPreviewQuestions | None:
    previous = session.scalar(
        select(DailyRecord)
        .join(PreviewQuestionSet)
        .where(
            DailyRecord.section_id == record.section_id,
            DailyRecord.study_date < record.study_date,
            PreviewQuestionSet.question_1 != "",
            PreviewQuestionSet.question_2 != "",
            PreviewQuestionSet.question_3 != "",
        )
        .options(joinedload(DailyRecord.preview_question_set))
        .order_by(DailyRecord.study_date.desc(), DailyRecord.id.desc())
        .limit(1)
    )
    if previous is None or previous.preview_question_set is None:
        return None
    question_set = previous.preview_question_set
    return PreviousPreviewQuestions(
        study_date=previous.study_date,
        questions=[question_set.question_1, question_set.question_2, question_set.question_3],
    )


def daily_record_response(session: Session, record: DailyRecord) -> DailyRecordRead:
    previous_records = load_previous_records(session, record)
    active_runs = list(
        session.scalars(
            select(AiRun)
            .where(
                AiRun.daily_record_id == record.id,
                AiRun.status == AiRunStatus.RUNNING,
            )
            .order_by(AiRun.id.desc())
            .limit(5)
        )
    )
    latest_runs: dict[AiRunTask, AiRun] = {}
    for run in session.scalars(
        select(AiRun)
        .where(
            AiRun.daily_record_id == record.id,
            AiRun.status == AiRunStatus.COMPLETED,
            AiRun.source_refs_json != "",
        )
        .order_by(AiRun.id)
    ):
        latest_runs[run.task] = run
    source_refs: list[AiSourceReferenceRead] = []
    for task, run in latest_runs.items():
        try:
            references = json.loads(run.source_refs_json)
        except json.JSONDecodeError:
            continue
        for reference in references:
            source_refs.append(AiSourceReferenceRead(task=task.value, **reference))
    return DailyRecordRead(
        id=record.id,
        section_id=record.section_id,
        section_title=record.section.title,
        chapter_id=record.section.chapter_id,
        course_id=record.section.chapter.course_id,
        study_date=record.study_date,
        is_completed=record.is_completed,
        recall_last_learned=record.recall_last_learned,
        recall_core_concepts=record.recall_core_concepts,
        recall_clear_parts=record.recall_clear_parts,
        recall_blocked_parts=record.recall_blocked_parts,
        study_material_scope=record.study_material_scope,
        reconstruct_problem=record.reconstruct_problem,
        reconstruct_main_learning=record.reconstruct_main_learning,
        reconstruct_math=record.reconstruct_math,
        context_summary=record.context_summary,
        active_ai_runs=[AiRunRead.model_validate(run) for run in active_runs],
        ai_source_refs=source_refs,
        workflow_nodes=[WorkflowNodeRead.model_validate(node) for node in record.workflow_nodes],
        previous_records=[DailyRecordSummary.model_validate(item) for item in previous_records],
        ai_interactions=[AiInteractionRead.model_validate(item) for item in record.ai_interactions],
        exercises=[ExerciseRead.model_validate(item) for item in record.exercises],
        preview_question_set=(
            PreviewQuestionSetRead.model_validate(record.preview_question_set)
            if record.preview_question_set is not None
            else None
        ),
        previous_preview_questions=load_previous_preview_questions(session, record),
        section_note_prompt=(
            SectionNotePromptRead.model_validate(record.section_note_prompt)
            if record.section_note_prompt is not None
            else None
        ),
        materials=daily_record_material_reads(session, record),
    )


def material_read(material: LearningMaterial) -> MaterialRead:
    return MaterialRead(
        id=material.id,
        course_id=material.course_id,
        course_name=material.course.name,
        chapter_id=material.chapter_id,
        chapter_title=material.chapter.title if material.chapter is not None else "",
        section_id=material.section_id,
        section_title=material.section.title if material.section is not None else "",
        title=material.title,
        source_type=material.source_type,
        source_url=material.source_url,
        original_name=material.original_name,
        status=material.status,
        error_text=material.error_text,
        last_refresh_status=material.last_refresh_status,
        last_refresh_error=material.last_refresh_error,
        last_refresh_at=material.last_refresh_at,
        last_success_at=material.last_success_at,
        is_primary=material.is_primary,
        chunk_count=sum(chunk.version_hash == material.content_hash for chunk in material.chunks),
    )


def daily_record_material_reads(
    session: Session,
    record: DailyRecord,
) -> list[DailyRecordMaterialRead]:
    materials = scoped_materials(
        session,
        course_id=record.section.chapter.course_id,
        chapter_id=record.section.chapter_id,
        section_id=record.section_id,
    )
    selections = {
        selection.material_id: selection
        for selection in session.scalars(
            select(DailyRecordMaterial).where(DailyRecordMaterial.daily_record_id == record.id)
        )
    }
    return [
        DailyRecordMaterialRead(
            **material_read(material).model_dump(),
            selected=(
                selections[material.id].enabled
                if material.id in selections
                else material.status == MaterialStatus.READY
            ),
            range_note=(selections[material.id].range_note if material.id in selections else ""),
        )
        for material in materials
    ]


def material_http_error(error: MaterialError) -> HTTPException:
    detail = str(error)
    code = (
        status.HTTP_409_CONFLICT if "已经添加" in detail else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(status_code=code, detail=detail)


def material_root(request: Request):
    return request.app.state.material_dir


def remove_material_files(request: Request, material_ids: list[int]) -> None:
    for material_id in material_ids:
        with suppress(OSError, MaterialError):
            remove_storage(material_root(request), material_id)


def ai_http_error(error: AiProviderError) -> HTTPException:
    detail = str(error)
    if isinstance(error, AiOutputValidationError):
        code = status.HTTP_502_BAD_GATEWAY
    else:
        code = (
            status.HTTP_409_CONFLICT
            if "连接 Codex" in detail or "连接 Gemini" in detail
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return HTTPException(status_code=code, detail=detail)


@router.get("/ai/providers", response_model=list[AiProviderStatusRead])
async def get_ai_providers(
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> list[AiProviderStatusRead]:
    codex = codex_preference(session)
    gemini = gemini_preference(session)
    providers = await ai_service.statuses(
        codex_model=codex.model,
        codex_reasoning_effort=codex.reasoning_effort,
        gemini_model=gemini.model,
        gemini_reasoning_effort=gemini.reasoning_effort,
        gemini_enabled=gemini_enabled(session),
    )
    return [AiProviderStatusRead(**provider.__dict__) for provider in providers]


def ai_model_option_read(option: AiModelOption) -> AiModelOptionRead:
    return AiModelOptionRead(
        model=option.model,
        display_name=option.display_name,
        reasoning_efforts=list(option.reasoning_efforts),
        default_reasoning_effort=option.default_reasoning_effort,
    )


async def provider_options_payload(
    provider: str,
    session: Session,
    ai_service: AiService,
) -> AiProviderOptionsRead:
    if provider == "codex":
        preference = codex_preference(session)
        default_model = CODEX_DEFAULT_MODEL
        default_effort = CODEX_DEFAULT_REASONING_EFFORT
        try:
            entries = await ai_service.codex.model_entries()
            models = ai_service.codex.model_options(entries)
            error = ""
        except AiProviderError as request_error:
            models = []
            error = str(request_error)
    else:
        preference = gemini_preference(session)
        default_model = GEMINI_DEFAULT_MODEL
        default_effort = GEMINI_DEFAULT_REASONING_EFFORT
        try:
            models = await ai_service.gemini.model_options()
            error = ""
        except (AiProviderError, OSError, TimeoutError) as request_error:
            models = []
            error = str(request_error)
    return AiProviderOptionsRead(
        provider=provider,
        selected_model=preference.model,
        selected_reasoning_effort=preference.reasoning_effort,
        default_model=default_model,
        default_reasoning_effort=default_effort,
        models=[ai_model_option_read(option) for option in models],
        error=error,
    )


@router.get("/ai/provider-options", response_model=list[AiProviderOptionsRead])
async def get_ai_provider_options(
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> list[AiProviderOptionsRead]:
    return [
        await provider_options_payload("codex", session, ai_service),
        await provider_options_payload("gemini", session, ai_service),
    ]


@router.get("/ai/provider-snapshot", response_model=AiProviderSnapshotRead)
async def get_ai_provider_snapshot(
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> AiProviderSnapshotRead:
    providers = await get_ai_providers(session, ai_service)
    options = await get_ai_provider_options(session, ai_service)
    return AiProviderSnapshotRead(providers=providers, options=options)


@router.put(
    "/settings/ai-providers/{provider}",
    response_model=AiProviderOptionsRead,
)
async def update_ai_provider_preference(
    provider: str,
    payload: AiProviderPreferenceUpdate,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> AiProviderOptionsRead:
    if provider not in {"codex", "gemini"}:
        raise HTTPException(status_code=404, detail="没有找到这个模型提供方")
    options = await provider_options_payload(provider, session, ai_service)
    if options.error:
        raise HTTPException(status_code=409, detail=f"无法验证模型列表：{options.error}")
    selected = next((item for item in options.models if item.model == payload.model), None)
    effort = payload.reasoning_effort.lower()
    if selected is None:
        raise HTTPException(status_code=422, detail="所选模型当前不可用，请刷新后重新选择")
    if effort not in selected.reasoning_efforts:
        raise HTTPException(
            status_code=422,
            detail=f"{selected.display_name} 当前不支持 {effort.title()}",
        )
    save_preference(
        session,
        provider=provider,
        model=payload.model,
        reasoning_effort=effort,
    )
    options.selected_model = payload.model
    options.selected_reasoning_effort = effort
    return options


@router.post("/ai/providers/codex/login", response_model=AiProviderLoginRead)
async def start_codex_login(ai_service: AiServiceDependency) -> AiProviderLoginRead:
    try:
        return AiProviderLoginRead(**(await ai_service.codex.login()))
    except AiProviderError as error:
        raise ai_http_error(error) from error


@router.get(
    "/ai/providers/codex/login/{login_id}",
    response_model=AiProviderLoginStatusRead,
)
async def get_codex_login_status(
    login_id: str,
    ai_service: AiServiceDependency,
) -> AiProviderLoginStatusRead:
    return AiProviderLoginStatusRead(**ai_service.codex.login_status(login_id).__dict__)


@router.post("/ai/providers/codex/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_codex(ai_service: AiServiceDependency) -> Response:
    try:
        await ai_service.codex.logout()
    except AiProviderError as error:
        raise ai_http_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/ai/providers/gemini/login",
    response_model=GeminiProviderLoginRead,
)
async def start_gemini_login(
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> GeminiProviderLoginRead:
    save_setting(session, GEMINI_ENABLED_SETTING, "1")
    try:
        return GeminiProviderLoginRead(**(await ai_service.gemini.login()))
    except AiProviderError as error:
        raise ai_http_error(error) from error


@router.get(
    "/ai/providers/gemini/login/{login_id}",
    response_model=AiProviderLoginStatusRead,
)
async def get_gemini_login_status(
    login_id: str,
    ai_service: AiServiceDependency,
) -> AiProviderLoginStatusRead:
    return AiProviderLoginStatusRead(**ai_service.gemini.login_status(login_id).__dict__)


@router.post(
    "/ai/providers/gemini/login/{login_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_gemini_login(
    login_id: str,
    ai_service: AiServiceDependency,
) -> Response:
    await ai_service.gemini.cancel_login(login_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ai/providers/gemini/enable", status_code=status.HTTP_204_NO_CONTENT)
def enable_gemini(session: SessionDependency) -> Response:
    save_setting(session, GEMINI_ENABLED_SETTING, "1")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ai/providers/gemini/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_gemini(
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> Response:
    await ai_service.gemini.disconnect()
    save_setting(session, GEMINI_ENABLED_SETTING, "0")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ai-runs", response_model=list[AiRunRead])
def list_ai_runs(
    session: SessionDependency,
    daily_record_id: int | None = Query(default=None, ge=1),
    section_id: int | None = Query(default=None, ge=1),
    active_only: bool = False,
) -> list[AiRun]:
    if daily_record_id is None and section_id is None:
        raise HTTPException(status_code=422, detail="必须指定学习记录或小节")
    conditions = []
    if daily_record_id is not None:
        conditions.append(AiRun.daily_record_id == daily_record_id)
    if section_id is not None:
        conditions.append(AiRun.section_id == section_id)
    statement = select(AiRun).where(*conditions)
    if active_only:
        statement = statement.where(AiRun.status == AiRunStatus.RUNNING)
    return list(session.scalars(statement.order_by(AiRun.id.desc()).limit(20)))


@router.post("/ai-runs/{run_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_ai_run(run_id: int, session: SessionDependency) -> Response:
    run = session.get(AiRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    if run.status != AiRunStatus.RUNNING:
        raise HTTPException(status_code=409, detail="生成任务已经结束")
    run.status = AiRunStatus.FAILED
    run.error_text = "生成任务已取消，可从原操作重新生成。"
    session.commit()
    cancel_active_ai_run(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/daily-records/{record_id}/ai-review/{kind}",
    response_model=AiInteractionRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_ai_review(
    record_id: int,
    kind: AiInteractionKind,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> AiInteraction:
    record = load_daily_record(session, record_id)
    previous_records = load_previous_records(session, record)
    task = AiRunTask(kind.value)
    memory_context, source_refs, material_context = await grounded_task_context(
        session, ai_service, record, task
    )
    builder = (
        recall_review_prompt
        if kind == AiInteractionKind.RECALL_REVIEW
        else reconstruction_review_prompt
    )
    task_prompt = builder(record, previous_records)
    prompt = f"{memory_context}\n\n{task_prompt}"
    try:
        result = await run_codex(
            session,
            ai_service,
            task=task,
            prompt=prompt,
            context_snapshot=memory_context,
            course_id=record.section.chapter.course_id,
            section_id=record.section_id,
            daily_record_id=record.id,
            output_schema=TEXT_OUTPUT_SCHEMA,
            source_refs=source_refs,
            material_context_session=material_context,
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error
    interaction = AiInteraction(
        daily_record=record,
        kind=kind,
        prompt_text=prompt,
        feedback_text=normalize_ai_markdown(result.text),
    )
    session.add(interaction)
    session.commit()
    return interaction


@router.post(
    "/daily-records/{record_id}/ai-practice",
    response_model=ExerciseRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_ai_practice(
    record_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> Exercise:
    record = load_daily_record(session, record_id)
    memory_context, source_refs, material_context = await grounded_task_context(
        session, ai_service, record, AiRunTask.PRACTICE_GENERATION
    )
    prompt = (
        f"{memory_context}\n\n"
        f"{practice_generation_prompt(record, load_previous_records(session, record))}"
    )
    try:
        result = await run_codex(
            session,
            ai_service,
            task=AiRunTask.PRACTICE_GENERATION,
            prompt=prompt,
            context_snapshot=memory_context,
            course_id=record.section.chapter.course_id,
            section_id=record.section_id,
            daily_record_id=record.id,
            output_schema=PRACTICE_OUTPUT_SCHEMA,
            source_refs=source_refs,
            material_context_session=material_context,
            payload_validator=validate_practice_output,
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error
    payload = result.payload or parse_structured_output(result.text)
    items = payload.get("items")

    rendered_questions = "\n\n".join(
        f"### 第 {item['position']} 题 · {item['difficulty']}\n\n{item['stem_markdown']}"
        for item in items
    )
    exercise = Exercise(
        daily_record=record,
        generation_prompt=prompt,
        ai_questions=normalize_ai_markdown(rendered_questions),
        format_version=2,
        status="draft",
    )
    exercise_items: list[ExerciseItem] = []
    for item in items:
        options = [
            {**option, "label": normalize_ai_markdown(str(option.get("label", "")))}
            for option in item["options"]
        ]
        answer_key = {
            **item["answer_key"],
            "answer_markdown": normalize_ai_markdown(
                str(item["answer_key"].get("answer_markdown", ""))
            ),
        }
        exercise_items.append(
            ExerciseItem(
                position=item["position"],
                item_type=ExerciseItemType(item["item_type"]),
                difficulty=ExerciseDifficulty(item["difficulty"]),
                stem_markdown=normalize_ai_markdown(item["stem_markdown"]),
                options_json=json.dumps(options, ensure_ascii=False),
                answer_key_json=json.dumps(answer_key, ensure_ascii=False),
                rubric_markdown=normalize_ai_markdown(item["rubric_markdown"]),
                source_refs_json=json.dumps(item["source_refs"], ensure_ascii=False),
                response=ExerciseResponse(),
            )
        )
    exercise.items = exercise_items
    session.add(exercise)
    session.commit()
    return exercise


@router.post("/exercises/{exercise_id}/ai-grade", response_model=ExerciseRead)
async def generate_ai_grading(
    exercise_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> Exercise:
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    structured = exercise.format_version >= 2 and bool(exercise.items)
    if structured:
        unanswered = [
            item.position
            for item in exercise.items
            if item.response is None
            or not (
                item.response.answer_markdown.strip()
                or json.loads(item.response.selected_options_json or "[]")
            )
        ]
        if unanswered:
            raise HTTPException(
                status_code=422,
                detail=f"请先完成第 {', '.join(map(str, unanswered))} 题",
            )
    elif not exercise.ai_questions.strip() or not exercise.user_answers.strip():
        raise HTTPException(status_code=422, detail="请先保存练习题目和我的答案")
    record = load_daily_record(session, exercise.daily_record_id)
    memory_context, source_refs, material_context = await grounded_task_context(
        session, ai_service, record, AiRunTask.EXERCISE_GRADING
    )
    prompt = f"{memory_context}\n\n{grading_prompt(record, exercise)}"
    try:
        result = await run_codex(
            session,
            ai_service,
            task=AiRunTask.EXERCISE_GRADING,
            prompt=prompt,
            context_snapshot=memory_context,
            course_id=record.section.chapter.course_id,
            section_id=record.section_id,
            daily_record_id=record.id,
            exercise_id=exercise.id,
            output_schema=GRADING_OUTPUT_SCHEMA if structured else TEXT_OUTPUT_SCHEMA,
            source_refs=source_refs,
            material_context_session=material_context,
            payload_validator=(
                grading_output_validator({item.position for item in exercise.items})
                if structured
                else None
            ),
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error
    exercise.grading_prompt = prompt
    exercise.ai_feedback = "" if structured else normalize_ai_markdown(result.text)
    if structured:
        payload = result.payload or parse_structured_output(result.text)
        results = payload.get("results")
        by_position = {
            int(item["position"]): item for item in results if isinstance(item, dict)
        }
        for item in exercise.items:
            graded = by_position.get(item.position)
            if graded is None or item.response is None:
                raise RuntimeError("validated grading result became inconsistent")
            item.response.verdict = deterministic_choice_verdict(item) or str(
                graded["verdict"]
            )
            item.response.score = None
            item.response.feedback_markdown = normalize_ai_markdown(
                str(graded["feedback_markdown"])
            )
            item.response.status = ExerciseResponseStatus.GRADED
        exercise.status = "graded"
        review_node = next(
            (node for node in record.workflow_nodes if node.node_key == WorkflowNodeKey.REVIEW),
            None,
        )
        if review_node is not None:
            review_node.status = WorkflowNodeStatus.PENDING
    session.commit()
    return exercise


@router.post(
    "/daily-records/{record_id}/ai-preview-questions",
    response_model=PreviewQuestionSetRead,
)
async def generate_ai_preview_questions(
    record_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> PreviewQuestionSet:
    record = load_daily_record(session, record_id)
    memory_context, source_refs, material_context = await grounded_task_context(
        session, ai_service, record, AiRunTask.PREVIEW_QUESTIONS
    )
    prompt = f"""{memory_context}

{preview_questions_prompt(record, load_previous_records(session, record))}

请按 JSON 结构返回，questions 必须恰好包含 3 个字符串。"""
    try:
        result = await run_codex(
            session,
            ai_service,
            task=AiRunTask.PREVIEW_QUESTIONS,
            prompt=prompt,
            context_snapshot=memory_context,
            course_id=record.section.chapter.course_id,
            section_id=record.section_id,
            daily_record_id=record.id,
            output_schema=PREVIEW_OUTPUT_SCHEMA,
            source_refs=source_refs,
            material_context_session=material_context,
            payload_validator=validate_preview_output,
        )
        questions = (result.payload or parse_structured_output(result.text))["questions"]
    except AiProviderError as error:
        raise ai_http_error(error) from error
    question_set = record.preview_question_set
    if question_set is None:
        question_set = PreviewQuestionSet(daily_record=record, prompt_text=prompt)
        session.add(question_set)
    question_set.prompt_text = prompt
    question_set.question_1, question_set.question_2, question_set.question_3 = questions
    session.commit()
    return question_set


async def generate_section_note_result(
    record: DailyRecord,
    session: Session,
    ai_service: AiService,
    payload: SectionNoteGenerateRequest,
    existing_run: AiRun | None = None,
) -> AiGeneratedTextRead:
    memory_context, source_refs, material_context = await grounded_task_context(
        session, ai_service, record, AiRunTask.SECTION_NOTE_DRAFT
    )
    note_prompt = section_note_prompt(
        record,
        load_all_section_records(session, record),
        payload.existing_content,
        payload.mode,
    )
    prompt = f"{memory_context}\n\n{note_prompt}"
    result = await run_codex(
        session,
        ai_service,
        task=AiRunTask.SECTION_NOTE_DRAFT,
        prompt=prompt,
        context_snapshot=memory_context,
        course_id=record.section.chapter.course_id,
        section_id=record.section_id,
        daily_record_id=record.id,
        output_schema=TEXT_OUTPUT_SCHEMA,
        source_refs=source_refs,
        material_context_session=material_context,
        existing_run=existing_run,
    )
    return AiGeneratedTextRead(
        text=normalize_ai_markdown(result.text),
        provider=AiProvider.CODEX,
        model=result.model,
        context_snapshot=memory_context,
        source_refs=[
            AiSourceReferenceRead(task=AiRunTask.SECTION_NOTE_DRAFT.value, **reference)
            for reference in result.source_refs
        ],
        material_revision=material_context.revision if material_context is not None else 0,
        material_manifest_hash=(
            material_context.manifest_hash if material_context is not None else ""
        ),
    )


@router.post(
    "/daily-records/{record_id}/ai-section-note",
    response_model=AiGeneratedTextRead,
)
async def generate_ai_section_note(
    record_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
    payload: SectionNoteGenerateRequest | None = None,
) -> AiGeneratedTextRead:
    record = load_daily_record(session, record_id)
    try:
        return await generate_section_note_result(
            record,
            session,
            ai_service,
            payload or SectionNoteGenerateRequest(),
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error


async def run_section_note_background(
    request: Request,
    run_id: int,
    record_id: int,
    payload: SectionNoteGenerateRequest,
) -> None:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        run = session.get(AiRun, run_id)
        if run is None:
            return
        try:
            record = load_daily_record(session, record_id)
            await generate_section_note_result(
                record,
                session,
                request.app.state.ai_service,
                payload,
                existing_run=run,
            )
        except asyncio.CancelledError:
            if run.status == AiRunStatus.RUNNING:
                run.status = AiRunStatus.FAILED
                run.error_text = "服务已关闭，原生成任务已中断，请重新生成。"
                session.commit()
            raise
        except Exception as error:
            session.expire_all()
            stored = session.get(AiRun, run_id)
            if stored is not None and stored.status == AiRunStatus.RUNNING:
                stored.status = AiRunStatus.FAILED
                stored.error_text = str(error) or "笔记生成失败"
                session.commit()


@router.post(
    "/daily-records/{record_id}/ai-section-note-runs",
    response_model=AiRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_ai_section_note(
    record_id: int,
    request: Request,
    session: SessionDependency,
    payload: SectionNoteGenerateRequest | None = None,
) -> AiRun:
    record = load_daily_record(session, record_id)
    existing = session.scalar(
        select(AiRun)
        .where(
            AiRun.daily_record_id == record.id,
            AiRun.task == AiRunTask.SECTION_NOTE_DRAFT,
            AiRun.status == AiRunStatus.RUNNING,
        )
        .order_by(AiRun.id.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    preference = codex_preference(session)
    run = AiRun(
        provider="codex",
        task=AiRunTask.SECTION_NOTE_DRAFT,
        status=AiRunStatus.RUNNING,
        course_id=record.section.chapter.course_id,
        section_id=record.section_id,
        daily_record_id=record.id,
        model=preference.model,
        reasoning_effort=preference.reasoning_effort,
        context_snapshot="",
        prompt_text="",
        source_refs_json="[]",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    task = asyncio.create_task(
        run_section_note_background(
            request,
            run.id,
            record.id,
            payload or SectionNoteGenerateRequest(),
        )
    )
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)
    return run


@router.get("/ai-runs/{run_id}/result", response_model=AiRunResultRead)
def ai_run_result(run_id: int, session: SessionDependency) -> AiRunResultRead:
    run = session.get(AiRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    generated: AiGeneratedTextRead | None = None
    if run.status == AiRunStatus.COMPLETED:
        try:
            references = json.loads(run.source_refs_json or "[]")
        except json.JSONDecodeError:
            references = []
        generated = AiGeneratedTextRead(
            text=normalize_ai_markdown(run.output_text),
            provider=run.provider.value,
            model=run.model,
            context_snapshot=run.context_snapshot,
            source_refs=[
                AiSourceReferenceRead(task=run.task.value, **reference)
                for reference in references
            ],
            material_revision=run.material_revision,
            material_manifest_hash=run.material_manifest_hash,
        )
    return AiRunResultRead(run=AiRunRead.model_validate(run), result=generated)


@router.post("/sections/{section_id}/ai-polish-note", response_model=AiGeneratedTextRead)
async def polish_section_note(
    section_id: int,
    payload: NotePolishRequest,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> AiGeneratedTextRead:
    if not gemini_enabled(session):
        raise HTTPException(status_code=409, detail="请先在设置中重新连接 Antigravity")
    section = require_section(session, section_id)
    chapter = require_chapter(session, section.chapter_id)
    course = require_course(session, chapter.course_id)
    context = f"""课程：{course.name}
章节：{chapter.title}
小节：{section.title}
补充上下文：{payload.context or "无"}"""
    prompt = f"""你是一名专业的中文技术内容编辑者，同时熟悉 Obsidian Markdown。
请基于原笔记的实际内容进行深入语言润色、逻辑整理和 Obsidian 格式优化。
这不是简单排版，也不是重新生成一篇新笔记。必须以原笔记为唯一内容基础，
完整保留原有知识和详细程度。

优先级依次为：知识内容完整、原意和专业含义准确、逻辑关系清晰、中文表达自然、
Obsidian 中的结构和视觉可读性。

【内容润色】
1. 保留全部独有知识点、定义、公式、推导步骤、成立条件、例子、拓展说明、限定语和结论。
不得为了简洁而删除内容。
2. 可以重写生硬、含混、重复或不自然的句子，使中文表达更准确、连贯和易读。
3. 可以调整段落顺序，补充不引入新知识的过渡语，使概念、公式和章节之间关系更清楚。
4. 只有语义完全重复时才可以合并；相似但承担不同解释作用的内容必须保留。
5. 对过长段落合理拆分，对过碎短句适当合并，避免大量缺少联系的项目符号。
6. 统一术语、符号、变量命名和叙述视角，不得擅自改变公式、数值、条件和结论。
7. 不承担事实核查或内容纠错任务。不得新增原文未明确写出的疑点、错误说明、
“待核对”标记或外部知识；即使你怀疑某处有误，也只保留原意并改善表达。

【Obsidian 结构与格式】
8. 使用连续、清晰的 Markdown 标题层级，标题应概括内容，不得无故跳级。
9. 合理使用段落、列表、编号、粗体、引用、表格和分隔线；表格只用于真正的比较。
10. 仅在确实能提高阅读效率时适度使用 Obsidian 原生 Callout：`[!abstract]` 用于宏观总结，`[!info]`
用于定义或重要说明，`[!tip]` 用于理解方法，`[!warning]` 用于条件、限制和易混淆点，
`[!example]` 用于例子，`[!note]` 用于补充说明。不要把普通正文全部放入 Callout。
11. 不新增无依据的 `[[内部链接]]`，原文已有内部链接必须保留。
12. 不新增 YAML、标签、目录、Emoji、HTML、CSS 或与内容无关的装饰。

【数学与代码】
13. 行内公式统一使用 `$...$`，独立公式统一使用 `$$...$$`。
14. 不使用 `\\(...\\)` 或 `\\[...\\]`，保证 LaTeX 命令、花括号、上下标和矩阵完整。
15. 不得删除公式的符号解释、成立条件和推导步骤。
16. 代码块必须保留语言标识、缩进和原始语义。

【输出】
17. 输出一份完整、润色后的中文 Markdown 笔记。
18. 不输出修改说明、差异摘要、评价、前言或结尾说明。
19. 不得只输出发生变化的部分。
20. 输出前逐段检查：新增文字只能用于衔接、结构和语言组织，不能改变或扩展知识事实。

{context}

【原始笔记】
{payload.content}"""
    try:
        result = await run_gemini(
            session,
            ai_service,
            prompt=prompt,
            context_snapshot=context,
            course_id=course.id,
            section_id=section.id,
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error
    return AiGeneratedTextRead(
        text=normalize_ai_markdown(result.text),
        provider="gemini",
        model=result.model,
        context_snapshot=context,
    )


@router.get("/courses/{course_id}/learning-memory", response_model=CourseLearningMemoryRead)
def get_course_learning_memory(
    course_id: int,
    session: SessionDependency,
) -> CourseLearningMemoryRead:
    course = load_course_with_memories(session, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    course_memory = course.memory or ensure_course_memory(session, course.id)
    section_memories = [
        section.memory or ensure_section_memory(session, section.id)
        for chapter in course.chapters
        for section in chapter.sections
    ]
    chapter_memories = [
        chapter.memory or ensure_chapter_memory(session, chapter.id) for chapter in course.chapters
    ]
    session.commit()
    return CourseLearningMemoryRead(
        course=CourseMemoryRead.model_validate(course_memory),
        chapters=[ChapterMemoryRead.model_validate(memory) for memory in chapter_memories],
        sections=[SectionMemoryRead.model_validate(memory) for memory in section_memories],
    )


@router.put("/courses/{course_id}/learning-memory", response_model=CourseMemoryRead)
def update_course_learning_memory(
    course_id: int,
    payload: CourseMemoryUpdate,
    session: SessionDependency,
) -> CourseMemory:
    require_course(session, course_id)
    memory = ensure_course_memory(session, course_id)
    for field, value in payload.model_dump().items():
        setattr(memory, field, value)
    memory.version += 1
    session.commit()
    return memory


@router.post("/sections/{section_id}/learning-memory/refresh", response_model=SectionMemoryRead)
async def generate_section_learning_memory(
    section_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> SectionMemory:
    try:
        return await refresh_section_memory(session, ai_service, section_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AiProviderError as error:
        raise ai_http_error(error) from error


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(session: SessionDependency) -> list[CourseSummary]:
    section_summary = (
        select(
            Chapter.course_id.label("course_id"),
            func.count(Section.id).label("total_sections"),
            func.sum(case((Section.status == SectionStatus.COMPLETED, 1), else_=0)).label(
                "completed_sections"
            ),
            func.sum(case((Section.status == SectionStatus.IN_PROGRESS, 1), else_=0)).label(
                "in_progress_sections"
            ),
        )
        .outerjoin(Section, Section.chapter_id == Chapter.id)
        .group_by(Chapter.course_id)
        .subquery()
    )
    activity_summary = (
        select(
            Chapter.course_id.label("course_id"),
            func.max(DailyRecord.updated_at).label("last_study_at"),
        )
        .join(Section, Section.chapter_id == Chapter.id)
        .join(DailyRecord, DailyRecord.section_id == Section.id)
        .group_by(Chapter.course_id)
        .subquery()
    )
    total_sections = func.coalesce(section_summary.c.total_sections, 0)
    in_progress_sections = func.coalesce(section_summary.c.in_progress_sections, 0)
    course_bucket = case(
        (Course.completed_at.is_not(None), 2),
        ((in_progress_sections > 0) | activity_summary.c.last_study_at.is_not(None), 0),
        else_=1,
    )
    rows = session.execute(
        select(
            Course,
            total_sections,
            func.coalesce(section_summary.c.completed_sections, 0),
            in_progress_sections,
            activity_summary.c.last_study_at,
        )
        .outerjoin(section_summary, section_summary.c.course_id == Course.id)
        .outerjoin(activity_summary, activity_summary.c.course_id == Course.id)
        .order_by(
            course_bucket,
            case(
                (course_bucket == 0, activity_summary.c.last_study_at),
                (course_bucket == 1, Course.created_at),
                else_=Course.completed_at,
            ).desc(),
            Course.id.desc(),
        )
    )
    return [
        CourseSummary(
            id=course.id,
            name=course.name,
            description=course.description,
            learning_goal=course.learning_goal,
            completed_at=course.completed_at,
            completion_summary=course.completion_summary,
            completion_summary_version=course.completion_summary_version,
            total_sections=total_sections,
            completed_sections=completed_sections,
            in_progress_sections=in_progress_sections,
            course_state=(
                "completed"
                if course.completed_at is not None
                else "active"
                if in_progress_sections > 0 or last_study_at is not None
                else "not_started"
            ),
            last_study_at=last_study_at,
            created_at=course.created_at,
        )
        for course, total_sections, completed_sections, in_progress_sections, last_study_at in rows
    ]


@router.post("/courses", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreate, session: SessionDependency) -> Course:
    course = Course(**payload.model_dump())
    session.add(course)
    session.commit()
    return course


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, session: SessionDependency) -> Course:
    return load_course_detail(session, course_id)


@router.patch("/courses/{course_id}", response_model=CourseRead)
def update_course(course_id: int, payload: CourseUpdate, session: SessionDependency) -> Course:
    course = require_course(session, course_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(course, field, value)
    session.commit()
    return course


@router.post("/courses/{course_id}/complete", response_model=CourseCompletionRead)
async def complete_course(
    course_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> CourseCompletionRead:
    course = load_course_with_memories(session, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    sections = [section for chapter in course.chapters for section in chapter.sections]
    if not sections:
        raise HTTPException(status_code=422, detail="课程还没有小节")
    incomplete = [
        section.title
        for section in sections
        if section.status != SectionStatus.COMPLETED
    ]
    if incomplete:
        raise HTTPException(
            status_code=409,
            detail=f"还有 {len(incomplete)} 个小节未完成，不能完成课程",
        )
    memory = course.memory or ensure_course_memory(session, course.id)
    blocks = [
        f"课程：{course.name}",
        f"学习目标：{course.learning_goal or '暂无'}",
        f"课程记忆：{memory.overview or '暂无'}",
        f"核心概念：{memory.core_concepts or '暂无'}",
        f"关键方法：{memory.key_methods or '暂无'}",
        f"未解决问题：{memory.unresolved_questions or '暂无'}",
    ]
    for chapter in course.chapters:
        chapter_memory = chapter.memory.summary if chapter.memory is not None else "暂无"
        blocks.append(f"\n## {chapter.title}\n{chapter_memory}")
        for section in chapter.sections:
            summary = section.memory.summary if section.memory is not None else "暂无摘要"
            blocks.append(f"- {section.title}：{summary}")
    source = "\n".join(blocks)
    learner_profile = setting_value(session, "learner_profile") or "暂无"
    prompt = (
        f"【学习者背景】\n{learner_profile}\n\n"
        f"{course_completion_prompt(source)}"
    )
    try:
        result = await run_codex(
            session,
            ai_service,
            task=AiRunTask.COURSE_COMPLETION,
            prompt=prompt,
            context_snapshot=source,
            course_id=course.id,
            section_id=None,
            output_schema=TEXT_OUTPUT_SCHEMA,
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error
    course.completed_at = datetime.now()
    course.completion_summary = normalize_ai_markdown(result.text)
    course.completion_summary_version += 1
    session.commit()
    return CourseCompletionRead(
        course_id=course.id,
        completed_at=course.completed_at,
        completion_summary=course.completion_summary,
        completion_summary_version=course.completion_summary_version,
    )


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    session: SessionDependency,
    request: Request,
) -> Response:
    material_ids = list(
        session.scalars(select(LearningMaterial.id).where(LearningMaterial.course_id == course_id))
    )
    session.delete(require_course(session, course_id))
    session.commit()
    remove_material_files(request, material_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/courses/{course_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_chapter(course_id: int, payload: ChapterCreate, session: SessionDependency) -> Chapter:
    course = require_course(session, course_id)
    course.completed_at = None
    position = payload.position
    if position is None:
        current_max = session.scalar(
            select(func.max(Chapter.position)).where(Chapter.course_id == course_id)
        )
        position = 0 if current_max is None else current_max + 1
    chapter = Chapter(course_id=course_id, title=payload.title, position=position)
    session.add(chapter)
    session.commit()
    return chapter


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(chapter_id: int, payload: ChapterUpdate, session: SessionDependency) -> Chapter:
    chapter = require_chapter(session, chapter_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(chapter, field, value)
    session.commit()
    return chapter


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: int,
    session: SessionDependency,
    request: Request,
) -> Response:
    chapter = require_chapter(session, chapter_id)
    chapter.course.completed_at = None
    material_ids = list(
        session.scalars(
            select(LearningMaterial.id).where(LearningMaterial.chapter_id == chapter_id)
        )
    )
    session.delete(chapter)
    session.commit()
    remove_material_files(request, material_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/chapters/{chapter_id}/sections",
    response_model=SectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_section(chapter_id: int, payload: SectionCreate, session: SessionDependency) -> Section:
    chapter = require_chapter(session, chapter_id)
    chapter.course.completed_at = None
    position = payload.position
    if position is None:
        current_max = session.scalar(
            select(func.max(Section.position)).where(Section.chapter_id == chapter_id)
        )
        position = 0 if current_max is None else current_max + 1
    section = Section(chapter_id=chapter_id, title=payload.title, position=position)
    session.add(section)
    session.commit()
    return section


@router.patch("/sections/{section_id}", response_model=SectionRead)
def update_section(section_id: int, payload: SectionUpdate, session: SessionDependency) -> Section:
    section = require_section(session, section_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(section, field, value)
    if section.status != SectionStatus.COMPLETED:
        section.chapter.course.completed_at = None
    session.commit()
    return section


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    section_id: int,
    session: SessionDependency,
    request: Request,
) -> Response:
    section = require_section(session, section_id)
    section.chapter.course.completed_at = None
    material_ids = list(
        session.scalars(
            select(LearningMaterial.id).where(LearningMaterial.section_id == section_id)
        )
    )
    session.delete(section)
    session.commit()
    remove_material_files(request, material_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sections/{section_id}/daily-records/today", response_model=DailyRecordRead)
def open_today_record(
    section_id: int,
    session: SessionDependency,
    current_date: CurrentDateDependency,
    continue_completed: Annotated[bool, Query()] = False,
) -> DailyRecordRead:
    section = session.scalar(
        select(Section).where(Section.id == section_id).options(joinedload(Section.chapter))
    )
    if section is None:
        raise HTTPException(status_code=404, detail="小节不存在")
    if section.status == SectionStatus.COMPLETED and not continue_completed:
        raise HTTPException(status_code=409, detail="已完成小节需要确认后才能继续学习")
    if section.status == SectionStatus.COMPLETED and continue_completed:
        section.chapter.course.completed_at = None

    record = session.scalar(
        select(DailyRecord)
        .where(DailyRecord.section_id == section_id, DailyRecord.study_date == current_date)
        .options(selectinload(DailyRecord.workflow_nodes))
    )
    if record is None:
        record = DailyRecord(section=section, study_date=current_date)
        record.workflow_nodes = [
            WorkflowNodeState(node_key=node_key, position=position)
            for position, (node_key, _) in enumerate(WORKFLOW_NODES, start=1)
        ]
        session.add(record)
        session.flush()
        record.material_selections = [
            DailyRecordMaterial(
                material_id=material.id,
                enabled=True,
                content_hash=material.content_hash,
            )
            for material in scoped_materials(
                session,
                course_id=section.chapter.course_id,
                chapter_id=section.chapter_id,
                section_id=section.id,
            )
            if material.status == MaterialStatus.READY
        ]
        if section.status == SectionStatus.NOT_STARTED:
            section.status = SectionStatus.IN_PROGRESS
        session.commit()

    if session.dirty:
        session.commit()

    return daily_record_response(session, load_daily_record(session, record.id))


@router.get("/daily-records/{record_id}", response_model=DailyRecordRead)
def get_daily_record(record_id: int, session: SessionDependency) -> DailyRecordRead:
    return daily_record_response(session, load_daily_record(session, record_id))


@router.patch("/daily-records/{record_id}", response_model=DailyRecordRead)
def update_daily_record(
    record_id: int,
    payload: DailyRecordContentUpdate,
    session: SessionDependency,
) -> DailyRecordRead:
    record = load_daily_record(session, record_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(record, field, value)
    session.commit()
    return daily_record_response(session, load_daily_record(session, record_id))


@router.patch("/workflow-nodes/{node_id}", response_model=WorkflowNodeRead)
def update_workflow_node(
    node_id: int,
    payload: WorkflowNodeUpdate,
    session: SessionDependency,
    confirm_skip: Annotated[bool, Query()] = False,
) -> WorkflowNodeState:
    node = session.get(WorkflowNodeState, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="流程节点不存在")
    if node.node_key in {WorkflowNodeKey.DAILY_CLOSE, WorkflowNodeKey.DAILY_COMPLETE}:
        raise HTTPException(status_code=422, detail="请使用今日完成操作")
    if payload.status == WorkflowNodeStatus.SKIPPED:
        if node.node_key != WorkflowNodeKey.PRACTICE:
            raise HTTPException(status_code=422, detail="只有练习节点可以跳过")
        if not confirm_skip:
            raise HTTPException(status_code=409, detail="跳过练习节点需要确认")
    node.status = payload.status
    session.commit()
    return node


@router.post("/daily-records/{record_id}/complete", response_model=DailyRecordRead)
async def complete_daily_record(
    record_id: int,
    session: SessionDependency,
    ai_service: AiServiceDependency,
) -> DailyRecordRead:
    record = load_daily_record(session, record_id)
    task_context = build_task_context(
        session,
        record,
        AiRunTask.DAILY_SUMMARY,
        include_material_evidence=False,
    )
    prompt = f"{task_context.text}\n\n{daily_summary_prompt(daily_summary_source(session, record))}"
    try:
        result = await run_codex(
            session,
            ai_service,
            task=AiRunTask.DAILY_SUMMARY,
            prompt=prompt,
            context_snapshot=task_context.text,
            course_id=record.section.chapter.course_id,
            section_id=record.section_id,
            daily_record_id=record.id,
            output_schema=DAILY_SUMMARY_OUTPUT_SCHEMA,
            source_refs=task_context.source_refs,
        )
    except AiProviderError as error:
        raise ai_http_error(error) from error
    daily_complete_node = next(
        node
        for node in record.workflow_nodes
        if node.node_key in {WorkflowNodeKey.DAILY_CLOSE, WorkflowNodeKey.DAILY_COMPLETE}
    )
    daily_complete_node.status = WorkflowNodeStatus.COMPLETED
    record.is_completed = True
    record.context_summary = normalize_ai_markdown(result.text)
    apply_daily_summary_memory(session, record, result.payload or {})
    session.commit()
    return daily_record_response(session, load_daily_record(session, record_id))


@router.post(
    "/daily-records/{record_id}/ai-prompts/{kind}",
    response_model=AiInteractionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_interaction(
    record_id: int,
    kind: AiInteractionKind,
    session: SessionDependency,
) -> AiInteraction:
    record = load_daily_record(session, record_id)
    previous_records = load_previous_records(session, record)
    prompt_builders = {
        AiInteractionKind.RECALL_REVIEW: recall_review_prompt,
        AiInteractionKind.RECONSTRUCTION_REVIEW: reconstruction_review_prompt,
    }
    task_prompt = prompt_builders[kind](record, previous_records)
    interaction = AiInteraction(
        daily_record=record,
        kind=kind,
        prompt_text=(f"{course_context(session, record, AiRunTask(kind.value))}\n\n{task_prompt}"),
    )
    session.add(interaction)
    session.commit()
    return interaction


@router.patch("/ai-interactions/{interaction_id}", response_model=AiInteractionRead)
def update_ai_interaction(
    interaction_id: int,
    payload: AiInteractionUpdate,
    session: SessionDependency,
) -> AiInteraction:
    interaction = session.get(AiInteraction, interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="AI 提示词记录不存在")
    interaction.feedback_text = payload.feedback_text
    session.commit()
    return interaction


@router.post(
    "/daily-records/{record_id}/exercises",
    response_model=ExerciseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_exercise(record_id: int, session: SessionDependency) -> Exercise:
    record = load_daily_record(session, record_id)
    task_prompt = practice_generation_prompt(record, load_previous_records(session, record))
    exercise = Exercise(
        daily_record=record,
        generation_prompt=(
            f"{course_context(session, record, AiRunTask.PRACTICE_GENERATION)}\n\n{task_prompt}"
        ),
    )
    session.add(exercise)
    session.commit()
    return exercise


@router.patch("/exercises/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    exercise_id: int,
    payload: ExerciseUpdate,
    session: SessionDependency,
) -> Exercise:
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(exercise, field, value)
    session.commit()
    return exercise


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_legacy_exercise(exercise_id: int, session: SessionDependency) -> Response:
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    if exercise.format_version >= 2:
        raise HTTPException(status_code=409, detail="当前只支持删除旧版练习")
    session.delete(exercise)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/exercise-items/{item_id}/response", response_model=ExerciseRead)
def update_exercise_response(
    item_id: int,
    payload: ExerciseResponseUpdate,
    session: SessionDependency,
) -> Exercise:
    item = session.get(ExerciseItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="练习题不存在")
    selected = payload.selected_options
    option_ids = {str(option.get("id", "")) for option in item.options}
    if not set(selected).issubset(option_ids):
        raise HTTPException(status_code=422, detail="选择题选项无效")
    if item.item_type == ExerciseItemType.SINGLE_CHOICE and len(selected) > 1:
        raise HTTPException(status_code=422, detail="单选题只能选择一个选项")
    if item.item_type not in {
        ExerciseItemType.SINGLE_CHOICE,
        ExerciseItemType.MULTIPLE_CHOICE,
    } and selected:
        raise HTTPException(status_code=422, detail="当前题型不使用选项作答")

    response = item.response
    if response is None:
        response = ExerciseResponse(exercise_item=item)
        session.add(response)
    response.answer_markdown = payload.answer_markdown
    response.selected_options_json = json.dumps(selected, ensure_ascii=False)
    response.status = (
        ExerciseResponseStatus.DRAFT
        if payload.answer_markdown.strip() or selected
        else ExerciseResponseStatus.UNANSWERED
    )
    response.verdict = ""
    response.feedback_markdown = ""
    response.score = None
    item.exercise.status = "draft"
    item.exercise.user_answers = "\n\n".join(
        f"### 第 {saved.position} 题\n\n"
        + (
            f"选择：{', '.join(saved.response.selected_options)}"
            if saved.response and saved.response.selected_options
            else saved.response.answer_markdown
            if saved.response
            else "未作答"
        )
        for saved in item.exercise.items
    )
    session.commit()
    return item.exercise


@router.post("/exercises/{exercise_id}/complete", response_model=ExerciseRead)
def complete_exercise(exercise_id: int, session: SessionDependency) -> Exercise:
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    if exercise.format_version < 2 or not exercise.items:
        raise HTTPException(status_code=422, detail="旧版练习请使用原有保存方式")
    unanswered = [
        item.position
        for item in exercise.items
        if item.response is None
        or not (
            item.response.answer_markdown.strip()
            or json.loads(item.response.selected_options_json or "[]")
        )
    ]
    if unanswered:
        raise HTTPException(
            status_code=422,
            detail=f"请先完成第 {', '.join(map(str, unanswered))} 题",
        )
    for item in exercise.items:
        if item.response is not None and item.response.status != ExerciseResponseStatus.GRADED:
            item.response.status = ExerciseResponseStatus.SUBMITTED
    exercise.status = "submitted"
    record = load_daily_record(session, exercise.daily_record_id)
    practice_node = next(
        (node for node in record.workflow_nodes if node.node_key == WorkflowNodeKey.PRACTICE),
        None,
    )
    if practice_node is not None:
        practice_node.status = WorkflowNodeStatus.COMPLETED
    session.commit()
    return exercise


@router.post("/exercises/{exercise_id}/grading-prompt", response_model=ExerciseRead)
def create_grading_prompt(exercise_id: int, session: SessionDependency) -> Exercise:
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    if not exercise.ai_questions.strip() or not exercise.user_answers.strip():
        raise HTTPException(status_code=422, detail="请先保存 AI 题目和我的答案")
    record = load_daily_record(session, exercise.daily_record_id)
    exercise.grading_prompt = (
        f"{course_context(session, record, AiRunTask.EXERCISE_GRADING)}\n\n"
        f"{grading_prompt(record, exercise)}"
    )
    session.commit()
    return exercise


@router.post(
    "/exercises/{exercise_id}/mistakes",
    response_model=MistakeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_mistake(
    exercise_id: int,
    payload: MistakeCreate,
    session: SessionDependency,
) -> Mistake:
    exercise = session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    if payload.exercise_item_id is not None and not any(
        item.id == payload.exercise_item_id for item in exercise.items
    ):
        raise HTTPException(status_code=422, detail="错题和练习题不属于同一组练习")
    mistake = Mistake(exercise=exercise, **payload.model_dump())
    session.add(mistake)
    session.commit()
    return mistake


@router.patch("/mistakes/{mistake_id}", response_model=MistakeRead)
def update_mistake(
    mistake_id: int,
    payload: MistakeUpdate,
    session: SessionDependency,
) -> Mistake:
    mistake = session.get(Mistake, mistake_id)
    if mistake is None:
        raise HTTPException(status_code=404, detail="错题不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(mistake, field, value)
    session.commit()
    return mistake


@router.delete("/mistakes/{mistake_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mistake(mistake_id: int, session: SessionDependency) -> Response:
    mistake = session.get(Mistake, mistake_id)
    if mistake is None:
        raise HTTPException(status_code=404, detail="错题不存在")
    session.delete(mistake)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/mistakes", response_model=MistakeIndexRead)
def list_mistakes(session: SessionDependency) -> MistakeIndexRead:
    courses = session.scalars(
        select(Course)
        .options(selectinload(Course.chapters).selectinload(Chapter.sections))
        .order_by(Course.id)
    )
    mistakes = session.scalars(
        select(Mistake)
        .join(Mistake.exercise)
        .join(Exercise.daily_record)
        .join(DailyRecord.section)
        .join(Section.chapter)
        .join(Chapter.course)
        .options(
            joinedload(Mistake.exercise)
            .joinedload(Exercise.daily_record)
            .joinedload(DailyRecord.section)
            .joinedload(Section.chapter)
            .joinedload(Chapter.course)
        )
        .order_by(DailyRecord.study_date.desc(), Mistake.id.desc())
    )
    return MistakeIndexRead(
        courses=[
            MistakeScopeCourse(
                id=course.id,
                name=course.name,
                chapters=[
                    MistakeScopeChapter(
                        id=chapter.id,
                        title=chapter.title,
                        sections=[
                            MistakeScopeSection(id=section.id, title=section.title)
                            for section in chapter.sections
                        ],
                    )
                    for chapter in course.chapters
                ],
            )
            for course in courses
        ],
        items=[
            MistakeIndexItem(
                id=mistake.id,
                exercise_id=mistake.exercise_id,
                exercise_item_id=mistake.exercise_item_id,
                daily_record_id=mistake.exercise.daily_record_id,
                study_date=mistake.exercise.daily_record.study_date,
                course_id=mistake.exercise.daily_record.section.chapter.course_id,
                course_name=mistake.exercise.daily_record.section.chapter.course.name,
                chapter_id=mistake.exercise.daily_record.section.chapter_id,
                chapter_title=mistake.exercise.daily_record.section.chapter.title,
                section_id=mistake.exercise.daily_record.section_id,
                section_title=mistake.exercise.daily_record.section.title,
                original_question=mistake.original_question,
                user_answer=mistake.user_answer,
                error_content=mistake.error_content,
                error_type=mistake.error_type,
                correct_approach=mistake.correct_approach,
                cause_analysis=mistake.cause_analysis,
                status=mistake.status,
            )
            for mistake in mistakes
        ],
    )


@router.post(
    "/daily-records/{record_id}/preview-questions/prompt",
    response_model=PreviewQuestionSetRead,
)
def create_preview_questions_prompt(
    record_id: int,
    session: SessionDependency,
) -> PreviewQuestionSet:
    record = load_daily_record(session, record_id)
    prompt_text = (
        f"{course_context(session, record, AiRunTask.PREVIEW_QUESTIONS)}\n\n"
        f"{preview_questions_prompt(record, load_previous_records(session, record))}"
    )
    question_set = record.preview_question_set
    if question_set is None:
        question_set = PreviewQuestionSet(daily_record=record, prompt_text=prompt_text)
        session.add(question_set)
    else:
        question_set.prompt_text = prompt_text
    session.commit()
    return question_set


@router.put(
    "/daily-records/{record_id}/preview-questions",
    response_model=PreviewQuestionSetRead,
)
def save_preview_questions(
    record_id: int,
    payload: PreviewQuestionsUpdate,
    session: SessionDependency,
) -> PreviewQuestionSet:
    record = load_daily_record(session, record_id)
    question_set = record.preview_question_set
    if question_set is None:
        raise HTTPException(status_code=409, detail="请先生成明日预习问题提示词")
    for field, value in payload.model_dump().items():
        setattr(question_set, field, value)
    session.commit()
    return question_set


def load_material(session: Session, material_id: int) -> LearningMaterial:
    material = (
        session.execute(material_query().where(LearningMaterial.id == material_id))
        .unique()
        .scalar_one_or_none()
    )
    if material is None:
        raise HTTPException(status_code=404, detail="材料不存在")
    return material


def ensure_new_material(
    session: Session,
    *,
    course_id: int,
    digest: str,
) -> None:
    existing = session.scalar(
        select(LearningMaterial.id).where(
            LearningMaterial.course_id == course_id,
            LearningMaterial.source_hash == digest,
        )
    )
    if existing is not None:
        raise MaterialError("该材料已经添加到课程")


def is_first_material_in_scope(
    session: Session,
    *,
    course_id: int,
    chapter_id: int | None,
    section_id: int | None,
) -> bool:
    existing = session.scalar(
        select(LearningMaterial.id).where(
            LearningMaterial.course_id == course_id,
            LearningMaterial.chapter_id == chapter_id,
            LearningMaterial.section_id == section_id,
        )
    )
    return existing is None


@router.get("/materials", response_model=list[MaterialRead])
def list_materials(
    session: SessionDependency,
    course_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[MaterialRead]:
    query = material_query().order_by(
        LearningMaterial.course_id,
        LearningMaterial.chapter_id,
        LearningMaterial.section_id,
        LearningMaterial.is_primary.desc(),
        LearningMaterial.id.desc(),
    )
    if course_id is not None:
        query = query.where(LearningMaterial.course_id == course_id)
    return [material_read(material) for material in session.scalars(query).unique()]


@router.post(
    "/materials/pdf",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pdf_material(
    request: Request,
    session: SessionDependency,
    title: Annotated[str, Form(min_length=1, max_length=300)],
    course_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    chapter_id: Annotated[int | None, Form(gt=0)] = None,
    section_id: Annotated[int | None, Form(gt=0)] = None,
    is_primary: Annotated[bool, Form()] = False,
) -> MaterialRead:
    require_course(session, course_id)
    try:
        validate_scope(session, course_id, chapter_id, section_id)
        content = await file.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES:
            raise MaterialError("PDF 超过 50 MB 限制")
        if not content.startswith(b"%PDF"):
            raise MaterialError("请选择有效的 PDF 文件")
        digest = content_hash(content)
        ensure_new_material(session, course_id=course_id, digest=digest)
    except MaterialError as error:
        raise material_http_error(error) from error

    material = LearningMaterial(
        course_id=course_id,
        chapter_id=chapter_id,
        section_id=section_id,
        title=title.strip(),
        source_type=MaterialSourceType.PDF,
        original_name=file.filename or "material.pdf",
        source_hash=digest,
        content_hash="",
        parser_version=MATERIAL_PARSER_VERSION,
        is_primary=is_primary
        or is_first_material_in_scope(
            session,
            course_id=course_id,
            chapter_id=chapter_id,
            section_id=section_id,
        ),
    )
    session.add(material)
    session.flush()
    root = material_root(request)
    directory = storage_directory(root, material.id)
    directory.mkdir(parents=True, exist_ok=True)
    versions = directory / "versions"
    versions.mkdir(exist_ok=True)
    source_path = versions / f"{digest}.pdf"
    await run_in_threadpool(source_path.write_bytes, content)
    material.storage_path = str(source_path.relative_to(root.resolve()))
    try:
        chunks = await run_in_threadpool(extract_pdf, source_path)
        material.content_hash = revision_hash(digest, chunks)
        save_chunks(session, material, chunks)
        material.last_refresh_status = MaterialRefreshStatus.SUCCEEDED
        material.last_success_at = datetime.now()
    except MaterialError as error:
        material.status = MaterialStatus.FAILED
        material.error_text = str(error)
        material.last_refresh_status = MaterialRefreshStatus.FAILED
        material.last_refresh_error = str(error)
    material.last_refresh_at = datetime.now()
    set_primary(session, material)
    session.commit()
    return material_read(load_material(session, material.id))


@router.post(
    "/materials/url",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
)
def create_url_material(
    request: Request,
    payload: MaterialUrlCreate,
    session: SessionDependency,
) -> MaterialRead:
    require_course(session, payload.course_id)
    try:
        validate_scope(
            session,
            payload.course_id,
            payload.chapter_id,
            payload.section_id,
        )
    except MaterialError as error:
        raise material_http_error(error) from error

    duplicate = session.scalar(
        select(LearningMaterial.id).where(
            LearningMaterial.course_id == payload.course_id,
            LearningMaterial.source_url == payload.url,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="该链接材料已存在，请使用重新解析")

    is_video = looks_like_video_url(payload.url)
    first_in_scope = is_first_material_in_scope(
        session,
        course_id=payload.course_id,
        chapter_id=payload.chapter_id,
        section_id=payload.section_id,
    )
    material = LearningMaterial(
        course_id=payload.course_id,
        chapter_id=payload.chapter_id,
        section_id=payload.section_id,
        title=payload.title,
        source_type=MaterialSourceType.VIDEO if is_video else MaterialSourceType.URL,
        source_url=payload.url,
        source_hash="",
        content_hash="",
        parser_version=MATERIAL_PARSER_VERSION,
        status=MaterialStatus.FAILED,
        error_text="等待解析",
        is_primary=False,
    )
    session.add(material)
    session.flush()
    try:
        if is_video:
            final_url, page_title, content, chunks = fetch_video_transcript(payload.url)
            extension = "vtt"
        else:
            final_url, page_title, content = fetch_url(payload.url)
            chunks = html_chunks(content)
            extension = "html"
        digest = content_hash(content)
        duplicate_content = session.scalar(
            select(LearningMaterial.id).where(
                LearningMaterial.course_id == payload.course_id,
                LearningMaterial.source_hash == digest,
                LearningMaterial.id != material.id,
            )
        )
        if duplicate_content is not None:
            session.delete(material)
            session.commit()
            raise HTTPException(status_code=409, detail="该材料已经添加到课程")
        if not chunks:
            raise MaterialError("材料没有可提取正文")
        material.source_url = final_url
        material.original_name = page_title
        material.source_hash = digest
        material.content_hash = revision_hash(digest, chunks)
        material.parser_version = MATERIAL_PARSER_VERSION
        material.is_primary = payload.is_primary or first_in_scope
        root = material_root(request)
        directory = storage_directory(root, material.id)
        directory.mkdir(parents=True, exist_ok=True)
        versions = directory / "versions"
        versions.mkdir(exist_ok=True)
        source_path = versions / f"{digest}.{extension}"
        source_path.write_bytes(content)
        material.storage_path = str(source_path.relative_to(root.resolve()))
        save_chunks(session, material, chunks)
        material.last_refresh_status = MaterialRefreshStatus.SUCCEEDED
        material.last_success_at = datetime.now()
    except MaterialError as error:
        material.status = MaterialStatus.FAILED
        material.error_text = str(error)
        material.last_refresh_status = MaterialRefreshStatus.FAILED
        material.last_refresh_error = str(error)
    material.last_refresh_at = datetime.now()
    if material.status == MaterialStatus.READY:
        set_primary(session, material)
    session.commit()
    session.expire_all()
    return material_read(load_material(session, material.id))


@router.patch("/materials/{material_id}", response_model=MaterialRead)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    session: SessionDependency,
) -> MaterialRead:
    material = load_material(session, material_id)
    course_id = payload.course_id if payload.course_id is not None else material.course_id
    chapter_id = (
        payload.chapter_id if "chapter_id" in payload.model_fields_set else material.chapter_id
    )
    section_id = (
        payload.section_id if "section_id" in payload.model_fields_set else material.section_id
    )
    require_course(session, course_id)
    try:
        validate_scope(session, course_id, chapter_id, section_id)
    except MaterialError as error:
        raise material_http_error(error) from error
    material.course_id = course_id
    material.chapter_id = chapter_id
    material.section_id = section_id
    if payload.title is not None:
        material.title = payload.title
    if payload.is_primary is not None:
        material.is_primary = payload.is_primary
    set_primary(session, material)
    session.commit()
    return material_read(load_material(session, material.id))


@router.post("/materials/{material_id}/refresh", response_model=MaterialRefreshRead)
def refresh_material(
    material_id: int,
    request: Request,
    session: SessionDependency,
    current_date: CurrentDateDependency,
) -> MaterialRefreshRead:
    material = load_material(session, material_id)
    previous_revision = material.content_hash
    had_active_revision = material.status == MaterialStatus.READY and any(
        chunk.version_hash == previous_revision for chunk in material.chunks
    )
    refresh_error = ""
    try:
        if material.source_type == MaterialSourceType.PDF:
            root = material_root(request).resolve()
            source_path = (root / material.storage_path).resolve()
            if not source_path.is_relative_to(root) or not source_path.is_file():
                raise MaterialError("原 PDF 文件不存在，请删除后重新添加")
            content = source_path.read_bytes()
            source_digest = content_hash(content)
            chunks = extract_pdf(source_path)
            final_url = material.source_url
            page_title = material.original_name
            new_storage_path = material.storage_path
        elif material.source_type == MaterialSourceType.VIDEO:
            final_url, page_title, content, chunks = fetch_video_transcript(material.source_url)
            extension = "vtt"
            source_digest = content_hash(content)
        else:
            final_url, page_title, content = fetch_url(material.source_url)
            chunks = html_chunks(content)
            extension = "html"
            source_digest = content_hash(content)
        if not chunks:
            raise MaterialError("材料没有可提取正文")
        new_revision = revision_hash(source_digest, chunks)
        if material.source_type != MaterialSourceType.PDF:
            root = material_root(request)
            directory = storage_directory(root, material.id)
            directory.mkdir(parents=True, exist_ok=True)
            versions = directory / "versions"
            versions.mkdir(exist_ok=True)
            source_path = versions / f"{source_digest}.{extension}"
            source_path.write_bytes(content)
            new_storage_path = str(source_path.relative_to(root.resolve()))
        material.source_url = final_url
        material.original_name = page_title
        material.source_hash = source_digest
        material.content_hash = new_revision
        material.parser_version = MATERIAL_PARSER_VERSION
        material.storage_path = new_storage_path
        save_chunks(session, material, chunks)
        material.last_refresh_status = MaterialRefreshStatus.SUCCEEDED
        material.last_refresh_error = ""
        material.last_refresh_at = datetime.now()
        material.last_success_at = datetime.now()
        for selection in material.daily_record_selections:
            if (
                not selection.daily_record.is_completed
                and selection.daily_record.study_date == current_date
            ):
                selection.content_hash = material.content_hash
    except (MaterialError, OSError) as error:
        refresh_error = str(error)
        material.last_refresh_status = MaterialRefreshStatus.FAILED
        material.last_refresh_error = refresh_error
        material.last_refresh_at = datetime.now()
        if had_active_revision:
            material.status = MaterialStatus.READY
            material.error_text = ""
        else:
            material.status = MaterialStatus.FAILED
            material.error_text = refresh_error
    session.commit()
    session.expire_all()
    loaded = load_material(session, material.id)
    return MaterialRefreshRead(
        refresh_status=loaded.last_refresh_status,
        using_previous_revision=bool(refresh_error and had_active_revision),
        error=refresh_error,
        material=material_read(loaded),
    )


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: int,
    request: Request,
    session: SessionDependency,
) -> Response:
    material = load_material(session, material_id)
    session.delete(material)
    session.commit()
    with suppress(OSError):
        remove_storage(material_root(request), material_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/daily-records/{record_id}/materials/{material_id}",
    response_model=DailyRecordRead,
)
def update_daily_record_material(
    record_id: int,
    material_id: int,
    payload: DailyRecordMaterialUpdate,
    session: SessionDependency,
) -> DailyRecordRead:
    record = load_daily_record(session, record_id)
    inherited_ids = {
        material.id
        for material in scoped_materials(
            session,
            course_id=record.section.chapter.course_id,
            chapter_id=record.section.chapter_id,
            section_id=record.section_id,
        )
    }
    if material_id not in inherited_ids:
        raise HTTPException(status_code=422, detail="该材料不适用于当前小节")
    material = load_material(session, material_id)
    selection = session.scalar(
        select(DailyRecordMaterial).where(
            DailyRecordMaterial.daily_record_id == record.id,
            DailyRecordMaterial.material_id == material_id,
        )
    )
    if selection is None:
        selection = DailyRecordMaterial(
            daily_record_id=record.id,
            material_id=material_id,
            content_hash=material.content_hash,
        )
        session.add(selection)
    elif not record.is_completed:
        selection.content_hash = material.content_hash
    selection.enabled = payload.selected
    selection.range_note = payload.range_note.strip()
    session.commit()
    return daily_record_response(session, load_daily_record(session, record.id))


def local_settings_response(request: Request, session: Session) -> LocalSettingsRead:
    vault = get_vault_path(session)
    return LocalSettingsRead(
        obsidian_vault_path=str(vault) if vault is not None else "",
        learner_profile=setting_value(session, "learner_profile"),
        service_version=request.app.version,
        desktop_launch=request.app.state.shutdown_callback is not None,
        semantic_search_enabled=semantic_enabled(session),
        semantic_search_model_ready=model_ready(session),
    )


@router.get("/settings", response_model=LocalSettingsRead)
def get_local_settings(request: Request, session: SessionDependency) -> LocalSettingsRead:
    return local_settings_response(request, session)


def material_search_settings(session: Session) -> MaterialSearchSettingsRead:
    return MaterialSearchSettingsRead(
        semantic_enabled=semantic_enabled(session),
        model_ready=model_ready(session),
        model=EMBEDDING_MODEL,
        model_size=EMBEDDING_MODEL_SIZE,
    )


@router.get("/settings/material-search", response_model=MaterialSearchSettingsRead)
def get_material_search_settings(session: SessionDependency) -> MaterialSearchSettingsRead:
    return material_search_settings(session)


@router.post("/settings/material-search/enable", response_model=MaterialSearchSettingsRead)
async def enable_material_search(session: SessionDependency) -> MaterialSearchSettingsRead:
    search_index_path = index_path(session)
    search_model_cache = model_cache_path(session)
    try:
        await run_in_threadpool(
            prepare_semantic_model_paths,
            search_index_path,
            search_model_cache,
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"语义检索模型准备失败：{error}",
        ) from error
    set_semantic_enabled(session, True)
    return material_search_settings(session)


@router.post("/settings/material-search/disable", response_model=MaterialSearchSettingsRead)
def disable_material_search(session: SessionDependency) -> MaterialSearchSettingsRead:
    set_semantic_enabled(session, False)
    return material_search_settings(session)


@router.put("/settings/learner-profile", response_model=LocalSettingsRead)
def update_learner_profile(
    payload: LearnerProfileUpdate,
    request: Request,
    session: SessionDependency,
) -> LocalSettingsRead:
    save_setting(session, "learner_profile", payload.learner_profile.strip())
    return local_settings_response(request, session)


@router.get("/onboarding", response_model=OnboardingStatusRead)
def get_onboarding_status(request: Request) -> OnboardingStatusRead:
    return OnboardingStatusRead(pending=request.app.state.first_run_marker.is_file())


@router.post("/onboarding/complete", response_model=OnboardingStatusRead)
def complete_onboarding(request: Request) -> OnboardingStatusRead:
    marker: Path = request.app.state.first_run_marker
    marker.unlink(missing_ok=True)
    return OnboardingStatusRead(pending=False)


def vault_candidate_read(candidate: VaultCandidate) -> ObsidianVaultCandidateRead:
    return ObsidianVaultCandidateRead(**candidate.__dict__)


@router.get("/settings/obsidian-vaults", response_model=ObsidianVaultDiscoveryRead)
def get_obsidian_vaults() -> ObsidianVaultDiscoveryRead:
    return ObsidianVaultDiscoveryRead(
        vaults=[vault_candidate_read(candidate) for candidate in discover_obsidian_vaults()],
        browse_supported=vault_browser_supported(),
    )


@router.post("/settings/obsidian/browse", response_model=ObsidianVaultBrowseRead)
def browse_obsidian_vault() -> ObsidianVaultBrowseRead:
    try:
        candidate = browse_for_vault()
    except VaultBrowserUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(error)
        ) from error
    except VaultBrowserError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return ObsidianVaultBrowseRead(
        vault=vault_candidate_read(candidate) if candidate is not None else None
    )


@router.put("/settings/obsidian", response_model=LocalSettingsRead)
def update_obsidian_vault(
    payload: ObsidianVaultUpdate,
    request: Request,
    session: SessionDependency,
) -> LocalSettingsRead:
    try:
        save_vault_path(session, payload.obsidian_vault_path)
    except NotePathError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return local_settings_response(request, session)


@router.get("/notes", response_model=NoteIndexRead)
def list_notes(session: SessionDependency) -> NoteIndexRead:
    if get_vault_path(session) is None:
        raise HTTPException(status_code=409, detail="请先在设置中配置 Obsidian vault 路径")

    sections = session.scalars(
        select(Section)
        .join(Section.chapter)
        .join(Chapter.course)
        .options(
            joinedload(Section.chapter).joinedload(Chapter.course),
        )
        .order_by(Course.id, Chapter.position, Chapter.id, Section.position, Section.id)
    )
    items: list[NoteIndexItem] = []
    issues: list[NoteIndexIssue] = []
    for section in sections:
        try:
            content, relative_path, modified_at_ns = read_section_note(session, section)
        except NotePathError as error:
            issues.append(
                NoteIndexIssue(
                    section_id=section.id,
                    section_title=section.title,
                    detail=str(error),
                )
            )
            continue
        if modified_at_ns is None:
            continue
        items.append(
            NoteIndexItem(
                section_id=section.id,
                course_id=section.chapter.course_id,
                course_name=section.chapter.course.name,
                chapter_id=section.chapter_id,
                chapter_title=section.chapter.title,
                section_title=section.title,
                relative_path=relative_path,
                content=content,
                modified_at_ns=modified_at_ns,
            )
        )
    return NoteIndexRead(items=items, issues=issues)


@router.post("/export/archive")
def export_markdown_archive(
    payload: MarkdownArchiveRequest,
    session: SessionDependency,
) -> Response:
    try:
        content = build_markdown_archive(
            session,
            payload.course_ids,
            payload.content_types,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    filename = f"learning-flow-export-{date.today().isoformat()}.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sections/{section_id}/note", response_model=SectionNoteRead)
def get_section_note(section_id: int, session: SessionDependency) -> SectionNoteRead:
    section = require_section(session, section_id)
    try:
        content, relative_path, modified_at_ns = read_section_note(session, section)
    except NotePathError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SectionNoteRead(
        section_id=section.id,
        file_name=f"{section.title}.md",
        relative_path=relative_path,
        content=content,
        modified_at_ns=modified_at_ns,
    )


@router.post("/markdown/validate", response_model=MarkdownValidationRead)
def validate_markdown(payload: MarkdownValidationRequest) -> MarkdownValidationRead:
    normalized, issues = validate_note_markdown(payload.content)
    return MarkdownValidationRead(
        normalized_content=normalized,
        issues=[issue.__dict__ for issue in issues],
    )


@router.put("/sections/{section_id}/note", response_model=SectionNoteRead)
def save_section_note(
    section_id: int,
    payload: SectionNoteWrite,
    session: SessionDependency,
) -> SectionNoteRead:
    section = require_section(session, section_id)
    try:
        content, relative_path, modified_at_ns = write_section_note(
            session,
            section,
            payload.content,
            payload.expected_modified_at_ns,
            payload.force_overwrite,
        )
    except NoteConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except NotePathError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return SectionNoteRead(
        section_id=section.id,
        file_name=f"{section.title}.md",
        relative_path=relative_path,
        content=content,
        modified_at_ns=modified_at_ns,
    )


@router.post(
    "/daily-records/{record_id}/section-note-prompt",
    response_model=SectionNotePromptRead,
)
def create_section_note_prompt(
    record_id: int,
    session: SessionDependency,
    payload: SectionNoteGenerateRequest | None = None,
) -> SectionNotePrompt:
    payload = payload or SectionNoteGenerateRequest()
    record = load_daily_record(session, record_id)
    context = build_task_context(
        session,
        record,
        AiRunTask.SECTION_NOTE_DRAFT,
        include_material_evidence=False,
    ).text
    full_materials = inline_material_context(session, record)
    if full_materials:
        context = f"{context}\n\n{full_materials}"
    task_prompt = section_note_prompt(
        record,
        load_all_section_records(session, record),
        payload.existing_content,
        payload.mode,
    )
    prompt_text = f"{context}\n\n{task_prompt}"
    prompt = record.section_note_prompt
    if prompt is None:
        prompt = SectionNotePrompt(daily_record=record, prompt_text=prompt_text)
        session.add(prompt)
    else:
        prompt.prompt_text = prompt_text
    session.commit()
    return prompt
