import { useState } from 'react'
import type { FormEvent } from 'react'
import { Brain, RefreshCw, Save } from 'lucide-react'
import { useLoaderData } from 'react-router-dom'
import { api } from '../api'
import type { ChapterMemory, CourseLearningMemory, CourseMemoryPayload, SectionMemory } from '../api'
import { PageBackBar } from '../components/PageBackBar'
import type { CourseMemoryRouteData } from '../routeData'
import { useTransientNotice } from '../useTransientNotice'

const memoryFields: Array<{
  key: keyof CourseMemoryPayload
  title: string
  description: string
}> = [
  { key: 'overview', title: '个人课程概览', description: '你希望每次生成都知道的课程定位与学习边界' },
  { key: 'core_concepts', title: '核心概念', description: '跨小节持续使用的关键概念' },
  { key: 'key_methods', title: '关键方法', description: '反复出现的推导、计算与分析方法' },
  { key: 'unresolved_questions', title: '未解决问题', description: '后续学习需要继续确认的内容' },
  { key: 'error_patterns', title: '常见错误', description: '多次出现的理解或作答偏差' },
]

export function CourseMemoryPage() {
  const routeData = useLoaderData() as CourseMemoryRouteData
  const [memory, setMemory] = useState<CourseLearningMemory | null>(routeData.memory)
  const [busySectionId, setBusySectionId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(routeData.error)
  const [notice, setNotice] = useTransientNotice()

  if (!routeData.course || !memory) {
    return (
      <main className="context-page">
        <PageBackBar ariaLabel="学习记忆导航" to="/courses" />
        <div className="content content--wide context-page__content">
          <p className="error-banner" role="alert">
            {routeData.notFound ? '课程不存在' : error}
          </p>
        </div>
      </main>
    )
  }

  const sectionMeta = new Map(
    routeData.course.chapters.flatMap((chapter) => (
      chapter.sections.map((section) => [
        section.id,
        { chapter: chapter.title, section: section.title, status: section.status },
      ] as const)
    )),
  )
  const chapterMeta = new Map(
    routeData.course.chapters.map((chapter) => [chapter.id, chapter.title] as const),
  )

  async function saveCourseMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!memory) return
    setSaving(true)
    setError('')
    try {
      const data = new FormData(event.currentTarget)
      const payload = Object.fromEntries(
        memoryFields.map(({ key }) => [key, String(data.get(key) ?? '')]),
      ) as CourseMemoryPayload
      const courseMemory = await api.updateCourseLearningMemory(memory.course.course_id, payload)
      setMemory({ ...memory, course: courseMemory })
      setNotice('课程学习记忆已保存')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '保存学习记忆失败')
    } finally {
      setSaving(false)
    }
  }

  async function refreshSection(sectionId: number) {
    if (!memory) return
    setBusySectionId(sectionId)
    setError('')
    try {
      await api.refreshSectionLearningMemory(sectionId)
      setMemory(await api.getCourseLearningMemory(memory.course.course_id))
      setNotice('小节与章节学习记忆已更新')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '更新小节学习记忆失败')
    } finally {
      setBusySectionId(null)
    }
  }

  function memorySummary(item: SectionMemory) {
    return item.summary || item.core_concepts || item.key_methods
  }

  function chapterMemorySummary(item: ChapterMemory) {
    return item.summary || item.core_concepts || item.key_methods
  }

  return (
    <main className="context-page">
      <PageBackBar ariaLabel="学习记忆导航" to={`/courses/${routeData.course.id}`} />
      <div className="content content--wide context-page__content memory-page">
        <header className="page-heading">
          <p className="eyebrow">课程上下文</p>
          <h1>{routeData.course.name} · 学习记忆</h1>
          <p className="page-summary">生成评阅、练习和笔记时自动读取。课程汇总可手动调整，小节记忆由已保存的学习记录重新整理。</p>
        </header>
        {error && <p className="error-banner" role="alert">{error}</p>}
        {notice && <p className="notice-banner" role="status">{notice}</p>}

        <section className="memory-section" aria-labelledby="course-memory-title">
          <div className="section-heading section-heading--spaced">
            <div>
              <h2 id="course-memory-title">课程级记忆</h2>
              <p>作为每次新会话的稳定背景，不等同于聊天历史。</p>
            </div>
            <Brain size={20} aria-hidden="true" />
          </div>
          <form className="memory-form" onSubmit={saveCourseMemory}>
            {memoryFields.map((field) => (
              <label key={field.key}>
                <span className="field-label-copy">
                  <strong>{field.title}</strong>
                  <span>{field.description}</span>
                </span>
                <textarea name={field.key} rows={4} defaultValue={memory.course[field.key]} />
              </label>
            ))}
            <div className="form-actions">
              <button className="primary-button" type="submit" disabled={saving}>
                <Save size={15} />{saving ? '保存中' : '保存课程记忆'}
              </button>
            </div>
          </form>
          <div className="generated-outline" aria-label="自动课程脉络">
            <span className="field-label-copy">
              <strong>自动课程脉络</strong>
              <span>由章节和小节记忆生成，不会覆盖上面的个人课程概览。</span>
            </span>
            <pre>{memory.course.generated_outline || '完成小节记忆整理后在这里形成课程脉络。'}</pre>
          </div>
        </section>

        <section className="memory-section" aria-labelledby="chapter-memory-title">
          <div className="section-heading section-heading--spaced">
            <div>
              <h2 id="chapter-memory-title">章节记忆</h2>
              <p>承接同章各小节的概念关系、方法和未解决问题。</p>
            </div>
            <span className="count-label">{(memory.chapters ?? []).length} 个章节</span>
          </div>
          <div className="section-memory-list">
            {(memory.chapters ?? []).map((item) => (
              <article className="section-memory-item" key={item.chapter_id}>
                <header>
                  <span>
                    <strong>{chapterMeta.get(item.chapter_id) ?? `章节 ${item.chapter_id}`}</strong>
                    <small>{chapterMemorySummary(item) || '尚未生成'}</small>
                  </span>
                </header>
                <details>
                  <summary>查看记忆内容</summary>
                  <dl className="section-memory-detail">
                    <div><dt>摘要</dt><dd>{item.summary || '暂无'}</dd></div>
                    <div><dt>核心概念</dt><dd>{item.core_concepts || '暂无'}</dd></div>
                    <div><dt>关键方法</dt><dd>{item.key_methods || '暂无'}</dd></div>
                    <div><dt>未解决问题</dt><dd>{item.unresolved_questions || '暂无'}</dd></div>
                    <div><dt>常见错误</dt><dd>{item.error_patterns || '暂无'}</dd></div>
                  </dl>
                </details>
              </article>
            ))}
          </div>
        </section>

        <section className="memory-section" aria-labelledby="section-memory-title">
          <div className="section-heading section-heading--spaced">
            <div>
              <h2 id="section-memory-title">小节记忆</h2>
              <p>每小节独立保存，完成学习后可重新生成。</p>
            </div>
            <span className="count-label">{memory.sections.length} 个小节</span>
          </div>
          <div className="section-memory-list">
            {memory.sections.map((item) => {
              const meta = sectionMeta.get(item.section_id)
              return (
                <article className="section-memory-item" key={item.section_id}>
                  <header>
                    <span>
                      <strong>{meta?.section ?? `小节 ${item.section_id}`}</strong>
                      <small>{meta?.chapter}{memorySummary(item) ? ` · ${memorySummary(item)}` : ' · 尚未生成'}</small>
                    </span>
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={busySectionId !== null}
                      onClick={(event) => {
                        event.preventDefault()
                        void refreshSection(item.section_id)
                      }}
                    >
                      <RefreshCw size={15} />
                      {busySectionId === item.section_id ? '整理中' : '重新整理'}
                    </button>
                  </header>
                  <details>
                    <summary>查看记忆内容</summary>
                    <dl className="section-memory-detail">
                      <div><dt>摘要</dt><dd>{item.summary || '暂无'}</dd></div>
                      <div><dt>核心概念</dt><dd>{item.core_concepts || '暂无'}</dd></div>
                      <div><dt>关键方法</dt><dd>{item.key_methods || '暂无'}</dd></div>
                      <div><dt>未解决问题</dt><dd>{item.unresolved_questions || '暂无'}</dd></div>
                      <div><dt>常见错误</dt><dd>{item.error_patterns || '暂无'}</dd></div>
                    </dl>
                  </details>
                </article>
              )
            })}
          </div>
        </section>
      </div>
    </main>
  )
}
