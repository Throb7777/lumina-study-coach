import { Files, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { CourseDetail, LearningMaterial } from '../api'
import { AppDialog } from './AppDialog'
import { MaterialLibrary } from './MaterialLibrary'
import type { MaterialScopeOption } from './MaterialLibrary'

interface MaterialLibraryDialogProps {
  onClose: () => void
  open: boolean
  returnFocusTo?: HTMLElement | null
}

export function MaterialLibraryDialog({
  onClose,
  open,
  returnFocusTo,
}: MaterialLibraryDialogProps) {
  const [materials, setMaterials] = useState<LearningMaterial[]>([])
  const [courses, setCourses] = useState<CourseDetail[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [courseFilter, setCourseFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    void Promise.resolve()
      .then(() => {
        if (controller.signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
        setLoading(true)
        setError('')
        return Promise.all([
          api.listMaterials(undefined, controller.signal),
          api.listCourses(controller.signal),
        ])
      })
      .then(async ([loadedMaterials, summaries]) => {
        const loadedCourses = await Promise.all(
          summaries.map((course) => api.getCourse(course.id, controller.signal)),
        )
        if (controller.signal.aborted) return
        setMaterials(loadedMaterials)
        setCourses(loadedCourses)
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof Error && requestError.name === 'AbortError') return
        setError(requestError instanceof Error ? requestError.message : '读取材料库失败')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [open])

  const scopeOptions = useMemo<MaterialScopeOption[]>(() => courses.flatMap((course) => [
    {
      value: `course-${course.id}`,
      label: `${course.name} · 课程`,
      course_id: course.id,
      chapter_id: null,
      section_id: null,
      is_primary: false,
    },
    ...course.chapters.flatMap((chapter) => [
      {
        value: `chapter-${chapter.id}`,
        label: `${course.name} · ${chapter.title}`,
        course_id: course.id,
        chapter_id: chapter.id,
        section_id: null,
        is_primary: false,
      },
      ...chapter.sections.map((section) => ({
        value: `section-${section.id}`,
        label: `${course.name} · ${chapter.title} · ${section.title}`,
        course_id: course.id,
        chapter_id: chapter.id,
        section_id: section.id,
        is_primary: false,
      })),
    ]),
  ]), [courses])

  const normalizedQuery = query.trim().toLocaleLowerCase()
  const visibleMaterials = materials.filter((material) => (
    (courseFilter === 'all' || material.course_id === Number(courseFilter))
    && (typeFilter === 'all' || material.source_type === typeFilter)
    && (statusFilter === 'all' || material.status === statusFilter)
    && (!normalizedQuery || [
      material.title,
      material.course_name,
      material.chapter_title,
      material.section_title,
      material.original_name,
      material.source_url,
    ].some((value) => value.toLocaleLowerCase().includes(normalizedQuery)))
  ))

  async function refreshMaterials() {
    try {
      setMaterials(await api.listMaterials())
      setError('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '刷新材料库失败')
    }
  }

  return (
    <AppDialog
      open={open}
      title="材料库"
      description="统一查看和管理课程、章节与小节使用的 PDF、网页和视频字幕。"
      size="workspace"
      busy={loading}
      closeOnBackdrop={false}
      returnFocusTo={returnFocusTo}
      onClose={onClose}
    >
      {error && <p className="inline-error" role="alert">{error}</p>}
      {loading ? (
        <p className="muted">正在读取材料...</p>
      ) : (
        <>
          <section className="material-index-toolbar material-index-toolbar--dialog" aria-label="材料筛选">
            <label className="index-search">
              <Search size={16} aria-hidden="true" />
              <span className="sr-only">搜索材料</span>
              <input
                type="search"
                value={query}
                placeholder="搜索材料名称、课程或来源"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <label className="compact-select"><span className="sr-only">按课程筛选</span><select value={courseFilter} onChange={(event) => setCourseFilter(event.target.value)}><option value="all">全部课程</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.name}</option>)}</select></label>
            <label className="compact-select"><span className="sr-only">按类型筛选</span><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">全部类型</option><option value="pdf">PDF</option><option value="url">网页</option><option value="video">视频字幕</option></select></label>
            <label className="compact-select"><span className="sr-only">按状态筛选</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">全部状态</option><option value="ready">可用</option><option value="failed">解析失败</option></select></label>
          </section>
          {materials.length > 0 && visibleMaterials.length === 0 ? (
            <div className="empty-state empty-state--compact"><Files size={20} aria-hidden="true" /><p>没有匹配的材料</p></div>
          ) : (
            <MaterialLibrary
              materials={visibleMaterials}
              scopeOptions={scopeOptions}
              defaultScope={scopeOptions[0]?.value}
              allowAdd={scopeOptions.length > 0}
              allowScopeEdit={scopeOptions.length > 0}
              showCourse
              onChanged={refreshMaterials}
            />
          )}
        </>
      )}
    </AppDialog>
  )
}
