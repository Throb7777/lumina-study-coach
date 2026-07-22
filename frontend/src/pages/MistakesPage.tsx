import { BookX, CheckCircle2, CircleAlert, Filter, ListChecks } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useLoaderData } from 'react-router-dom'
import type { MistakeStatus, MistakeType } from '../api'
import type { MistakesRouteData } from '../routeData'

const mistakeTypeLabels: Record<MistakeType, string> = {
  concept: '概念理解',
  formula_condition: '公式条件',
  derivation: '推导步骤',
  calculation: '计算',
  question_understanding: '题意理解',
  expression: '表达',
  cannot_solve: '不会做',
  other: '其他',
}

const mistakeTypes = Object.entries(mistakeTypeLabels) as [MistakeType, string][]

export function MistakesPage() {
  const { mistakes, courses, error } = useLoaderData() as MistakesRouteData
  const [courseId, setCourseId] = useState('all')
  const [chapterId, setChapterId] = useState('all')
  const [sectionId, setSectionId] = useState('all')
  const [errorType, setErrorType] = useState<'all' | MistakeType>('all')
  const [mistakeStatus, setMistakeStatus] = useState<'all' | MistakeStatus>('all')

  const chapters = useMemo(() => courses.flatMap((course) => (
    course.chapters
      .filter(() => courseId === 'all' || course.id === Number(courseId))
      .map((chapter) => ({
        ...chapter,
        course_id: course.id,
        course_name: course.name,
      }))
  )), [courseId, courses])
  const sections = useMemo(() => chapters.flatMap((chapter) => (
    chapter.sections
      .filter(() => chapterId === 'all' || chapter.id === Number(chapterId))
      .map((section) => ({
        ...section,
        chapter_id: chapter.id,
        chapter_title: chapter.title,
        course_name: chapter.course_name,
      }))
  )), [chapterId, chapters])

  const filteredMistakes = mistakes.filter((mistake) => (
    (courseId === 'all' || mistake.course_id === Number(courseId))
    && (chapterId === 'all' || mistake.chapter_id === Number(chapterId))
    && (sectionId === 'all' || mistake.section_id === Number(sectionId))
    && (errorType === 'all' || mistake.error_type === errorType)
    && (mistakeStatus === 'all' || mistake.status === mistakeStatus)
  ))
  const unresolvedCount = filteredMistakes.filter((mistake) => mistake.status === 'unresolved').length
  const understoodCount = filteredMistakes.length - unresolvedCount
  const typeCounts = mistakeTypes
    .map(([type, label]) => ({
      type,
      label,
      count: filteredMistakes.filter((mistake) => mistake.error_type === type).length,
    }))
    .filter((item) => item.count > 0)
  const largestTypeCount = Math.max(1, ...typeCounts.map((item) => item.count))

  return (
    <main className="content content--workspace index-page mistakes-page">
      <header className="page-heading">
        <p className="eyebrow">学习复盘</p>
        <h1>错题与薄弱点</h1>
        <p className="page-summary">按课程结构、错误类型和解决状态回看已经整理的问题。</p>
      </header>

      {error && <p className="error-banner" role="alert">{error}</p>}

      <section className="index-filter-panel" aria-label="错题筛选">
        <div className="section-heading"><Filter size={17} aria-hidden="true" /><h2>筛选范围</h2></div>
        <div className="index-filter-grid">
          <label>课程<select value={courseId} onChange={(event) => { setCourseId(event.target.value); setChapterId('all'); setSectionId('all') }}><option value="all">全部课程</option>{courses.map((course) => <option value={course.id} key={course.id}>{course.name}</option>)}</select></label>
          <label>章节<select value={chapterId} onChange={(event) => { setChapterId(event.target.value); setSectionId('all') }}><option value="all">全部章节</option>{chapters.map((chapter) => <option value={chapter.id} key={chapter.id}>{courseId === 'all' ? `${chapter.course_name} / ${chapter.title}` : chapter.title}</option>)}</select></label>
          <label>小节<select value={sectionId} onChange={(event) => setSectionId(event.target.value)}><option value="all">全部小节</option>{sections.map((section) => <option value={section.id} key={section.id}>{chapterId !== 'all' ? section.title : courseId === 'all' ? `${section.course_name} / ${section.chapter_title} / ${section.title}` : `${section.chapter_title} / ${section.title}`}</option>)}</select></label>
          <label>错误类型<select value={errorType} onChange={(event) => setErrorType(event.target.value as 'all' | MistakeType)}><option value="all">全部类型</option>{mistakeTypes.map(([type, label]) => <option value={type} key={type}>{label}</option>)}</select></label>
          <label>解决状态<select value={mistakeStatus} onChange={(event) => setMistakeStatus(event.target.value as 'all' | MistakeStatus)}><option value="all">全部状态</option><option value="unresolved">未解决</option><option value="understood">已理解</option></select></label>
        </div>
      </section>

      <section className="mistake-overview" aria-labelledby="mistake-overview-title">
        <div className="section-heading"><ListChecks size={17} aria-hidden="true" /><h2 id="mistake-overview-title">当前汇总</h2></div>
        <div className="overview-stats">
          <div><span>当前错题</span><strong>{filteredMistakes.length}</strong></div>
          <div><span>未解决</span><strong>{unresolvedCount}</strong></div>
          <div><span>已理解</span><strong>{understoodCount}</strong></div>
        </div>
        {typeCounts.length > 0 && (
          <div className="type-distribution" aria-label="错误类型分布">
            {typeCounts.map((item) => (
              <div className="type-distribution__row" key={item.type}>
                <span>{item.label}</span>
                <div className="type-distribution__track" aria-hidden="true"><span style={{ width: `${(item.count / largestTypeCount) * 100}%` }} /></div>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="index-results" aria-labelledby="mistake-results-title">
        <div className="section-heading section-heading--spaced"><BookX size={17} aria-hidden="true" /><h2 id="mistake-results-title">错题记录</h2><span className="count-label">{filteredMistakes.length} 条</span></div>
        {!error && mistakes.length === 0 && <div className="empty-state"><BookX size={22} aria-hidden="true" /><p>还没有整理过错题</p></div>}
        {mistakes.length > 0 && filteredMistakes.length === 0 && <div className="empty-state empty-state--compact"><Filter size={20} aria-hidden="true" /><p>当前筛选范围没有错题</p></div>}
        <div className="index-record-list">
          {filteredMistakes.map((mistake) => (
            <details className="index-record" key={mistake.id}>
              <summary>
                <span className="index-record__title">{mistake.original_question}</span>
                <span className="mistake-type-tag">{mistakeTypeLabels[mistake.error_type]}</span>
                <span className={`record-status record-status--${mistake.status}`}>
                  {mistake.status === 'understood' ? <CheckCircle2 size={14} aria-hidden="true" /> : <CircleAlert size={14} aria-hidden="true" />}
                  {mistake.status === 'understood' ? '已理解' : '未解决'}
                </span>
                <span className="index-record__date">{mistake.study_date}</span>
              </summary>
              <div className="index-record__body">
                <p className="record-context">{mistake.course_name} / {mistake.chapter_title} / {mistake.section_title}</p>
                <dl className="mistake-detail-grid">
                  <div><dt>错误内容</dt><dd>{mistake.error_content}</dd></div>
                  <div><dt>为什么错</dt><dd>{mistake.cause_analysis}</dd></div>
                  <div><dt>正确思路</dt><dd>{mistake.correct_approach}</dd></div>
                </dl>
                <Link className="secondary-button inline-link-button" to={`/daily-records/${mistake.daily_record_id}`}>打开学习记录</Link>
              </div>
            </details>
          ))}
        </div>
      </section>
    </main>
  )
}
