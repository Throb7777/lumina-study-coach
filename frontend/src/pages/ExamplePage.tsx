import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Circle,
  ExternalLink,
  FileText,
  Link2,
  LockKeyhole,
} from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import { MarkdownContent } from '../components/MarkdownContent'
import exampleJson from '../data/example-course.json?raw'
import { isBundledExampleVisible } from '../examplePreference'

type ExampleView = 'workflow' | 'practice' | 'note'

interface ExampleOption {
  id: string
  label: string
}

interface ExampleItem {
  position: number
  item_type: string
  difficulty: string
  stem_markdown: string
  options: ExampleOption[]
  source_refs: string[]
  response: {
    answer_markdown: string
    selected_options: string[]
    verdict: string
    feedback_markdown: string
  }
}

interface ExamplePack {
  course: {
    name: string
    description: string
    learning_goal: string
    chapter: string
    section: string
    study_date: string
  }
  materials: Array<{ type: string; title: string; description: string; href: string }>
  attribution: { text: string; license_name: string; license_url: string }
  workflow: Array<{
    number: string
    key: string
    title: string
    summary: string
    input_markdown: string
    feedback_markdown: string
  }>
  exercise: { items: ExampleItem[] }
  preview_questions: string[]
  note_markdown: string
  quality: {
    materials: number
    questions: number
    choice_questions: number
    correct: number
    incorrect: number
    source_references: number
    cross_day_handoff: boolean
  }
}

const example = JSON.parse(exampleJson) as ExamplePack

const itemTypeLabels: Record<string, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  short_answer: '概念简答',
  calculation: '计算题',
  application: '应用题',
  derivation: '推导分析',
  extension: '思维延伸',
}

const difficultyLabels: Record<string, string> = {
  basic: '基础',
  intermediate: '进阶',
  challenge: '挑战',
}

const verdictLabels: Record<string, string> = {
  correct: '正确',
  partial: '部分正确',
  incorrect: '错误',
}

function WorkflowExample() {
  return (
    <div className="example-workflow">
      <section className="example-materials" aria-labelledby="example-materials-title">
        <div className="example-section-heading">
          <div><Link2 size={18} aria-hidden="true" /><h2 id="example-materials-title">本次材料</h2></div>
          <span>{example.materials.length} 份真实公开材料</span>
        </div>
        <div className="example-material-list">
          {example.materials.map((material) => (
            <a href={material.href} target="_blank" rel="noreferrer" key={material.href}>
              <span className="example-material-type">{material.type.toUpperCase()}</span>
              <span><strong>{material.title}</strong><small>{material.description}</small></span>
              <ExternalLink size={15} aria-hidden="true" />
            </a>
          ))}
        </div>
      </section>

      <section aria-labelledby="example-flow-title">
        <div className="example-section-heading">
          <div><BookOpen size={18} aria-hidden="true" /><h2 id="example-flow-title">每日学习流程</h2></div>
          <span>6 / 6 已完成</span>
        </div>
        <div className="example-flow-list">
          {example.workflow.map((stage, index) => (
            <details className="example-flow-stage" open={index === 0} key={stage.key}>
              <summary>
                <span className="example-stage-number">{stage.number}</span>
                <span><strong>{stage.title}</strong><small>{stage.summary}</small></span>
                <span className="example-stage-status"><Check size={14} aria-hidden="true" />已完成</span>
              </summary>
              <div className="example-stage-content">
                <section>
                  <h3>{stage.key === 'study' ? '本次范围' : stage.key === 'preview' ? '今日摘要' : '学习记录'}</h3>
                  <MarkdownContent content={stage.input_markdown} />
                </section>
                {stage.feedback_markdown && (
                  <section>
                    <h3>模型反馈</h3>
                    <MarkdownContent content={stage.feedback_markdown} />
                  </section>
                )}
                {stage.key === 'preview' && (
                  <section>
                    <h3>下次思考问题</h3>
                    <ol className="example-preview-questions">
                      {example.preview_questions.map((question) => <li key={question}>{question}</li>)}
                    </ol>
                  </section>
                )}
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  )
}

function PracticeExample() {
  const [position, setPosition] = useState(1)
  const item = useMemo(
    () => example.exercise.items.find((candidate) => candidate.position === position)
      ?? example.exercise.items[0],
    [position],
  )

  return (
    <section className="example-practice" aria-labelledby="example-practice-title">
      <div className="example-section-heading">
        <div><Check size={18} aria-hidden="true" /><h2 id="example-practice-title">练习与逐题批改</h2></div>
        <span>{example.quality.correct} 题正确 · {example.quality.incorrect} 题需修正</span>
      </div>
      <div className="structured-exercise exercise-review-workspace">
        <div className="exercise-question-nav" role="navigation" aria-label="示例批改题目导航">
          {example.exercise.items.map((candidate) => (
            <button
              className={candidate.position === item.position ? 'active' : ''}
              type="button"
              title={`第 ${candidate.position} 题，${verdictLabels[candidate.response.verdict]}`}
              aria-current={candidate.position === item.position ? 'step' : undefined}
              data-verdict={candidate.response.verdict}
              key={candidate.position}
              onClick={() => setPosition(candidate.position)}
            >
              {candidate.position}
            </button>
          ))}
        </div>
        <article className="exercise-review-item">
          <header className="exercise-question-header">
            <div>
              <span>第 {item.position} / {example.exercise.items.length} 题</span>
              <strong>{itemTypeLabels[item.item_type] ?? item.item_type} · {difficultyLabels[item.difficulty] ?? item.difficulty}</strong>
            </div>
            <span className={`exercise-review-verdict exercise-review-verdict--${item.response.verdict}`}>
              {verdictLabels[item.response.verdict] ?? '已批改'}
            </span>
          </header>
          <div className="exercise-question-stem"><MarkdownContent content={item.stem_markdown} /></div>
          {item.options.length > 0 && (
            <div className="exercise-review-options" aria-label="本题选项">
              {item.options.map((option) => {
                const selected = item.response.selected_options.includes(option.id)
                return (
                  <div data-selected={selected} key={option.id}>
                    {selected ? <Check size={17} aria-hidden="true" /> : <Circle size={17} aria-hidden="true" />}
                    <strong>{option.id}</strong>
                    <MarkdownContent content={option.label} />
                  </div>
                )
              })}
            </div>
          )}
          <section className="exercise-review-answer">
            <div><strong>示例作答</strong><span>只读</span></div>
            <MarkdownContent content={item.response.answer_markdown || `选择：${item.response.selected_options.join('、')}`} />
          </section>
          <section className={`exercise-item-feedback exercise-item-feedback--${item.response.verdict}`}>
            <div><strong>本题反馈</strong><span>{verdictLabels[item.response.verdict]}</span></div>
            <MarkdownContent content={item.response.feedback_markdown} />
          </section>
          {item.source_refs.length > 0 && <p className="exercise-source">依据：{item.source_refs.join('；')}</p>}
          <div className="exercise-question-footer">
            <button className="secondary-button" type="button" disabled={item.position === 1} onClick={() => setPosition(item.position - 1)}><ChevronLeft size={16} />上一题</button>
            <span>逐题复核 {item.position}/{example.exercise.items.length}</span>
            <button className="secondary-button" type="button" disabled={item.position === example.exercise.items.length} onClick={() => setPosition(item.position + 1)}>下一题<ChevronRight size={16} /></button>
          </div>
        </article>
      </div>
    </section>
  )
}

function NoteExample() {
  return (
    <section className="example-note" aria-labelledby="example-note-title">
      <div className="example-section-heading">
        <div><FileText size={18} aria-hidden="true" /><h2 id="example-note-title">小节笔记</h2></div>
        <span>GPT 初稿 · Gemini 润色 · Obsidian Markdown</span>
      </div>
      <div className="example-note-reader"><MarkdownContent content={example.note_markdown} /></div>
    </section>
  )
}

export function ExamplePage() {
  const [view, setView] = useState<ExampleView>('workflow')
  if (!isBundledExampleVisible()) return <Navigate to="/courses" replace />

  return (
    <main className="content content--workspace example-page">
      <Link className="example-back" to="/courses"><ArrowLeft size={16} />返回课程</Link>
      <header className="example-heading">
        <div>
          <div className="example-label"><LockKeyhole size={14} aria-hidden="true" />只读完整示例</div>
          <h1>{example.course.name}</h1>
          <p>{example.course.description}</p>
        </div>
        <dl className="example-quality">
          <div><dt>材料</dt><dd>{example.quality.materials}</dd></div>
          <div><dt>练习</dt><dd>{example.quality.questions}</dd></div>
          <div><dt>引用</dt><dd>{example.quality.source_references}</dd></div>
        </dl>
      </header>
      <div className="example-course-path">
        <span>{example.course.chapter}</span><span>{example.course.section}</span><span>{example.course.study_date}</span>
      </div>
      <nav className="example-tabs" aria-label="示例内容" role="tablist">
        {([
          ['workflow', '完整流程'],
          ['practice', '练习与批改'],
          ['note', '小节笔记'],
        ] as Array<[ExampleView, string]>).map(([key, label]) => (
          <button type="button" role="tab" aria-selected={view === key} key={key} onClick={() => setView(key)}>{label}</button>
        ))}
      </nav>

      {view === 'workflow' && <WorkflowExample />}
      {view === 'practice' && <PracticeExample />}
      {view === 'note' && <NoteExample />}

      <footer className="example-attribution">
        <span>{example.attribution.text}</span>
        <a href={example.attribution.license_url} target="_blank" rel="noreferrer">{example.attribution.license_name}<ExternalLink size={13} /></a>
        <span>示例不写入学习数据，也不会调用模型。</span>
      </footer>
    </main>
  )
}
