import { FileText, NotebookPen, Search, Settings } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useLoaderData, useLocation, useSearchParams } from 'react-router-dom'
import type { NotesRouteData } from '../routeData'

function noteExcerpt(content: string) {
  const plainText = content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[#>*_`[\]()-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return plainText.length > 150 ? `${plainText.slice(0, 150)}...` : plainText
}

export function NotesPage() {
  const { notes, error, vaultMissing } = useLoaderData() as NotesRouteData
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const courses = useMemo(() => Array.from(new Map(
    notes.items.map((note) => [note.course_id, note.course_name]),
  )), [notes.items])
  const query = searchParams.get('q') ?? ''
  const requestedCourseId = searchParams.get('course') ?? 'all'
  const courseId = courses.some(([id]) => String(id) === requestedCourseId) ? requestedCourseId : 'all'
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const filteredNotes = notes.items.filter((note) => (
    (courseId === 'all' || note.course_id === Number(courseId))
    && (!normalizedQuery || [
      note.course_name,
      note.chapter_title,
      note.section_title,
      note.relative_path,
      note.content,
    ].some((value) => value.toLocaleLowerCase().includes(normalizedQuery)))
  ))

  function updateSearchParam(name: 'q' | 'course', value: string) {
    const next = new URLSearchParams(searchParams)
    if (!value || value === 'all') next.delete(name)
    else next.set(name, value)
    setSearchParams(next, { replace: true })
  }

  return (
    <main className="content content--workspace index-page notes-page">
      <header className="page-heading">
        <p className="eyebrow">结构化成果</p>
        <h1>小节笔记</h1>
        <p className="page-summary">查看和搜索 Lumina 所管理的课程笔记，不扫描 Vault 中的其他目录。</p>
      </header>

      {error && !vaultMissing && <p className="error-banner" role="alert">{error}</p>}
      {vaultMissing && (
        <div className="empty-state note-configuration-state">
          <Settings size={22} aria-hidden="true" />
          <p>需要先配置 Obsidian Vault 才能读取笔记</p>
          <Link className="secondary-button inline-link-button" to="/settings">打开设置</Link>
        </div>
      )}

      {!vaultMissing && (
        <>
          <section className="note-index-toolbar" aria-label="笔记搜索">
            <label className="index-search">
              <Search size={16} aria-hidden="true" />
              <span className="sr-only">搜索小节笔记</span>
              <input type="search" value={query} placeholder="搜索课程、小节或笔记正文" onChange={(event) => updateSearchParam('q', event.target.value)} />
            </label>
            <label className="compact-select"><span className="sr-only">按课程筛选</span><select value={courseId} onChange={(event) => updateSearchParam('course', event.target.value)}><option value="all">全部课程</option>{courses.map(([id, name]) => <option value={id} key={id}>{name}</option>)}</select></label>
          </section>

          {notes.issues.length > 0 && (
            <details className="index-warning">
              <summary>{notes.issues.length} 个小节笔记暂时无法索引</summary>
              <ul>{notes.issues.map((issue) => (
                <li key={issue.section_id}>
                  <strong>{issue.course_name} / {issue.chapter_title} / {issue.section_title}</strong>
                  ：{issue.detail}
                </li>
              ))}</ul>
            </details>
          )}

          <section className="index-results" aria-labelledby="note-results-title">
            <div className="section-heading section-heading--spaced"><NotebookPen size={17} aria-hidden="true" /><h2 id="note-results-title">笔记列表</h2><span className="count-label">{filteredNotes.length} 篇</span></div>
            {!error && notes.items.length === 0 && <div className="empty-state"><FileText size={22} aria-hidden="true" /><p>还没有保存过小节笔记</p></div>}
            {notes.items.length > 0 && filteredNotes.length === 0 && <div className="empty-state empty-state--compact"><Search size={20} aria-hidden="true" /><p>没有匹配的笔记</p></div>}
            <div className="note-index-list">
              {filteredNotes.map((note) => (
                <article className="note-index-item" key={note.section_id}>
                  <div>
                    <p className="record-context">{note.course_name} / {note.chapter_title}</p>
                    <h2>{note.section_title}</h2>
                    <p className="note-path">{note.relative_path}</p>
                    <p className="note-excerpt">{noteExcerpt(note.content) || '这篇笔记目前没有正文内容。'}</p>
                  </div>
                  <Link
                    className="secondary-button inline-link-button"
                    to={`/notes/${note.section_id}${location.search}`}
                  >
                    打开笔记
                  </Link>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
