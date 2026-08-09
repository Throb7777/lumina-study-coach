export type SectionStatus = 'not_started' | 'in_progress' | 'completed'
export type WorkflowNodeStatus = 'pending' | 'completed' | 'skipped'
export type MistakeStatus = 'unresolved' | 'understood'
export type MistakeType =
  | 'concept'
  | 'formula_condition'
  | 'derivation'
  | 'calculation'
  | 'question_understanding'
  | 'expression'
  | 'cannot_solve'
  | 'other'

export interface Course {
  id: number
  name: string
  description: string
  learning_goal: string
  completed_at: string | null
  completion_summary: string
  completion_summary_version: number
}

export interface CourseSummary extends Course {
  total_sections: number
  completed_sections: number
  in_progress_sections: number
  course_state: 'active' | 'not_started' | 'completed'
  last_study_at: string | null
  created_at: string
}

export interface Section {
  id: number
  chapter_id: number
  title: string
  position: number
  status: SectionStatus
  daily_records: DailyRecordSummary[]
}

export interface Chapter {
  id: number
  course_id: number
  title: string
  position: number
  sections: Section[]
}

export interface CourseDetail extends Course {
  chapters: Chapter[]
}

export interface WorkflowNode {
  id: number
  node_key: string
  title: string
  position: number
  status: WorkflowNodeStatus
}

export interface DailyRecordSummary {
  id: number
  study_date: string
  is_completed: boolean
  recall_last_learned: string
  recall_core_concepts: string
  reconstruct_main_learning: string
}

export type AiInteractionKind = 'recall_review' | 'reconstruction_review'

export interface AiInteraction {
  id: number
  daily_record_id: number
  kind: AiInteractionKind
  prompt_text: string
  feedback_text: string
}

export type GuidedReflectionKind = 'recall' | 'reconstruct'

export interface GuidedQuestion {
  id: string
  question_markdown: string
  focus: string
}

export interface GuidedQuestionReview {
  id: string
  verdict: 'correct' | 'partial' | 'incorrect'
  feedback_markdown: string
}

export interface GuidedReflection {
  id: number
  daily_record_id: number
  kind: GuidedReflectionKind
  questions: GuidedQuestion[]
  answers: Record<string, string>
  reviews: GuidedQuestionReview[]
  feedback_text: string
}

export type AiRunTask =
  | 'recall_questions'
  | 'recall_review'
  | 'reconstruction_questions'
  | 'reconstruction_review'
  | 'practice_generation'
  | 'exercise_grading'
  | 'preview_questions'
  | 'section_note_draft'
  | 'section_note_polish'
  | 'section_memory'
  | 'daily_summary'
  | 'material_context'
  | 'course_completion'

export interface AiRun {
  id: number
  provider: 'codex' | 'gemini'
  task: AiRunTask
  status: 'running' | 'completed' | 'failed'
  course_id: number | null
  section_id: number | null
  daily_record_id: number | null
  exercise_id: number | null
  model: string
  reasoning_effort: string
  error_text: string
  created_at: string
  updated_at: string
}

export interface AiRunResult {
  run: AiRun
  result: AiGeneratedText | null
}

export interface MarkdownValidation {
  normalized_content: string
  issues: Array<{ code: string; message: string; line: number | null }>
}

export interface Exercise {
  id: number
  daily_record_id: number
  generation_prompt: string
  ai_questions: string
  user_answers: string
  grading_prompt: string
  ai_feedback: string
  format_version?: number
  status?: string
  items?: ExerciseItem[]
  mistakes: Mistake[]
}

export type ExerciseItemType =
  | 'single_choice'
  | 'multiple_choice'
  | 'short_answer'
  | 'derivation'
  | 'proof'
  | 'calculation'
  | 'application'
  | 'extension'

export type ExerciseDifficulty = 'basic' | 'intermediate' | 'challenge'

export interface ExerciseOption {
  id: string
  label: string
}

export interface ExerciseResponse {
  id: number
  exercise_item_id: number
  answer_markdown: string
  selected_options: string[]
  status: 'unanswered' | 'draft' | 'submitted' | 'graded'
  verdict: string
  feedback_markdown: string
  score: number | null
  attachments: ExerciseResponseAttachment[]
}

export interface ExerciseResponseAttachment {
  id: number
  original_name: string
  media_type: string
  size_bytes: number
  processing_status: string
}

export interface ExerciseItem {
  id: number
  exercise_id: number
  position: number
  item_type: ExerciseItemType
  difficulty: ExerciseDifficulty
  stem_markdown: string
  options: ExerciseOption[]
  reference_answer_markdown: string
  source_refs: string[]
  response: ExerciseResponse | null
}

export interface Mistake {
  id: number
  exercise_id: number
  exercise_item_id: number | null
  original_question: string
  user_answer: string
  error_content: string
  error_type: MistakeType
  correct_approach: string
  cause_analysis: string
  status: MistakeStatus
}

export interface MistakePayload {
  exercise_item_id?: number | null
  error_content: string
  error_type: MistakeType
}

export interface MistakeIndexItem extends Mistake {
  daily_record_id: number
  study_date: string
  course_id: number
  course_name: string
  chapter_id: number
  chapter_title: string
  section_id: number
  section_title: string
}

export interface MistakeScopeSection {
  id: number
  title: string
}

export interface MistakeScopeChapter {
  id: number
  title: string
  sections: MistakeScopeSection[]
}

export interface MistakeScopeCourse {
  id: number
  name: string
  chapters: MistakeScopeChapter[]
}

export interface MistakeIndex {
  items: MistakeIndexItem[]
  courses: MistakeScopeCourse[]
}

export type ExportContentType =
  | 'outline'
  | 'daily_records'
  | 'ai_reviews'
  | 'exercises'
  | 'mistakes'
  | 'notes'

export interface ExportArchivePayload {
  course_ids: number[]
  content_types: ExportContentType[]
}

export interface DownloadFile {
  blob: Blob
  filename: string
}

export interface PreviewQuestionSet {
  id: number
  daily_record_id: number
  prompt_text: string
  question_1: string
  question_2: string
  question_3: string
}

export interface PreviousPreviewQuestions {
  daily_record_id: number
  section_id: number
  section_title: string
  study_date: string
  questions: string[]
}

export interface SectionNotePrompt {
  id: number
  daily_record_id: number
  prompt_text: string
}

export interface LocalSettings {
  obsidian_vault_path: string
  learner_profile: string
  service_version: string
  desktop_launch: boolean
  semantic_search_enabled: boolean
  semantic_search_model_ready: boolean
}

export interface OnboardingStatus {
  pending: boolean
}

export interface MaterialSearchSettings {
  semantic_enabled: boolean
  model_ready: boolean
  model: string
  model_size: string
}

export interface CourseCompletion {
  course_id: number
  completed_at: string
  completion_summary: string
  completion_summary_version: number
}

export type MaterialSourceType = 'pdf' | 'url' | 'video'
export type MaterialStatus = 'ready' | 'failed'

export interface LearningMaterial {
  id: number
  course_id: number
  course_name: string
  chapter_id: number | null
  chapter_title: string
  section_id: number | null
  section_title: string
  title: string
  source_type: MaterialSourceType
  source_url: string
  original_name: string
  status: MaterialStatus
  error_text: string
  warning_text?: string
  total_pages?: number
  ocr_pages?: number
  failed_pages?: number
  last_refresh_status?: 'idle' | 'running' | 'succeeded' | 'failed'
  last_refresh_error?: string
  last_refresh_at?: string | null
  last_success_at?: string | null
  is_primary: boolean
  chunk_count: number
}

export interface MaterialRefreshResult {
  refresh_status: NonNullable<LearningMaterial['last_refresh_status']>
  using_previous_revision: boolean
  error: string
  material: LearningMaterial
}

export interface DailyRecordMaterial extends LearningMaterial {
  selected: boolean
  range_note: string
}

export interface MaterialScopePayload {
  course_id: number
  chapter_id: number | null
  section_id: number | null
  is_primary: boolean
}

export interface UrlMaterialPayload extends MaterialScopePayload {
  title: string
  url: string
}

export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
}

export type AiProvider = 'codex' | 'gemini'
export type AiProviderState = 'not_installed' | 'launch_blocked' | 'disconnected' | 'connected' | 'model_unavailable' | 'error'

export interface AiProviderStatus {
  provider: AiProvider
  installed: boolean
  connected: boolean
  detail: string
  account: string
  plan: string
  version: string
  state: AiProviderState
  preferred_model: string
  model_available: boolean | null
  reasoning_effort: string
  active_model: string
  executable?: string
  service_mode?: string
}

export interface AiModelOption {
  model: string
  display_name: string
  reasoning_efforts: string[]
  default_reasoning_effort: string
}

export interface AiProviderOptions {
  provider: AiProvider
  selected_model: string
  selected_reasoning_effort: string
  default_model: string
  default_reasoning_effort: string
  models: AiModelOption[]
  error: string
}

export interface AiProviderSnapshot {
  providers: AiProviderStatus[]
  options: AiProviderOptions[]
}

export interface AiProviderLogin {
  auth_url: string
  login_id: string
}

export interface GeminiProviderLogin {
  login_id: string
}

export interface AiProviderLoginStatus {
  status: 'pending' | 'succeeded' | 'failed' | 'not_found'
  error: string
  detail: string
}

export interface AiGeneratedText {
  text: string
  provider: AiProvider
  model: string
  context_snapshot: string
  source_refs: AiSourceReference[]
  material_revision: number
  material_manifest_hash: string
}

export interface AiSourceReference {
  task: string
  material_id: number
  material_title: string
  source_type: MaterialSourceType
  location: string
  content_hash: string
  chunk_position?: number | null
}

export interface CourseMemory {
  id: number
  course_id: number
  overview: string
  generated_outline: string
  core_concepts: string
  key_methods: string
  unresolved_questions: string
  error_patterns: string
  version: number
}

export interface SectionMemory {
  id: number
  section_id: number
  summary: string
  core_concepts: string
  key_methods: string
  unresolved_questions: string
  error_patterns: string
  version: number
}

export interface ChapterMemory {
  id: number
  chapter_id: number
  summary: string
  core_concepts: string
  key_methods: string
  unresolved_questions: string
  error_patterns: string
  version: number
}

export interface CourseLearningMemory {
  course: CourseMemory
  chapters: ChapterMemory[]
  sections: SectionMemory[]
}

export type CourseMemoryPayload = Pick<
  CourseMemory,
  | 'overview'
  | 'core_concepts'
  | 'key_methods'
  | 'unresolved_questions'
  | 'error_patterns'
>

export interface ObsidianVaultCandidate {
  name: string
  path: string
  has_obsidian_directory: boolean
  writable: boolean
}

export interface BackupPreview {
  token: string
  created_at: string
  format_version: number
  file_count: number
  total_size_bytes: number
  includes_materials: boolean
  includes_attachments: boolean
  includes_notes: boolean
  requires_obsidian_vault: boolean
}

export interface BackupRestoreStatus {
  token: string
  status: 'pending' | 'restarting' | 'completed' | 'failed'
  detail: string
}

export interface ObsidianVaultDiscovery {
  vaults: ObsidianVaultCandidate[]
  browse_supported: boolean
}

export interface SectionNote {
  section_id: number
  file_name: string
  relative_path: string
  content: string
  modified_at_ns: number | null
}

export interface NoteIndexItem {
  section_id: number
  course_id: number
  course_name: string
  chapter_id: number
  chapter_title: string
  section_title: string
  relative_path: string
  content: string
  modified_at_ns: number
}

export interface NoteIndexIssue {
  section_id: number
  course_id: number
  course_name: string
  chapter_id: number
  chapter_title: string
  section_title: string
  detail: string
}

export interface NoteIndex {
  items: NoteIndexItem[]
  issues: NoteIndexIssue[]
}

export interface DailyRecord {
  id: number
  section_id: number
  section_title: string
  chapter_id: number
  course_id: number
  study_date: string
  is_completed: boolean
  recall_last_learned: string
  recall_core_concepts: string
  recall_clear_parts: string
  recall_blocked_parts: string
  study_material_scope: string
  reconstruct_problem: string
  reconstruct_main_learning: string
  reconstruct_math: string
  context_summary: string
  active_ai_runs?: AiRun[]
  ai_source_refs: AiSourceReference[]
  workflow_nodes: WorkflowNode[]
  previous_records: DailyRecordSummary[]
  ai_interactions: AiInteraction[]
  guided_reflections: GuidedReflection[]
  exercises: Exercise[]
  preview_question_set: PreviewQuestionSet | null
  previous_preview_questions: PreviousPreviewQuestions | null
  section_note_prompt: SectionNotePrompt | null
  materials: DailyRecordMaterial[]
}

export type DailyRecordContent = Pick<
  DailyRecord,
  | 'recall_last_learned'
  | 'recall_core_concepts'
  | 'recall_clear_parts'
  | 'recall_blocked_parts'
  | 'study_material_scope'
  | 'reconstruct_problem'
  | 'reconstruct_main_learning'
  | 'reconstruct_math'
>

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const AI_PROVIDER_SNAPSHOT_TIMEOUT_MS = 15_000

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? '请求失败')
  }

  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

async function withRequestTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  signal: AbortSignal | undefined,
  timeoutMs: number,
  timeoutMessage: string,
): Promise<T> {
  const controller = new AbortController()
  let timedOut = false
  const abortFromCaller = () => controller.abort(signal?.reason)
  if (signal?.aborted) {
    abortFromCaller()
  } else {
    signal?.addEventListener('abort', abortFromCaller, { once: true })
  }
  const timer = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  try {
    return await operation(controller.signal)
  } catch (error) {
    if (timedOut) {
      throw new Error(timeoutMessage, { cause: error })
    }
    throw error
  } finally {
    globalThis.clearTimeout(timer)
    signal?.removeEventListener('abort', abortFromCaller)
  }
}

async function requestDownload(path: string, options: RequestInit): Promise<DownloadFile> {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? '导出失败')
  }
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] ?? 'learning-flow-export.zip'
  return { blob: await response.blob(), filename }
}

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(path, { method: 'POST', body: form })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? '上传失败')
  }
  return response.json() as Promise<T>
}

async function getAiProviderSnapshot(signal?: AbortSignal): Promise<AiProviderSnapshot> {
  return withRequestTimeout(async (requestSignal) => {
    try {
      return await request<AiProviderSnapshot>(
        '/api/ai/provider-snapshot',
        { signal: requestSignal },
      )
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) {
        throw error
      }
      const [providers, options] = await Promise.all([
        request<AiProviderStatus[]>('/api/ai/providers', { signal: requestSignal }),
        request<AiProviderOptions[]>('/api/ai/provider-options', { signal: requestSignal }),
      ])
      return { providers, options }
    }
  }, signal, AI_PROVIDER_SNAPSHOT_TIMEOUT_MS, '读取模型连接状态超时，请重试')
}

export const api = {
  getHealth: (signal?: AbortSignal) => request<HealthResponse>('/api/health', { signal }),
  getAiProviders: (signal?: AbortSignal) =>
    request<AiProviderStatus[]>('/api/ai/providers', { signal }),
  getAiProviderOptions: (signal?: AbortSignal) =>
    request<AiProviderOptions[]>('/api/ai/provider-options', { signal }),
  getAiProviderSnapshot,
  updateAiProviderPreference: (
    provider: AiProvider,
    payload: { model: string; reasoning_effort: string },
  ) => request<AiProviderOptions>(`/api/settings/ai-providers/${provider}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),
  startCodexLogin: () =>
    request<AiProviderLogin>('/api/ai/providers/codex/login', { method: 'POST' }),
  getCodexLoginStatus: (loginId: string, signal?: AbortSignal) =>
    request<AiProviderLoginStatus>(`/api/ai/providers/codex/login/${encodeURIComponent(loginId)}`, { signal }),
  logoutCodex: () =>
    request<void>('/api/ai/providers/codex/logout', { method: 'POST' }),
  startGeminiLogin: () =>
    request<GeminiProviderLogin>('/api/ai/providers/gemini/login', { method: 'POST' }),
  getGeminiLoginStatus: (loginId: string, signal?: AbortSignal) =>
    request<AiProviderLoginStatus>(`/api/ai/providers/gemini/login/${encodeURIComponent(loginId)}`, { signal }),
  cancelGeminiLogin: (loginId: string) =>
    request<void>(`/api/ai/providers/gemini/login/${encodeURIComponent(loginId)}/cancel`, { method: 'POST' }),
  enableGemini: () =>
    request<void>('/api/ai/providers/gemini/enable', { method: 'POST' }),
  disconnectGemini: () =>
    request<void>('/api/ai/providers/gemini/disconnect', { method: 'POST' }),
  listCourses: (signal?: AbortSignal) => request<CourseSummary[]>('/api/courses', { signal }),
  createCourse: (payload: Pick<Course, 'name' | 'description' | 'learning_goal'>) =>
    request<Course>('/api/courses', { method: 'POST', body: JSON.stringify(payload) }),
  getCourse: (courseId: number, signal?: AbortSignal) =>
    request<CourseDetail>(`/api/courses/${courseId}`, { signal }),
  updateCourse: (
    courseId: number,
    payload: Partial<Pick<Course, 'name' | 'description' | 'learning_goal'>>,
  ) =>
    request<Course>(`/api/courses/${courseId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteCourse: (courseId: number) =>
    request<void>(`/api/courses/${courseId}`, { method: 'DELETE' }),
  completeCourse: (courseId: number) =>
    request<CourseCompletion>(`/api/courses/${courseId}/complete`, { method: 'POST' }),
  createChapter: (courseId: number, title: string) =>
    request<Chapter>(`/api/courses/${courseId}/chapters`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  updateChapter: (chapterId: number, title: string) =>
    request<Chapter>(`/api/chapters/${chapterId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
  deleteChapter: (chapterId: number) =>
    request<void>(`/api/chapters/${chapterId}`, { method: 'DELETE' }),
  createSection: (chapterId: number, title: string) =>
    request<Section>(`/api/chapters/${chapterId}/sections`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  updateSection: (sectionId: number, payload: Partial<Pick<Section, 'title' | 'status'>>) =>
    request<Section>(`/api/sections/${sectionId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteSection: (sectionId: number) =>
    request<void>(`/api/sections/${sectionId}`, { method: 'DELETE' }),
  openTodayRecord: (sectionId: number, continueCompleted = false) =>
    request<DailyRecord>(
      `/api/sections/${sectionId}/daily-records/today${continueCompleted ? '?continue_completed=true' : ''}`,
      { method: 'POST' },
    ),
  getDailyRecord: (recordId: number, signal?: AbortSignal) =>
    request<DailyRecord>(`/api/daily-records/${recordId}`, { signal }),
  listAiRuns: (
    scope: { daily_record_id?: number; section_id?: number },
    activeOnly = false,
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams()
    if (scope.daily_record_id) params.set('daily_record_id', String(scope.daily_record_id))
    if (scope.section_id) params.set('section_id', String(scope.section_id))
    if (activeOnly) params.set('active_only', 'true')
    return request<AiRun[]>(`/api/ai-runs?${params}`, { signal })
  },
  cancelAiRun: (runId: number) =>
    request<void>(`/api/ai-runs/${runId}/cancel`, { method: 'POST' }),
  updateDailyRecord: (recordId: number, payload: Partial<DailyRecordContent>) =>
    request<DailyRecord>(`/api/daily-records/${recordId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listMaterials: (courseId?: number, signal?: AbortSignal) =>
    request<LearningMaterial[]>(
      `/api/materials${courseId ? `?course_id=${courseId}` : ''}`,
      { signal },
    ),
  createPdfMaterial: (
    title: string,
    file: File,
    scope: MaterialScopePayload,
  ) => {
    const form = new FormData()
    form.set('title', title)
    form.set('file', file)
    form.set('course_id', String(scope.course_id))
    if (scope.chapter_id !== null) form.set('chapter_id', String(scope.chapter_id))
    if (scope.section_id !== null) form.set('section_id', String(scope.section_id))
    form.set('is_primary', String(scope.is_primary))
    return requestForm<LearningMaterial>('/api/materials/pdf', form)
  },
  createUrlMaterial: (payload: UrlMaterialPayload) =>
    request<LearningMaterial>('/api/materials/url', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateMaterial: (
    materialId: number,
    payload: Partial<Pick<LearningMaterial, 'title' | 'course_id' | 'chapter_id' | 'section_id' | 'is_primary'>>,
  ) => request<LearningMaterial>(`/api/materials/${materialId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }),
  refreshMaterial: (materialId: number) =>
    request<MaterialRefreshResult>(`/api/materials/${materialId}/refresh`, { method: 'POST' }),
  deleteMaterial: (materialId: number) =>
    request<void>(`/api/materials/${materialId}`, { method: 'DELETE' }),
  updateDailyRecordMaterial: (
    recordId: number,
    materialId: number,
    selected: boolean,
    rangeNote: string,
  ) => request<DailyRecord>(`/api/daily-records/${recordId}/materials/${materialId}`, {
    method: 'PUT',
    body: JSON.stringify({ selected, range_note: rangeNote }),
  }),
  updateWorkflowNode: (
    nodeId: number,
    status: WorkflowNodeStatus,
    confirmSkip = false,
  ) => request<WorkflowNode>(
    `/api/workflow-nodes/${nodeId}${confirmSkip ? '?confirm_skip=true' : ''}`,
    { method: 'PATCH', body: JSON.stringify({ status }) },
  ),
  completeDailyRecord: (recordId: number) =>
    request<DailyRecord>(`/api/daily-records/${recordId}/complete`, { method: 'POST' }),
  generateAiReview: (recordId: number, kind: AiInteractionKind) =>
    request<AiInteraction>(`/api/daily-records/${recordId}/ai-review/${kind}`, {
      method: 'POST',
    }),
  generateGuidedReflectionQuestions: (recordId: number, kind: GuidedReflectionKind) =>
    request<GuidedReflection>(
      `/api/daily-records/${recordId}/guided-reflections/${kind}/questions`,
      { method: 'POST' },
    ),
  updateGuidedReflectionAnswers: (reflectionId: number, answers: Record<string, string>) =>
    request<GuidedReflection>(`/api/guided-reflections/${reflectionId}/answers`, {
      method: 'PUT',
      body: JSON.stringify({ answers }),
    }),
  reviewGuidedReflection: (reflectionId: number) =>
    request<GuidedReflection>(`/api/guided-reflections/${reflectionId}/review`, {
      method: 'POST',
    }),
  createAiInteraction: (recordId: number, kind: AiInteractionKind) =>
    request<AiInteraction>(`/api/daily-records/${recordId}/ai-prompts/${kind}`, {
      method: 'POST',
    }),
  updateAiInteraction: (interactionId: number, feedback_text: string) =>
    request<AiInteraction>(`/api/ai-interactions/${interactionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ feedback_text }),
    }),
  createExercise: (recordId: number) =>
    request<Exercise>(`/api/daily-records/${recordId}/exercises`, { method: 'POST' }),
  generateAiPractice: (recordId: number) =>
    request<Exercise>(`/api/daily-records/${recordId}/ai-practice`, { method: 'POST' }),
  updateExercise: (exerciseId: number, payload: Partial<Pick<Exercise, 'ai_questions' | 'user_answers' | 'ai_feedback'>>) =>
    request<Exercise>(`/api/exercises/${exerciseId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteExercise: (exerciseId: number) =>
    request<void>(`/api/exercises/${exerciseId}`, { method: 'DELETE' }),
  updateExerciseResponse: (
    itemId: number,
    payload: { answer_markdown: string; selected_options: string[] },
  ) => request<Exercise>(`/api/exercise-items/${itemId}/response`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),
  uploadExerciseResponseAttachment: (itemId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return requestForm<Exercise>(`/api/exercise-items/${itemId}/attachments`, form)
  },
  deleteExerciseResponseAttachment: (attachmentId: number) =>
    request<Exercise>(`/api/exercise-response-attachments/${attachmentId}`, {
      method: 'DELETE',
    }),
  completeExercise: (exerciseId: number) =>
    request<Exercise>(`/api/exercises/${exerciseId}/complete`, { method: 'POST' }),
  createGradingPrompt: (exerciseId: number) =>
    request<Exercise>(`/api/exercises/${exerciseId}/grading-prompt`, { method: 'POST' }),
  generateAiGrading: (exerciseId: number) =>
    request<Exercise>(`/api/exercises/${exerciseId}/ai-grade`, { method: 'POST' }),
  createMistake: (exerciseId: number, payload: MistakePayload) =>
    request<Mistake>(`/api/exercises/${exerciseId}/mistakes`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateMistake: (mistakeId: number, payload: Partial<Omit<Mistake, 'id' | 'exercise_id'>>) =>
    request<Mistake>(`/api/mistakes/${mistakeId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteMistake: (mistakeId: number) =>
    request<void>(`/api/mistakes/${mistakeId}`, { method: 'DELETE' }),
  listMistakes: (signal?: AbortSignal) =>
    request<MistakeIndex>('/api/mistakes', { signal }),
  createPreviewQuestionsPrompt: (recordId: number) =>
    request<PreviewQuestionSet>(`/api/daily-records/${recordId}/preview-questions/prompt`, {
      method: 'POST',
    }),
  generateAiPreviewQuestions: (recordId: number) =>
    request<PreviewQuestionSet>(`/api/daily-records/${recordId}/ai-preview-questions`, {
      method: 'POST',
    }),
  getSettings: (signal?: AbortSignal) => request<LocalSettings>('/api/settings', { signal }),
  getMaterialSearchSettings: (signal?: AbortSignal) =>
    request<MaterialSearchSettings>('/api/settings/material-search', { signal }),
  enableMaterialSearch: () =>
    request<MaterialSearchSettings>('/api/settings/material-search/enable', { method: 'POST' }),
  disableMaterialSearch: () =>
    request<MaterialSearchSettings>('/api/settings/material-search/disable', { method: 'POST' }),
  getOnboardingStatus: (signal?: AbortSignal) =>
    request<OnboardingStatus>('/api/onboarding', { signal }),
  completeOnboarding: () =>
    request<OnboardingStatus>('/api/onboarding/complete', { method: 'POST' }),
  shutdownLocalService: () =>
    request<{ status: 'stopping' }>('/api/system/shutdown', {
      method: 'POST',
      body: JSON.stringify({ confirm: true }),
    }),
  updateLearnerProfile: (learner_profile: string) =>
    request<LocalSettings>('/api/settings/learner-profile', {
      method: 'PUT',
      body: JSON.stringify({ learner_profile }),
    }),
  discoverObsidianVaults: (signal?: AbortSignal) =>
    request<ObsidianVaultDiscovery>('/api/settings/obsidian-vaults', { signal }),
  browseObsidianVault: () =>
    request<{ vault: ObsidianVaultCandidate | null }>('/api/settings/obsidian/browse', {
      method: 'POST',
    }),
  updateObsidianVault: (obsidian_vault_path: string) =>
    request<LocalSettings>('/api/settings/obsidian', {
      method: 'PUT',
      body: JSON.stringify({ obsidian_vault_path }),
    }),
  createFullBackup: () => requestDownload('/api/backup/archive', { method: 'GET' }),
  inspectBackup: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return requestForm<BackupPreview>('/api/backup/inspect', form)
  },
  discardStagedBackup: (token: string) =>
    request<void>(`/api/backup/staged/${encodeURIComponent(token)}`, {
      method: 'DELETE',
    }),
  restoreBackup: (token: string, obsidian_vault_path: string) =>
    request<BackupRestoreStatus>('/api/backup/restore', {
      method: 'POST',
      body: JSON.stringify({ token, obsidian_vault_path, confirm: true }),
    }),
  getBackupRestoreStatus: (token: string, signal?: AbortSignal) =>
    request<BackupRestoreStatus>(
      `/api/backup/restore-status?token=${encodeURIComponent(token)}`,
      { signal },
    ),
  getSectionNote: (sectionId: number, signal?: AbortSignal) =>
    request<SectionNote>(`/api/sections/${sectionId}/note`, { signal }),
  listNotes: (signal?: AbortSignal) => request<NoteIndex>('/api/notes', { signal }),
  saveSectionNote: (
    sectionId: number,
    content: string,
    expected_modified_at_ns: number | null,
    force_overwrite = false,
  ) => request<SectionNote>(`/api/sections/${sectionId}/note`, {
    method: 'PUT',
    body: JSON.stringify({ content, expected_modified_at_ns, force_overwrite }),
  }),
  validateMarkdown: (content: string) =>
    request<MarkdownValidation>('/api/markdown/validate', {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
  createSectionNotePrompt: (recordId: number, existingContent = '', mode: 'create' | 'revise' = 'create') =>
    request<SectionNotePrompt>(`/api/daily-records/${recordId}/section-note-prompt`, {
      method: 'POST',
      body: JSON.stringify({ existing_content: existingContent, mode }),
    }),
  generateAiSectionNote: (recordId: number, existingContent = '', mode: 'create' | 'revise' = 'create') =>
    request<AiGeneratedText>(`/api/daily-records/${recordId}/ai-section-note`, {
      method: 'POST',
      body: JSON.stringify({ existing_content: existingContent, mode }),
    }),
  startAiSectionNote: (recordId: number, existingContent = '', mode: 'create' | 'revise' = 'create') =>
    request<AiRun>(`/api/daily-records/${recordId}/ai-section-note-runs`, {
      method: 'POST',
      body: JSON.stringify({ existing_content: existingContent, mode }),
    }),
  getAiRunResult: (runId: number, signal?: AbortSignal) =>
    request<AiRunResult>(`/api/ai-runs/${runId}/result`, { signal }),
  polishSectionNote: (sectionId: number, content: string, context = '') =>
    request<AiGeneratedText>(`/api/sections/${sectionId}/ai-polish-note`, {
      method: 'POST',
      body: JSON.stringify({ content, context }),
    }),
  getCourseLearningMemory: (courseId: number, signal?: AbortSignal) =>
    request<CourseLearningMemory>(`/api/courses/${courseId}/learning-memory`, { signal }),
  updateCourseLearningMemory: (courseId: number, payload: CourseMemoryPayload) =>
    request<CourseMemory>(`/api/courses/${courseId}/learning-memory`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  refreshSectionLearningMemory: (sectionId: number) =>
    request<SectionMemory>(`/api/sections/${sectionId}/learning-memory/refresh`, {
      method: 'POST',
    }),
  exportMarkdownArchive: (payload: ExportArchivePayload) =>
    requestDownload('/api/export/archive', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
