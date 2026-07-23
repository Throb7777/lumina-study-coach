import type { LoaderFunctionArgs } from 'react-router-dom'
import { ApiError, api } from './api'
import type {
  CourseDetail,
  CourseLearningMemory,
  CourseSummary,
  DailyRecord,
  LocalSettings,
  MistakeIndexItem,
  MistakeScopeCourse,
  NoteIndex,
  ObsidianVaultDiscovery,
  SectionNote,
} from './api'

export interface CoursesRouteData {
  courses: CourseSummary[]
  error: string
  onboardingError: string
  onboardingPending: boolean
}

export interface CourseRouteData {
  course: CourseDetail | null
  error: string
  notFound: boolean
}

export interface CourseMemoryRouteData {
  course: CourseDetail | null
  memory: CourseLearningMemory | null
  error: string
  notFound: boolean
}

export interface DailyRecordRouteData {
  record: DailyRecord | null
  error: string
  notFound: boolean
}

export interface SectionNoteRouteData {
  mode: 'workflow' | 'library'
  record: DailyRecord | null
  note: SectionNote | null
  error: string
  notFound: boolean
  vaultMissing: boolean
}

export interface MistakesRouteData {
  mistakes: MistakeIndexItem[]
  courses: MistakeScopeCourse[]
  error: string
}

export interface NotesRouteData {
  notes: NoteIndex
  error: string
  vaultMissing: boolean
}

export interface SettingsRouteData {
  settings: LocalSettings | null
  discovery: ObsidianVaultDiscovery | null
  settingsError: string
  discoveryError: string
}

function routeId(params: LoaderFunctionArgs['params'], key: string) {
  const value = Number(params[key])
  return Number.isInteger(value) && value > 0 ? value : 0
}

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === 'AbortError'
}

function message(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

export async function coursesLoader({ request }: LoaderFunctionArgs): Promise<CoursesRouteData> {
  const [coursesResult, onboardingResult] = await Promise.all([
    api.listCourses(request.signal)
      .then((courses) => ({ courses, error: '' }))
      .catch((error: unknown) => {
        if (isAbortError(error)) throw error
        return { courses: [], error: message(error, '读取课程失败') }
      }),
    api.getOnboardingStatus(request.signal)
      .then((status) => ({ pending: status.pending, error: '' }))
      .catch((error: unknown) => {
        if (isAbortError(error)) throw error
        return { pending: false, error: message(error, '无法读取首次使用状态') }
      }),
  ])
  return {
    courses: coursesResult.courses,
    error: coursesResult.error,
    onboardingError: onboardingResult.error,
    onboardingPending: onboardingResult.pending,
  }
}

export async function courseLoader({ params, request }: LoaderFunctionArgs): Promise<CourseRouteData> {
  try {
    return { course: await api.getCourse(routeId(params, 'courseId'), request.signal), error: '', notFound: false }
  } catch (error) {
    if (isAbortError(error)) throw error
    return {
      course: null,
      error: message(error, '读取课程失败'),
      notFound: error instanceof ApiError && error.status === 404,
    }
  }
}

export async function courseMemoryLoader({
  params,
  request,
}: LoaderFunctionArgs): Promise<CourseMemoryRouteData> {
  const courseId = routeId(params, 'courseId')
  try {
    const [course, memory] = await Promise.all([
      api.getCourse(courseId, request.signal),
      api.getCourseLearningMemory(courseId, request.signal),
    ])
    return { course, memory, error: '', notFound: false }
  } catch (error) {
    if (isAbortError(error)) throw error
    return {
      course: null,
      memory: null,
      error: message(error, '读取学习记忆失败'),
      notFound: error instanceof ApiError && error.status === 404,
    }
  }
}

export async function dailyRecordLoader({ params, request }: LoaderFunctionArgs): Promise<DailyRecordRouteData> {
  try {
    return { record: await api.getDailyRecord(routeId(params, 'recordId'), request.signal), error: '', notFound: false }
  } catch (error) {
    if (isAbortError(error)) throw error
    return {
      record: null,
      error: message(error, '读取学习记录失败'),
      notFound: error instanceof ApiError && error.status === 404,
    }
  }
}

export async function sectionNoteLoader({ params, request }: LoaderFunctionArgs): Promise<SectionNoteRouteData> {
  let record: DailyRecord
  try {
    record = await api.getDailyRecord(routeId(params, 'recordId'), request.signal)
  } catch (error) {
    if (isAbortError(error)) throw error
    return {
      mode: 'workflow',
      record: null,
      note: null,
      error: message(error, '读取学习记录失败'),
      notFound: error instanceof ApiError && error.status === 404,
      vaultMissing: false,
    }
  }

  try {
    return {
      mode: 'workflow',
      record,
      note: await api.getSectionNote(record.section_id, request.signal),
      error: '',
      notFound: false,
      vaultMissing: false,
    }
  } catch (error) {
    if (isAbortError(error)) throw error
    if (error instanceof ApiError && error.status === 409) {
      return { mode: 'workflow', record, note: null, error: error.message, notFound: false, vaultMissing: true }
    }
    return {
      mode: 'workflow',
      record,
      note: null,
      error: message(error, '读取笔记失败'),
      notFound: error instanceof ApiError && error.status === 404,
      vaultMissing: false,
    }
  }
}

export async function libraryNoteLoader({ params, request }: LoaderFunctionArgs): Promise<SectionNoteRouteData> {
  try {
    return {
      mode: 'library',
      record: null,
      note: await api.getSectionNote(routeId(params, 'sectionId'), request.signal),
      error: '',
      notFound: false,
      vaultMissing: false,
    }
  } catch (error) {
    if (isAbortError(error)) throw error
    return {
      mode: 'library',
      record: null,
      note: null,
      error: message(error, '读取笔记失败'),
      notFound: error instanceof ApiError && error.status === 404,
      vaultMissing: error instanceof ApiError && error.status === 409,
    }
  }
}

export async function mistakesLoader({ request }: LoaderFunctionArgs): Promise<MistakesRouteData> {
  try {
    const index = await api.listMistakes(request.signal)
    return { mistakes: index.items, courses: index.courses, error: '' }
  } catch (error) {
    if (isAbortError(error)) throw error
    return { mistakes: [], courses: [], error: message(error, '读取错题失败') }
  }
}

export async function notesLoader({ request }: LoaderFunctionArgs): Promise<NotesRouteData> {
  try {
    return {
      notes: await api.listNotes(request.signal),
      error: '',
      vaultMissing: false,
    }
  } catch (error) {
    if (isAbortError(error)) throw error
    return {
      notes: { items: [], issues: [] },
      error: message(error, '读取笔记失败'),
      vaultMissing: error instanceof ApiError && error.status === 409,
    }
  }
}

export async function settingsLoader({ request }: LoaderFunctionArgs): Promise<SettingsRouteData> {
  const [settingsResult, discoveryResult] = await Promise.all([
    api.getSettings(request.signal)
      .then((settings) => ({ settings, error: '' }))
      .catch((error: unknown) => {
        if (isAbortError(error)) throw error
        return { settings: null, error: message(error, '读取设置失败') }
      }),
    api.discoverObsidianVaults(request.signal)
      .then((discovery) => ({ discovery, error: '' }))
      .catch((error: unknown) => {
        if (isAbortError(error)) throw error
        return { discovery: null, error: message(error, '无法检测 Obsidian Vault') }
      }),
  ])

  return {
    settings: settingsResult.settings,
    discovery: discoveryResult.discovery,
    settingsError: settingsResult.error,
    discoveryError: discoveryResult.error,
  }
}
