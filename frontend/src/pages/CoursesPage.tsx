import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, BookMarked, BookOpen, Plus, Search, Trash2 } from 'lucide-react'
import { flushSync } from 'react-dom'
import { Link, useLoaderData, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { CourseSummary } from '../api'
import { AppDialog } from '../components/AppDialog'
import { DraftStatus } from '../components/DraftStatus'
import { TwoStepDeleteDialog } from '../components/TwoStepDeleteDialog'
import { UnsavedChangesGuard } from '../components/UnsavedChangesGuard'
import { clearDraft, readDraft, writeDraft } from '../draftStorage'
import { dismissBundledExample, isBundledExampleVisible } from '../examplePreference'
import type { CoursesRouteData } from '../routeData'

interface CourseDraft {
  description: string
  learning_goal: string
  name: string
}

const emptyCourseDraft: CourseDraft = { description: '', learning_goal: '', name: '' }
const createCourseDraftKey = 'course-create'

export function CoursesPage() {
  const routeData = useLoaderData() as CoursesRouteData
  const [courses, setCourses] = useState<CourseSummary[]>(routeData.courses)
  const error = routeData.error
  const [welcomeOpen, setWelcomeOpen] = useState(routeData.onboardingPending)
  const [welcomeBusy, setWelcomeBusy] = useState(false)
  const [welcomeError, setWelcomeError] = useState('')
  const [query, setQuery] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [restoredCreateDraft] = useState<CourseDraft | null>(() => readDraft(createCourseDraftKey, emptyCourseDraft))
  const [createDraft, setCreateDraft] = useState<CourseDraft>(restoredCreateDraft ?? emptyCourseDraft)
  const [createOpen, setCreateOpen] = useState(restoredCreateDraft !== null)
  const [createError, setCreateError] = useState('')
  const [exampleVisible, setExampleVisible] = useState(isBundledExampleVisible)
  const [exampleDeleteOpen, setExampleDeleteOpen] = useState(false)
  const exampleDeleteButton = useRef<HTMLButtonElement | null>(null)
  const navigate = useNavigate()
  const createDirty = JSON.stringify(createDraft) !== JSON.stringify(emptyCourseDraft)

  useEffect(() => {
    if (createDirty) writeDraft(createCourseDraftKey, emptyCourseDraft, createDraft)
    else clearDraft(createCourseDraftKey)
  }, [createDraft, createDirty])

  async function completeOnboarding() {
    setWelcomeBusy(true)
    setWelcomeError('')
    try {
      await api.completeOnboarding()
      setWelcomeOpen(false)
    } catch (requestError) {
      setWelcomeError(requestError instanceof Error ? requestError.message : '暂时无法开始使用')
    } finally {
      setWelcomeBusy(false)
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      await createCourse(true)
    } catch {
      // createCourse keeps the dialog open and renders the request error.
    }
  }

  async function createCourse(openCreatedCourse: boolean) {
    if (!createDraft.name.trim()) throw new Error('请填写课程名称')
    setSubmitting(true)
    setCreateError('')
    try {
      const course = await api.createCourse({
        name: createDraft.name.trim(),
        description: createDraft.description,
        learning_goal: createDraft.learning_goal,
      })
      clearDraft(createCourseDraftKey)
      flushSync(() => {
        setCourses((current) => [{
          ...course,
          total_sections: 0,
          completed_sections: 0,
          in_progress_sections: 0,
          course_state: 'not_started',
          last_study_at: null,
          created_at: new Date().toISOString(),
        }, ...current])
        setCreateDraft(emptyCourseDraft)
        setCreateOpen(false)
      })
      if (openCreatedCourse) navigate(`/courses/${course.id}`)
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '创建课程失败'
      setCreateError(message)
      throw requestError
    } finally {
      setSubmitting(false)
    }
  }

  function closeCreateDialog() {
    clearDraft(createCourseDraftKey)
    setCreateDraft(emptyCourseDraft)
    setCreateOpen(false)
    setCreateError('')
  }

  const normalizedQuery = query.trim().toLocaleLowerCase()
  const filteredCourses = normalizedQuery
    ? courses.filter((course) => (
        course.name.toLocaleLowerCase().includes(normalizedQuery)
        || course.description.toLocaleLowerCase().includes(normalizedQuery)
        || course.learning_goal.toLocaleLowerCase().includes(normalizedQuery)
      ))
    : courses
  const unfinishedCourses = filteredCourses.filter((course) => course.course_state !== 'completed')
  const completedCourses = filteredCourses.filter((course) => course.course_state === 'completed')

  function courseActivityLabel(course: CourseSummary) {
    if (course.course_state === 'completed') return '已完成'
    if (!course.last_study_at) return '尚未开始'
    return `最近学习 ${new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(new Date(course.last_study_at))}`
  }

  function courseRow(course: CourseSummary) {
    const progress = course.total_sections === 0
      ? 0
      : Math.round((course.completed_sections / course.total_sections) * 100)
    return (
      <Link className="course-item" to={`/courses/${course.id}`} key={course.id}>
        <div className="course-item__content">
          <div className="course-item__title-row"><h3>{course.name}</h3><span>{courseActivityLabel(course)}</span></div>
          <p>{course.description || course.learning_goal || '尚未填写课程描述'}</p>
          <div className="course-item__progress">
            <span>已完成 {course.completed_sections}/{course.total_sections} 个小节</span>
            {course.in_progress_sections > 0 && <span>{course.in_progress_sections} 个进行中</span>}
          </div>
          <div className="progress-track progress-track--compact" aria-label={`已完成 ${course.completed_sections} 个，共 ${course.total_sections} 个小节`}>
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>
        <ArrowRight size={18} aria-hidden="true" />
      </Link>
    )
  }

  return (
    <main className="content content--workspace">
      <header className="page-heading">
        <div>
          <p className="eyebrow">课程</p>
          <h1>学习课程</h1>
          <p className="page-summary">按课程组织章节、小节和每日学习记录。</p>
        </div>
      </header>

      {error && <p className="error-banner" role="alert">{error}</p>}
      {routeData.onboardingError && (
        <p className="error-banner" role="alert">{routeData.onboardingError}</p>
      )}

      <section className="course-list" aria-labelledby="course-list-title">
          <div className="course-toolbar">
            <div className="section-heading">
            <BookOpen size={18} aria-hidden="true" />
            <h2 id="course-list-title">全部课程</h2>
              <span className="count-label">共 {courses.length} 门</span>
            </div>
            <div className="course-toolbar__actions">
              <label className="course-search">
                <Search size={16} aria-hidden="true" />
                <span className="sr-only">搜索课程</span>
                <input
                  type="search"
                  value={query}
                  placeholder="搜索课程名称、描述或学习目标"
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <button className="primary-button" type="button" onClick={() => setCreateOpen(true)}>
                <Plus size={17} aria-hidden="true" />
                创建课程
              </button>
            </div>
          </div>
          {courses.length === 0 && !exampleVisible && !error && (
            <div className="empty-state">
              <BookOpen size={22} aria-hidden="true" />
              <p>还没有课程</p>
              <button className="secondary-button" type="button" onClick={() => setCreateOpen(true)}>
                <Plus size={16} aria-hidden="true" />
                创建第一门课程
              </button>
            </div>
          )}
          {courses.length > 0 && filteredCourses.length === 0 && (
            <div className="empty-state empty-state--compact">
              <Search size={20} aria-hidden="true" />
              <p>没有匹配的课程</p>
            </div>
          )}
          <div className="course-items">
            {unfinishedCourses.map(courseRow)}
            {exampleVisible && !normalizedQuery && (
              <div className="course-item-shell course-item-shell--example">
                <Link className="course-item course-item--example" to="/example">
                  <BookMarked size={20} aria-hidden="true" />
                  <div className="course-item__content">
                    <div className="course-item__title-row"><h3>MIT 18.06 线性代数示例</h3><span>只读示例</span></div>
                    <p>查看真实材料驱动的六步学习、12 道练习、逐题批改和最终笔记。</p>
                    <div className="course-item__progress"><span>完整流程已完成</span><span>不会写入学习数据</span></div>
                  </div>
                  <ArrowRight size={18} aria-hidden="true" />
                </Link>
                <button
                  ref={exampleDeleteButton}
                  className="icon-button course-item-shell__delete"
                  type="button"
                  title="删除示例课程"
                  aria-label="删除示例课程"
                  onClick={() => setExampleDeleteOpen(true)}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </div>
            )}
            {completedCourses.map(courseRow)}
          </div>
      </section>

      <AppDialog
        open={welcomeOpen}
        title="欢迎使用 Lumina"
        description={(
          <div className="onboarding-welcome">
            <img src="/favicon-192.png" alt="" width="48" height="48" />
            <p>从课程和小节开始，按清晰的学习流程持续推进。</p>
          </div>
        )}
        busy={welcomeBusy}
        closeOnBackdrop={false}
        showCloseButton={false}
        onClose={() => undefined}
        footer={(
          <button
            className="primary-button onboarding-welcome__action"
            type="button"
            data-dialog-initial-focus
            disabled={welcomeBusy}
            onClick={() => void completeOnboarding()}
          >
            <BookOpen size={17} aria-hidden="true" />
            {welcomeBusy ? '正在进入' : '开始使用'}
          </button>
        )}
      >
        {welcomeError && <p className="dialog-error" role="alert">{welcomeError}</p>}
      </AppDialog>
      <AppDialog
        open={createOpen}
        title="创建课程"
        description="先建立课程，再继续添加章节和小节。"
        size="medium"
        busy={submitting}
        closeOnBackdrop={false}
        onClose={closeCreateDialog}
        footer={(
          <>
            <button className="secondary-button" type="button" disabled={submitting} onClick={closeCreateDialog}>取消</button>
            <button className="primary-button" type="submit" form="create-course-form" disabled={submitting}>
              <Plus size={17} aria-hidden="true" />
              {submitting ? '正在创建' : '创建并进入'}
            </button>
          </>
        )}
      >
          <form id="create-course-form" className="dialog-form" onSubmit={handleCreate}>
            <DraftStatus
              dirtyCount={createDirty ? 1 : 0}
              recoveredLabel={restoredCreateDraft === null ? undefined : '已恢复课程草稿'}
            />
            {createError && <p className="dialog-error" role="alert">{createError}</p>}
            <label>
              课程名称
              <input name="name" required maxLength={200} data-dialog-initial-focus value={createDraft.name} onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <label>
              课程描述
              <textarea name="description" rows={3} maxLength={5000} value={createDraft.description} onChange={(event) => setCreateDraft((current) => ({ ...current, description: event.target.value }))} />
            </label>
            <label>
              长期研究方向或学习目标
              <textarea name="learning_goal" rows={3} maxLength={5000} value={createDraft.learning_goal} onChange={(event) => setCreateDraft((current) => ({ ...current, learning_goal: event.target.value }))} />
            </label>
          </form>
      </AppDialog>
      <TwoStepDeleteDialog
        open={exampleDeleteOpen}
        title="删除示例课程？"
        description="删除后，示例课程将从本机课程首页隐藏，不会影响你的课程和学习数据。"
        finalDescription="确认永久隐藏内置示例课程？此操作不会删除任何真实课程。"
        returnFocusTo={exampleDeleteButton.current}
        onCancel={() => setExampleDeleteOpen(false)}
        onConfirm={() => {
          dismissBundledExample()
          setExampleVisible(false)
          setExampleDeleteOpen(false)
        }}
      />
      <UnsavedChangesGuard
        dirty={createOpen && createDirty}
        onDiscard={() => clearDraft(createCourseDraftKey)}
        onSave={() => createCourse(false)}
      />
    </main>
  )
}
