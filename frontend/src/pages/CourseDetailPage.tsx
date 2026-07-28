import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  CalendarDays,
  Brain,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Library,
  Pencil,
  Play,
  Plus,
  Trash2,
} from 'lucide-react'
import { Link, useLoaderData, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api'
import type {
  Chapter,
  CourseDetail,
  LearningMaterial,
  Section,
  SectionStatus,
} from '../api'
import { AppDialog } from '../components/AppDialog'
import { ConfirmDialog } from '../components/ConfirmDialog'
import type { ConfirmDialogVariant } from '../components/ConfirmDialog'
import { TwoStepDeleteDialog } from '../components/TwoStepDeleteDialog'
import { DraftStatus } from '../components/DraftStatus'
import { MaterialLibrary } from '../components/MaterialLibrary'
import type { MaterialScopeOption } from '../components/MaterialLibrary'
import { MarkdownContent } from '../components/MarkdownContent'
import { PageBackBar } from '../components/PageBackBar'
import { TextEditDialog } from '../components/TextEditDialog'
import { UnsavedChangesGuard } from '../components/UnsavedChangesGuard'
import {
  clearDraft,
  clearFormDraft,
  readDraft,
  restoreFormDraft,
  writeDraft,
  writeFormDraft,
} from '../draftStorage'
import { formIsDirty, updateFormBaseline } from '../formState'
import type { CourseRouteData } from '../routeData'

const statusLabels: Record<SectionStatus, string> = {
  not_started: '未完成',
  in_progress: '进行中',
  completed: '已完成',
}

const HISTORY_PREVIEW_COUNT = 3

function localDateKey() {
  const today = new Date()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${today.getFullYear()}-${month}-${day}`
}

function formatStudyDate(value: string, today: string) {
  const [year, month, day] = value.split('-').map(Number)
  const currentYear = Number(today.slice(0, 4))
  if (!year || !month || !day) return value
  return year === currentYear ? `${month}月${day}日` : `${year}年${month}月${day}日`
}

function historyStorageKey(courseId: number) {
  return `learning-flow-coach.course-${courseId}.expanded-history`
}

function readExpandedHistory(courseId?: number) {
  if (!courseId) return null
  const value = Number(sessionStorage.getItem(historyStorageKey(courseId)))
  return Number.isInteger(value) && value > 0 ? value : null
}

type EditTarget =
  | { kind: 'course' }
  | { kind: 'chapter'; chapter: Chapter }
  | { kind: 'section'; section: Section }

type ConfirmAction =
  | { kind: 'delete-course' }
  | { kind: 'delete-chapter'; chapter: Chapter }
  | { kind: 'delete-section'; section: Section }
  | { kind: 'continue-section'; section: Section }

interface ConfirmDialogConfig {
  confirmLabel: string
  description: string
  title: string
  variant: ConfirmDialogVariant
  finalDescription?: string
  targetKey?: string
}

interface CourseEditDraft {
  description: string
  learning_goal: string
  name: string
}

function getConfirmDialogConfig(action: ConfirmAction, courseName: string): ConfirmDialogConfig {
  switch (action.kind) {
    case 'delete-course':
      return {
        title: '删除课程？',
        description: `删除“${courseName}”后，其中的章节、小节和全部学习记录都会一并删除，且无法恢复。`,
        confirmLabel: '删除课程',
        variant: 'danger',
        finalDescription: `即将永久删除“${courseName}”及其全部学习内容，删除后无法恢复。`,
        targetKey: `course-${courseName}`,
      }
    case 'delete-chapter':
      return {
        title: '删除章节？',
        description: `删除“${action.chapter.title}”后，其中的所有小节和学习记录都会一并删除，且无法恢复。`,
        confirmLabel: '删除章节',
        variant: 'danger',
        finalDescription: `即将永久删除“${action.chapter.title}”及其全部小节和学习记录，删除后无法恢复。`,
        targetKey: `chapter-${action.chapter.id}`,
      }
    case 'delete-section':
      return {
        title: '删除小节？',
        description: `删除“${action.section.title}”后，该小节的全部学习记录都会一并删除，且无法恢复。`,
        confirmLabel: '删除小节',
        variant: 'danger',
        finalDescription: `即将永久删除“${action.section.title}”及其全部学习记录，删除后无法恢复。`,
        targetKey: `section-${action.section.id}`,
      }
    case 'continue-section':
      return {
        title: '继续学习这个小节？',
        description: `“${action.section.title}”已经完成。确认后仍会创建或打开今天的学习记录。`,
        confirmLabel: '继续学习',
        variant: 'default',
      }
  }
}

export function CourseDetailPage() {
  const routeData = useLoaderData() as CourseRouteData
  const navigate = useNavigate()
  const [course, setCourse] = useState<CourseDetail | null>(routeData.course)
  const [error, setError] = useState(routeData.error)
  const [openingSectionId, setOpeningSectionId] = useState<number | null>(null)
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null)
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null)
  const [dialogBusy, setDialogBusy] = useState(false)
  const [dialogError, setDialogError] = useState('')
  const [dialogTrigger, setDialogTrigger] = useState<HTMLElement | null>(null)
  const [dirtyDraftKeys, setDirtyDraftKeys] = useState<Set<string>>(new Set())
  const [courseDraftRecovered, setCourseDraftRecovered] = useState(false)
  const [courseEditDraft, setCourseEditDraft] = useState<CourseEditDraft | null>(null)
  const [courseEditRecovered, setCourseEditRecovered] = useState(false)
  const [chapterCreateOpen, setChapterCreateOpen] = useState(false)
  const [openSectionCreateIds, setOpenSectionCreateIds] = useState<Set<number>>(new Set())
  const [titleEditDirty, setTitleEditDirty] = useState(false)
  const [titleEditValue, setTitleEditValue] = useState('')
  const [materials, setMaterials] = useState<LearningMaterial[]>([])
  const [materialsLoading, setMaterialsLoading] = useState(false)
  const [materialsOpen, setMaterialsOpen] = useState(false)
  const [materialScope, setMaterialScope] = useState<MaterialScopeOption | null>(null)
  const [courseCompletionBusy, setCourseCompletionBusy] = useState(false)
  const [expandedHistorySectionId, setExpandedHistorySectionId] = useState<number | null>(
    () => readExpandedHistory(routeData.course?.id),
  )
  const [showAllHistory, setShowAllHistory] = useState(false)
  const pageRef = useRef<HTMLElement>(null)
  const materialsPanelRef = useRef<HTMLElement>(null)
  const outlineDraftSignature = course
    ? `${course.id}:${(course.chapters ?? []).map((chapter) => chapter.id).join(',')}`
    : ''

  async function toggleMaterials(scope: MaterialScopeOption) {
    if (materialsOpen && materialScope?.value === scope.value) {
      setMaterialsOpen(false)
      return
    }
    if (!course) return
    setMaterialsLoading(true)
    setError('')
    try {
      const result = await api.listMaterials(course.id)
      setMaterials(Array.isArray(result) ? result : [])
      setMaterialScope(scope)
      setMaterialsOpen(true)
      window.setTimeout(() => {
        materialsPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 0)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '读取课程材料失败')
    } finally {
      setMaterialsLoading(false)
    }
  }

  function formDraftKey(key: string) {
    return `course-${course?.id ?? 'unknown'}-${key}`
  }

  function editDraftKey(target: EditTarget) {
    if (target.kind === 'course') return `course-${course?.id ?? 'unknown'}-edit`
    if (target.kind === 'chapter') return `chapter-${target.chapter.id}-title`
    return `section-${target.section.id}-title`
  }

  function courseEditBaseline(): CourseEditDraft | null {
    return course && {
      description: course.description,
      learning_goal: course.learning_goal,
      name: course.name,
    }
  }

  const courseEditDirty = editTarget?.kind === 'course'
    && courseEditDraft !== null
    && JSON.stringify(courseEditDraft) !== JSON.stringify(courseEditBaseline())
  const hasEditDraft = Boolean(courseEditDirty || titleEditDirty)

  useEffect(() => {
    if (!course || !pageRef.current) return
    const restoredKeys: string[] = []
    pageRef.current.querySelectorAll<HTMLFormElement>('form[data-dirty-key]').forEach((form) => {
      const key = form.dataset.dirtyKey
      if (key && restoreFormDraft(formDraftKey(key), form) && formIsDirty(form)) restoredKeys.push(key)
    })
    if (restoredKeys.length === 0) return
    const restoredSectionIds = restoredKeys
      .filter((key) => key.startsWith('section-create-'))
      .map((key) => Number(key.replace('section-create-', '')))
      .filter(Number.isFinite)
    const timer = window.setTimeout(() => {
      if (restoredKeys.includes('chapter-create')) setChapterCreateOpen(true)
      if (restoredSectionIds.length > 0) {
        setOpenSectionCreateIds((current) => new Set([...current, ...restoredSectionIds]))
      }
      setCourseDraftRecovered(true)
      setDirtyDraftKeys((currentKeys) => {
        if (restoredKeys.every((key) => currentKeys.has(key))) return currentKeys
        return new Set([...currentKeys, ...restoredKeys])
      })
    }, 0)
    return () => window.clearTimeout(timer)
    // The signature changes only when the course outline adds draft-bearing forms.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outlineDraftSignature])

  function updateDraftForm(event: FormEvent<HTMLElement>) {
    const target = event.target
    if (!(target instanceof Element)) return
    const form = target.closest<HTMLFormElement>('form[data-dirty-key]')
    const key = form?.dataset.dirtyKey
    if (!form || !key) return
    const dirty = formIsDirty(form)
    if (dirty) writeFormDraft(formDraftKey(key), form)
    else clearFormDraft(formDraftKey(key))
    setDirtyDraftKeys((currentKeys) => {
      const nextKeys = new Set(currentKeys)
      if (dirty) nextKeys.add(key)
      else nextKeys.delete(key)
      return nextKeys
    })
  }

  function markDraftSaved(form: HTMLFormElement) {
    updateFormBaseline(form)
    const key = form.dataset.dirtyKey
    if (!key) return
    clearFormDraft(formDraftKey(key))
    setDirtyDraftKeys((currentKeys) => {
      const nextKeys = new Set(currentKeys)
      nextKeys.delete(key)
      return nextKeys
    })
  }

  function focusCreateInput(formId: string) {
    window.setTimeout(() => {
      document.querySelector<HTMLInputElement>(`#${formId} input[name="title"]`)?.focus()
    }, 0)
  }

  function openChapterCreator() {
    setChapterCreateOpen(true)
    focusCreateInput('chapter-create-form')
  }

  function openSectionCreator(chapterId: number) {
    setOpenSectionCreateIds((current) => new Set([...current, chapterId]))
    focusCreateInput(`section-create-form-${chapterId}`)
  }

  function closeCreateForm(form: HTMLFormElement, chapterId?: number) {
    form.reset()
    markDraftSaved(form)
    if (chapterId === undefined) setChapterCreateOpen(false)
    else {
      setOpenSectionCreateIds((current) => {
        const next = new Set(current)
        next.delete(chapterId)
        return next
      })
    }
  }

  function updateChapter(updated: Chapter) {
    setCourse((current) => current && ({
      ...current,
      chapters: current.chapters.map((chapter) => chapter.id === updated.id ? updated : chapter),
    }))
  }

  function updateSection(updated: Section) {
    setCourse((current) => current && ({
      ...current,
      ...(updated.status === 'completed' ? {} : {
        completed_at: null,
        completion_summary: '',
      }),
      chapters: current.chapters.map((chapter) => chapter.id === updated.chapter_id ? {
        ...chapter,
        sections: chapter.sections.map((section) => section.id === updated.id ? updated : section),
      } : chapter),
    }))
  }

  function openEditor(target: EditTarget, trigger: HTMLElement) {
    setDialogTrigger(trigger)
    setDialogError('')
    setTitleEditDirty(false)
    setTitleEditValue('')
    if (target.kind === 'course') {
      const baseline = courseEditBaseline()
      const restoredDraft = baseline ? readDraft(editDraftKey(target), baseline) : null
      setCourseEditDraft(restoredDraft ?? baseline)
      setCourseEditRecovered(restoredDraft !== null)
    } else {
      setCourseEditDraft(null)
      setCourseEditRecovered(false)
    }
    setEditTarget(target)
  }

  function closeEditor() {
    if (dialogBusy) return
    if (editTarget) clearDraft(editDraftKey(editTarget))
    setDialogError('')
    setEditTarget(null)
    setCourseEditDraft(null)
    setCourseEditRecovered(false)
    setTitleEditDirty(false)
    setTitleEditValue('')
  }

  function openConfirmation(action: ConfirmAction, trigger: HTMLElement) {
    if (dirtyDraftKeys.size > 0 && action.kind.startsWith('delete-')) {
      setError('请先保存或清空章节、小节草稿，再执行删除操作')
      return
    }
    setDialogTrigger(trigger)
    setDialogError('')
    setConfirmAction(action)
  }

  function closeConfirmation() {
    if (dialogBusy) return
    setDialogError('')
    setConfirmAction(null)
  }

  async function handleCourseUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      await saveCourseEdit()
    } catch {
      // saveCourseEdit keeps the dialog open and renders the request error.
    }
  }

  async function saveCourseEdit() {
    if (!course || !courseEditDraft) throw new Error('当前课程不可保存')
    setDialogBusy(true)
    setDialogError('')
    try {
      const updated = await api.updateCourse(course.id, {
        name: courseEditDraft.name.trim(),
        description: courseEditDraft.description,
        learning_goal: courseEditDraft.learning_goal,
      })
      setCourse({ ...course, ...updated })
      clearDraft(editDraftKey({ kind: 'course' }))
      setEditTarget(null)
      setCourseEditDraft(null)
      setCourseEditRecovered(false)
      setError('')
    } catch (requestError) {
      setDialogError(requestError instanceof Error ? requestError.message : '保存课程失败')
      throw requestError
    } finally {
      setDialogBusy(false)
    }
  }

  function updateCourseEditDraft(field: keyof CourseEditDraft, value: string) {
    const baseline = courseEditBaseline()
    if (!baseline) return
    setCourseEditDraft((current) => {
      const next = { ...(current ?? baseline), [field]: value }
      if (JSON.stringify(next) === JSON.stringify(baseline)) clearDraft(`course-${course?.id ?? 'unknown'}-edit`)
      else writeDraft(`course-${course?.id ?? 'unknown'}-edit`, baseline, next)
      return next
    })
  }

  async function handleCreateChapter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!course) return
    const form = event.currentTarget
    const title = String(new FormData(form).get('title') ?? '')
    try {
      const chapter = await api.createChapter(course.id, title)
      setCourse((current) => current && ({
        ...current,
        completed_at: null,
        completion_summary: '',
        chapters: [...current.chapters, chapter],
      }))
      form.reset()
      markDraftSaved(form)
      setChapterCreateOpen(false)
      setError('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '创建章节失败')
    }
  }

  async function handleRenameChapter(chapter: Chapter, title: string, throwOnError = false) {
    setDialogBusy(true)
    setDialogError('')
    try {
      updateChapter(await api.updateChapter(chapter.id, title))
      clearDraft(editDraftKey({ kind: 'chapter', chapter }))
      setEditTarget(null)
      setTitleEditDirty(false)
      setError('')
    } catch (requestError) {
      setDialogError(requestError instanceof Error ? requestError.message : '修改章节失败')
      if (throwOnError) throw requestError
    } finally {
      setDialogBusy(false)
    }
  }

  async function handleCreateSection(event: FormEvent<HTMLFormElement>, chapter: Chapter) {
    event.preventDefault()
    const form = event.currentTarget
    const title = String(new FormData(form).get('title') ?? '')
    try {
      const section = await api.createSection(chapter.id, title)
      setCourse((current) => current && ({
        ...current,
        completed_at: null,
        completion_summary: '',
        chapters: current.chapters.map((item) => item.id === chapter.id ? {
          ...item,
          sections: [...item.sections, section],
        } : item),
      }))
      form.reset()
      markDraftSaved(form)
      setOpenSectionCreateIds((current) => {
        const next = new Set(current)
        next.delete(chapter.id)
        return next
      })
      setError('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '创建小节失败')
    }
  }

  async function handleRenameSection(section: Section, title: string, throwOnError = false) {
    setDialogBusy(true)
    setDialogError('')
    try {
      updateSection(await api.updateSection(section.id, { title }))
      clearDraft(editDraftKey({ kind: 'section', section }))
      setEditTarget(null)
      setTitleEditDirty(false)
      setError('')
    } catch (requestError) {
      setDialogError(requestError instanceof Error ? requestError.message : '修改小节失败')
      if (throwOnError) throw requestError
    } finally {
      setDialogBusy(false)
    }
  }

  async function saveAllCourseDrafts() {
    if (!course) throw new Error('当前课程不可保存')
    const forms = Array.from(document.querySelectorAll<HTMLFormElement>('form[data-dirty-key]'))
    for (const key of dirtyDraftKeys) {
      const form = forms.find((item) => item.dataset.dirtyKey === key)
      if (!form) throw new Error('有一处未保存草稿已关闭，请返回检查后重试')
      if (!form.reportValidity()) throw new Error('请先填写草稿标题')
      const title = String(new FormData(form).get('title') ?? '').trim()
      if (form.dataset.saveKind === 'chapter-create') {
        const chapter = await api.createChapter(course.id, title)
        setCourse((current) => current && ({
          ...current,
          completed_at: null,
          completion_summary: '',
          chapters: [...current.chapters, chapter],
        }))
      } else if (form.dataset.saveKind === 'section-create') {
        const chapterId = Number(form.dataset.entityId)
        const section = await api.createSection(chapterId, title)
        setCourse((current) => current && ({
          ...current,
          completed_at: null,
          completion_summary: '',
          chapters: current.chapters.map((chapter) => chapter.id === chapterId ? {
            ...chapter,
            sections: [...chapter.sections, section],
          } : chapter),
        }))
      } else {
        throw new Error('存在无法识别的课程草稿')
      }
      form.reset()
      markDraftSaved(form)
    }
    setError('')
  }

  async function saveAllCourseChanges() {
    await saveAllCourseDrafts()
    if (!editTarget || !hasEditDraft) return
    if (editTarget.kind === 'course') await saveCourseEdit()
    else if (editTarget.kind === 'chapter') await handleRenameChapter(editTarget.chapter, titleEditValue, true)
    else await handleRenameSection(editTarget.section, titleEditValue, true)
  }

  function discardAllCourseDrafts() {
    dirtyDraftKeys.forEach((key) => clearFormDraft(formDraftKey(key)))
    if (editTarget) clearDraft(editDraftKey(editTarget))
  }

  async function handleStatusChange(section: Section, status: SectionStatus) {
    try {
      updateSection(await api.updateSection(section.id, { status }))
      if (status === 'completed') {
        try {
          await api.refreshSectionLearningMemory(section.id)
        } catch (memoryError) {
          setError(
            memoryError instanceof Error
              ? `小节状态已更新，但学习记忆整理失败：${memoryError.message}`
              : '小节状态已更新，但学习记忆整理失败',
          )
          return
        }
      }
      setError('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '更新小节状态失败')
    }
  }

  async function handleCompleteCourse() {
    if (!course) return
    setCourseCompletionBusy(true)
    setError('')
    try {
      const completion = await api.completeCourse(course.id)
      setCourse((current) => current && ({
        ...current,
        completed_at: completion.completed_at,
        completion_summary: completion.completion_summary,
        completion_summary_version: completion.completion_summary_version,
      }))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '整理课程学习摘要失败')
    } finally {
      setCourseCompletionBusy(false)
    }
  }

  async function handleOpenSection(section: Section, trigger: HTMLElement) {
    if (dirtyDraftKeys.size > 0) {
      setError('请先保存或清空章节、小节草稿，再进入学习')
      return
    }
    rememberHistorySection(section.id)
    setOpeningSectionId(section.id)
    try {
      const record = await api.openTodayRecord(section.id)
      navigate(`/daily-records/${record.id}`)
    } catch (requestError) {
      if (
        requestError instanceof ApiError
        && requestError.status === 409
      ) {
        openConfirmation({ kind: 'continue-section', section }, trigger)
        return
      }
      setError(requestError instanceof Error ? requestError.message : '打开学习记录失败')
    } finally {
      setOpeningSectionId(null)
    }
  }

  async function handleConfirmAction() {
    if (!confirmAction || !course) return
    const action = confirmAction
    setDialogBusy(true)
    setDialogError('')

    try {
      switch (action.kind) {
        case 'delete-course':
          await api.deleteCourse(course.id)
          navigate('/courses')
          break
        case 'delete-chapter':
          await api.deleteChapter(action.chapter.id)
          setCourse((current) => current && ({
            ...current,
            completed_at: null,
            completion_summary: '',
            chapters: current.chapters.filter((item) => item.id !== action.chapter.id),
          }))
          break
        case 'delete-section':
          await api.deleteSection(action.section.id)
          setCourse((current) => current && ({
            ...current,
            completed_at: null,
            completion_summary: '',
            chapters: current.chapters.map((chapter) => chapter.id === action.section.chapter_id ? {
              ...chapter,
              sections: chapter.sections.filter((item) => item.id !== action.section.id),
            } : chapter),
          }))
          break
        case 'continue-section': {
          rememberHistorySection(action.section.id)
          const record = await api.openTodayRecord(action.section.id, true)
          navigate(`/daily-records/${record.id}`)
          break
        }
      }
      setConfirmAction(null)
      setError('')
    } catch (requestError) {
      setDialogError(requestError instanceof Error ? requestError.message : '操作失败')
    } finally {
      setDialogBusy(false)
    }
  }

  function rememberHistorySection(sectionId: number) {
    if (!course) return
    sessionStorage.setItem(historyStorageKey(course.id), String(sectionId))
    setExpandedHistorySectionId(sectionId)
  }

  function toggleSectionHistory(sectionId: number) {
    if (!course) return
    if (expandedHistorySectionId === sectionId) {
      sessionStorage.removeItem(historyStorageKey(course.id))
      setExpandedHistorySectionId(null)
      setShowAllHistory(false)
      return
    }
    rememberHistorySection(sectionId)
    setShowAllHistory(false)
  }

  if (!course) {
    return (
      <main className="context-page">
        <PageBackBar ariaLabel="课程导航" to="/courses" />
        <div className="content content--wide context-page__content">
          <p className="error-banner" role="alert">{routeData.notFound ? '课程不存在' : error}</p>
        </div>
      </main>
    )
  }

  const confirmDialogConfig = confirmAction
    ? getConfirmDialogConfig(confirmAction, course.name)
    : null
  const materialScopes: MaterialScopeOption[] = [
    {
      value: `course-${course.id}`,
      label: '整个课程',
      course_id: course.id,
      chapter_id: null,
      section_id: null,
      is_primary: false,
    },
    ...(course.chapters ?? []).flatMap((chapter) => [
      {
        value: `chapter-${chapter.id}`,
        label: chapter.title,
        course_id: course.id,
        chapter_id: chapter.id,
        section_id: null,
        is_primary: false,
      },
      ...(chapter.sections ?? []).map((section) => ({
        value: `section-${section.id}`,
        label: `${chapter.title} · ${section.title}`,
        course_id: course.id,
        chapter_id: chapter.id,
        section_id: section.id,
        is_primary: false,
      })),
    ]),
  ]
  const courseMaterialScope = materialScopes[0]
  const visibleMaterials = materialScope
    ? materials.filter((material) => (
      material.course_id === materialScope.course_id
      && material.chapter_id === materialScope.chapter_id
      && material.section_id === materialScope.section_id
    ))
    : []
  const sections = course.chapters.flatMap((chapter) => chapter.sections)
  const courseCanComplete = sections.length > 0
    && sections.every((section) => section.status === 'completed')
  const todayDate = localDateKey()

  return (
    <main ref={pageRef} className="context-page" onInputCapture={updateDraftForm} onChangeCapture={updateDraftForm}>
      <PageBackBar ariaLabel="课程导航" to="/courses" />
      <div className="content content--wide context-page__content">
        <header className="course-header">
          <div>
            <p className="eyebrow">课程</p>
            <h1>{course.name}</h1>
            {course.description && <p className="page-summary">{course.description}</p>}
            {course.learning_goal && <p className="learning-goal">{course.learning_goal}</p>}
          </div>
          <div className="header-actions">
            {courseCanComplete && !course.completed_at && (
              <button
                className="primary-button"
                type="button"
                disabled={courseCompletionBusy}
                onClick={() => void handleCompleteCourse()}
              >
                <CheckCircle2 size={16} />
                {courseCompletionBusy ? '正在整理' : '完成课程'}
              </button>
            )}
            <button className="secondary-button" type="button" disabled={materialsLoading} onClick={() => void toggleMaterials(courseMaterialScope)}>
              <Library size={16} />{materialsOpen && materialScope?.value === courseMaterialScope.value ? '收起课程材料' : '课程材料'}
            </button>
            <Link className="secondary-button inline-link-button" to={`/courses/${course.id}/memory`}>
              <Brain size={16} />学习记忆
            </Link>
            <button className="icon-button" type="button" title="编辑课程" aria-label="编辑课程" onClick={(event) => openEditor({ kind: 'course' }, event.currentTarget)}><Pencil size={17} /></button>
            <button className="icon-button icon-button--danger" type="button" title="删除课程" aria-label="删除课程" onClick={(event) => openConfirmation({ kind: 'delete-course' }, event.currentTarget)}><Trash2 size={17} /></button>
          </div>
        </header>

      {error && <p className="error-banner" role="alert">{error}</p>}
      <DraftStatus
        key={courseDraftRecovered ? 'course-restored' : 'course-current'}
        dirtyCount={dirtyDraftKeys.size}
        recoveredLabel={courseDraftRecovered ? '已恢复课程草稿' : undefined}
      />

        {course.completed_at && course.completion_summary && (
          <section className="course-completion-summary" aria-labelledby="course-completion-title">
            <div>
              <CheckCircle2 size={18} aria-hidden="true" />
              <h2 id="course-completion-title">课程学习摘要</h2>
              <span>已纳入后续学习上下文</span>
            </div>
            <div className="course-completion-summary__content">
              <MarkdownContent content={course.completion_summary} />
            </div>
          </section>
        )}

        {materialsOpen && (
          <section ref={materialsPanelRef} className="course-materials" aria-label="课程参考材料">
            <div className="section-heading section-heading--spaced">
              <div><h2>{materialScope?.label}材料</h2><p>此处添加的材料固定用于这个范围。</p></div>
            </div>
            <MaterialLibrary
              key={materialScope?.value}
              materials={visibleMaterials}
              scopeOptions={materialScope ? [materialScope] : [courseMaterialScope]}
              defaultScope={materialScope?.value ?? courseMaterialScope.value}
              showScopeSelect={false}
              allowScopeEdit={false}
              onChanged={async () => {
                const result = await api.listMaterials(course.id)
                setMaterials(Array.isArray(result) ? result : [])
              }}
            />
          </section>
        )}

        <section className="outline" aria-labelledby="outline-title">
        <div className="section-heading section-heading--spaced">
          <h2 id="outline-title">章节与小节</h2>
          <span className="count-label">{course.chapters.length} 个章节</span>
          <button
            className="secondary-button outline-create-button"
            type="button"
            aria-expanded={chapterCreateOpen}
            aria-controls="chapter-create-form"
            onClick={openChapterCreator}
          >
            <Plus size={15} />添加章节
          </button>
        </div>

        <form
          id="chapter-create-form"
          className="add-chapter-form"
          data-dirty-key="chapter-create"
          data-save-kind="chapter-create"
          hidden={!chapterCreateOpen}
          onSubmit={handleCreateChapter}
        >
          <input name="title" aria-label="章节标题" placeholder="新章节标题" required maxLength={200} />
          <button className="primary-button" type="submit"><Plus size={16} />保存章节</button>
          <button className="secondary-button" type="button" onClick={(event) => closeCreateForm(event.currentTarget.form!)}>取消</button>
        </form>

        {course.chapters.map((chapter, chapterIndex) => (
          <article className="chapter-block" key={chapter.id}>
            <header className="chapter-header">
              <div><span>{String(chapterIndex + 1).padStart(2, '0')}</span><h3>{chapter.title}</h3></div>
              <div className="row-actions">
                <button
                  className="icon-button"
                  type="button"
                  title="添加小节"
                  aria-label={`在${chapter.title}中添加小节`}
                  aria-expanded={openSectionCreateIds.has(chapter.id)}
                  aria-controls={`section-create-form-${chapter.id}`}
                  onClick={() => openSectionCreator(chapter.id)}
                ><Plus size={15} /></button>
                <button className="icon-button" type="button" title="章节材料" aria-label={`${chapter.title}章节材料`} onClick={() => {
                  const scope = materialScopes.find((item) => item.value === `chapter-${chapter.id}`)
                  if (scope) void toggleMaterials(scope)
                }}><Library size={15} /></button>
                <button className="icon-button" type="button" title="修改章节" aria-label={`修改章节 ${chapter.title}`} onClick={(event) => openEditor({ kind: 'chapter', chapter }, event.currentTarget)}><Pencil size={15} /></button>
                <button className="icon-button icon-button--danger" type="button" title="删除章节" aria-label={`删除章节 ${chapter.title}`} onClick={(event) => openConfirmation({ kind: 'delete-chapter', chapter }, event.currentTarget)}><Trash2 size={15} /></button>
              </div>
            </header>

            <div className="section-list">
              {chapter.sections.map((section, sectionIndex) => {
                const dailyRecords = [...section.daily_records]
                  .sort((left, right) => right.study_date.localeCompare(left.study_date))
                const latestRecord = dailyRecords[0]
                const historyExpanded = expandedHistorySectionId === section.id
                const visibleRecords = showAllHistory
                  ? dailyRecords
                  : dailyRecords.slice(0, HISTORY_PREVIEW_COUNT)
                const hasTodayRecord = dailyRecords.some((record) => record.study_date === todayDate)

                return (
                <div className="section-entry" key={section.id}>
                  <div className="section-row">
                    <span className="section-number">{chapterIndex + 1}.{sectionIndex + 1}</span>
                    <span className="section-title">{section.title}</span>
                    <select
                      aria-label={`${section.title}状态`}
                      className={`status-select status-select--${section.status}`}
                      value={section.status}
                      onChange={(event) => handleStatusChange(section, event.target.value as SectionStatus)}
                    >
                      {Object.entries(statusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                    <div className="row-actions">
                      <button className="icon-button" type="button" title="小节材料" aria-label={`${section.title}小节材料`} onClick={() => {
                        const scope = materialScopes.find((item) => item.value === `section-${section.id}`)
                        if (scope) void toggleMaterials(scope)
                      }}><Library size={15} /></button>
                      <button className="icon-button" type="button" title="修改小节" aria-label={`修改小节 ${section.title}`} onClick={(event) => openEditor({ kind: 'section', section }, event.currentTarget)}><Pencil size={15} /></button>
                      <button className="icon-button icon-button--danger" type="button" title="删除小节" aria-label={`删除小节 ${section.title}`} onClick={(event) => openConfirmation({ kind: 'delete-section', section }, event.currentTarget)}><Trash2 size={15} /></button>
                      <button
                        className="start-button"
                        type="button"
                        disabled={openingSectionId !== null}
                        onClick={(event) => handleOpenSection(section, event.currentTarget)}
                      >
                        <Play size={15} />
                        {openingSectionId === section.id
                          ? '正在打开'
                          : hasTodayRecord ? '继续学习' : '开始学习'}
                      </button>
                    </div>
                  </div>
                  {dailyRecords.length > 0 && (
                    <div className="section-history">
                      <button
                        className="section-history__summary"
                        type="button"
                        aria-label={`学习记录 ${dailyRecords.length} 次，最近 ${formatStudyDate(latestRecord.study_date, todayDate)}，${latestRecord.is_completed ? '当次完成' : '未完成'}`}
                        aria-expanded={historyExpanded}
                        aria-controls={`section-history-${section.id}`}
                        onClick={() => toggleSectionHistory(section.id)}
                      >
                        <CalendarDays size={14} aria-hidden="true" />
                        <span className="section-history__label">学习记录</span>
                        <span>{dailyRecords.length} 次</span>
                        <span aria-hidden="true">·</span>
                        <span>最近 {formatStudyDate(latestRecord.study_date, todayDate)}</span>
                        <span
                          className={`section-history__latest-status ${latestRecord.is_completed ? 'is-complete' : ''}`}
                        >
                          · {latestRecord.is_completed ? '当次完成' : '未完成'}
                        </span>
                        <ChevronDown className="section-history__chevron" size={14} aria-hidden="true" />
                      </button>
                      {historyExpanded && (
                        <div className="section-history__panel" id={`section-history-${section.id}`}>
                          <div className="section-history__list">
                            {visibleRecords.map((dailyRecord) => (
                              <Link
                                className="section-history__item"
                                to={`/daily-records/${dailyRecord.id}`}
                                key={dailyRecord.id}
                                aria-label={`${dailyRecord.study_date} · ${dailyRecord.is_completed ? '当次完成' : '未完成'}`}
                                onClick={() => rememberHistorySection(section.id)}
                              >
                                <span className="section-history__date">
                                  {dailyRecord.study_date === todayDate && <strong>今天 · </strong>}
                                  {formatStudyDate(dailyRecord.study_date, todayDate)}
                                </span>
                                <span className={`section-history__status ${dailyRecord.is_completed ? 'is-complete' : ''}`}>
                                  {dailyRecord.is_completed ? '当次完成' : '未完成'}
                                </span>
                                <ChevronRight size={14} aria-hidden="true" />
                              </Link>
                            ))}
                          </div>
                          {dailyRecords.length > HISTORY_PREVIEW_COUNT && (
                            <button
                              className="section-history__more"
                              type="button"
                              onClick={() => setShowAllHistory((current) => !current)}
                            >
                              {showAllHistory
                                ? `收起到最近 ${HISTORY_PREVIEW_COUNT} 次`
                                : `查看全部 ${dailyRecords.length} 次`}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                )
              })}
              {chapter.sections.length === 0 && (
                <div className="inline-empty inline-empty-action">
                  <span>本章还没有小节</span>
                  <button className="secondary-button" type="button" onClick={() => openSectionCreator(chapter.id)}>
                    <Plus size={15} />添加第一个小节
                  </button>
                </div>
              )}
            </div>

            <form
              id={`section-create-form-${chapter.id}`}
              className="inline-create-form"
              data-dirty-key={`section-create-${chapter.id}`}
              data-save-kind="section-create"
              data-entity-id={chapter.id}
              hidden={!openSectionCreateIds.has(chapter.id)}
              onSubmit={(event) => handleCreateSection(event, chapter)}
            >
              <input name="title" aria-label={`在${chapter.title}中创建小节`} placeholder="小节标题" required maxLength={200} />
              <button className="primary-button" type="submit"><Plus size={15} />保存小节</button>
              <button className="secondary-button" type="button" onClick={(event) => closeCreateForm(event.currentTarget.form!, chapter.id)}>取消</button>
            </form>
          </article>
        ))}

        {course.chapters.length === 0 && (
          <div className="empty-state empty-state--compact outline-empty-state">
            <p>还没有章节</p>
            <button className="primary-button" type="button" onClick={openChapterCreator}>
              <Plus size={16} />添加第一个章节
            </button>
          </div>
        )}
        </section>
      </div>

      {editTarget?.kind === 'course' && (
        <AppDialog
          open
          size="medium"
          title="编辑课程"
          busy={dialogBusy}
          closeOnBackdrop={false}
          onClose={closeEditor}
          returnFocusTo={dialogTrigger}
          footer={(
            <>
              <button className="secondary-button" type="button" disabled={dialogBusy} onClick={closeEditor}>取消</button>
              <button className="primary-button" type="submit" form="course-edit-dialog-form" disabled={dialogBusy}>
                <Check size={16} aria-hidden="true" />{dialogBusy ? '保存中...' : '保存'}
              </button>
            </>
          )}
        >
          <form id="course-edit-dialog-form" className="dialog-form" onSubmit={handleCourseUpdate}>
            <DraftStatus
              dirtyCount={courseEditDirty ? 1 : 0}
              recoveredLabel={courseEditRecovered ? '已恢复课程编辑草稿' : undefined}
            />
            <label>
              课程名称
              <input name="name" data-dialog-initial-focus value={courseEditDraft?.name ?? ''} required maxLength={200} disabled={dialogBusy} onChange={(event) => updateCourseEditDraft('name', event.target.value)} />
            </label>
            <label>
              课程描述
              <textarea name="description" rows={3} value={courseEditDraft?.description ?? ''} disabled={dialogBusy} onChange={(event) => updateCourseEditDraft('description', event.target.value)} />
            </label>
            <label>
              长期研究方向或学习目标
              <textarea name="learning_goal" rows={4} value={courseEditDraft?.learning_goal ?? ''} disabled={dialogBusy} onChange={(event) => updateCourseEditDraft('learning_goal', event.target.value)} />
            </label>
            {dialogError && <p className="dialog-error" role="alert">{dialogError}</p>}
          </form>
        </AppDialog>
      )}

      {editTarget?.kind === 'chapter' && (
        <TextEditDialog
          key={`chapter-${editTarget.chapter.id}`}
          open
          title="修改章节"
          label="章节标题"
          initialValue={editTarget.chapter.title}
          draftKey={editDraftKey(editTarget)}
          busy={dialogBusy}
          error={dialogError}
          returnFocusTo={dialogTrigger}
          onClose={closeEditor}
          onDirtyChange={(dirty, value) => { setTitleEditDirty(dirty); setTitleEditValue(value) }}
          onSubmit={(title) => handleRenameChapter(editTarget.chapter, title)}
        />
      )}

      {editTarget?.kind === 'section' && (
        <TextEditDialog
          key={`section-${editTarget.section.id}`}
          open
          title="修改小节"
          label="小节标题"
          initialValue={editTarget.section.title}
          draftKey={editDraftKey(editTarget)}
          busy={dialogBusy}
          error={dialogError}
          returnFocusTo={dialogTrigger}
          onClose={closeEditor}
          onDirtyChange={(dirty, value) => { setTitleEditDirty(dirty); setTitleEditValue(value) }}
          onSubmit={(title) => handleRenameSection(editTarget.section, title)}
        />
      )}

      {confirmAction && confirmDialogConfig && (
        confirmDialogConfig.finalDescription && confirmDialogConfig.targetKey
          ? <TwoStepDeleteDialog
              key={confirmDialogConfig.targetKey}
              open
              title={confirmDialogConfig.title}
              description={confirmDialogConfig.description}
              finalDescription={confirmDialogConfig.finalDescription}
              busy={dialogBusy}
              error={dialogError}
              returnFocusTo={dialogTrigger}
              onCancel={closeConfirmation}
              onConfirm={handleConfirmAction}
            />
          : <ConfirmDialog
              open
              title={confirmDialogConfig.title}
              description={confirmDialogConfig.description}
              confirmLabel={confirmDialogConfig.confirmLabel}
              variant={confirmDialogConfig.variant}
              busy={dialogBusy}
              error={dialogError}
              returnFocusTo={dialogTrigger}
              onCancel={closeConfirmation}
              onConfirm={handleConfirmAction}
            />
      )}
      <UnsavedChangesGuard
        dirty={dirtyDraftKeys.size > 0 || hasEditDraft}
        onDiscard={discardAllCourseDrafts}
        onSave={saveAllCourseChanges}
      />
    </main>
  )
}
