import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, BookMarked, BookOpen, Plus, Search } from 'lucide-react'
import { flushSync } from 'react-dom'
import { Link, useLoaderData, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { CourseSummary } from '../api'
import { AppDialog } from '../components/AppDialog'
import { DraftStatus } from '../components/DraftStatus'
import { UnsavedChangesGuard } from '../components/UnsavedChangesGuard'
import { clearDraft, readDraft, writeDraft } from '../draftStorage'
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
  const [query, setQuery] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [restoredCreateDraft] = useState<CourseDraft | null>(() => readDraft(createCourseDraftKey, emptyCourseDraft))
  const [createDraft, setCreateDraft] = useState<CourseDraft>(restoredCreateDraft ?? emptyCourseDraft)
  const [createOpen, setCreateOpen] = useState(restoredCreateDraft !== null)
  const [createError, setCreateError] = useState('')
  const navigate = useNavigate()
  const createDirty = JSON.stringify(createDraft) !== JSON.stringify(emptyCourseDraft)

  useEffect(() => {
    if (createDirty) writeDraft(createCourseDraftKey, emptyCourseDraft, createDraft)
    else clearDraft(createCourseDraftKey)
  }, [createDraft, createDirty])

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

      <section className="course-list" aria-labelledby="course-list-title">
          <div className="course-toolbar">
            <div className="section-heading">
            <BookOpen size={18} aria-hidden="true" />
            <h2 id="course-list-title">全部课程</h2>
              <span className="count-label">共 {courses.length} 门</span>
            </div>
            <div className="course-toolbar__actions">
              <Link className="secondary-button" to="/example">
                <BookMarked size={16} aria-hidden="true" />
                查看示例
              </Link>
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
          {courses.length === 0 && !error && (
            <div className="empty-state">
              <BookOpen size={22} aria-hidden="true" />
              <p>还没有课程</p>
              <button className="secondary-button" type="button" onClick={() => setCreateOpen(true)}>
                <Plus size={16} aria-hidden="true" />
                创建第一门课程
              </button>
              <Link className="text-button" to="/example">先看完整示例</Link>
            </div>
          )}
          {courses.length > 0 && filteredCourses.length === 0 && (
            <div className="empty-state empty-state--compact">
              <Search size={20} aria-hidden="true" />
              <p>没有匹配的课程</p>
            </div>
          )}
          <div className="course-items">
            {filteredCourses.map((course) => {
              const progress = course.total_sections === 0
                ? 0
                : Math.round((course.completed_sections / course.total_sections) * 100)
              return (
              <Link className="course-item" to={`/courses/${course.id}`} key={course.id}>
                <div className="course-item__content">
                  <h3>{course.name}</h3>
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
            })}
          </div>
      </section>

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
      <UnsavedChangesGuard
        dirty={createOpen && createDirty}
        onDiscard={() => clearDraft(createCourseDraftKey)}
        onSave={() => createCourse(false)}
      />
    </main>
  )
}
