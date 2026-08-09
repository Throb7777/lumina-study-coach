import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  Clipboard,
  FileText,
  Paperclip,
  Plus,
  Save,
  SkipForward,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { Link, useLoaderData } from 'react-router-dom'
import { api } from '../api'
import type {
  AiRun,
  DailyRecord,
  DailyRecordContent,
  DailyRecordMaterial,
  Exercise,
  ExerciseItem,
  GuidedReflection,
  GuidedReflectionKind,
  Mistake,
  MistakePayload,
  MistakeType,
  WorkflowNode,
  WorkflowNodeStatus,
  AiSourceReference,
} from '../api'
import { AiTaskStatus } from '../components/AiTaskStatus'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { TwoStepDeleteDialog } from '../components/TwoStepDeleteDialog'
import { DraftStatus } from '../components/DraftStatus'
import { EditableMarkdown } from '../components/EditableMarkdown'
import { IncompleteCompletionDialog } from '../components/IncompleteCompletionDialog'
import { MaterialLibrary } from '../components/MaterialLibrary'
import { MarkdownContent } from '../components/MarkdownContent'
import type { MaterialScopeOption } from '../components/MaterialLibrary'
import { PageBackBar } from '../components/PageBackBar'
import { UnsavedChangesGuard } from '../components/UnsavedChangesGuard'
import {
  clearFormDraft,
  restoreFormDraft,
  writeFormDraft,
} from '../draftStorage'
import { formIsDirty, updateFormBaseline } from '../formState'
import type { DailyRecordRouteData } from '../routeData'
import { useTransientNotice } from '../useTransientNotice'
import {
  aiRunPhase,
  aiTaskRunKeys,
  completionFields,
  exerciseDifficultyLabels,
  exerciseTypeLabels,
  exerciseVerdictLabels,
  firstPendingNodeId,
  incompleteFields,
  mistakeTypeLabels,
  nodeDescriptions,
  nodeTitles,
  sourceTaskLabels,
  statusLabels,
} from './dailyRecordSupport'
import type {
  ActiveAiTask,
  AiTaskFeedback,
  AiTaskKey,
  MistakeDraftDiscardAction,
  PendingCompletionAction,
} from './dailyRecordSupport'

function FieldLabel({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <label>
      <span className="field-label-copy"><strong>{title}</strong><span>{description}</span></span>
      {children}
    </label>
  )
}

function GuidedReflectionPanel({
  reflection,
  busy,
  taskState,
  completeLabel,
  onSubmit,
  onRegenerate,
  onComplete,
}: {
  reflection: GuidedReflection
  busy: boolean
  taskState: ReactNode
  completeLabel: string
  onSubmit: (event: FormEvent<HTMLFormElement>, reflection: GuidedReflection) => void
  onRegenerate: () => void
  onComplete: () => void
}) {
  const formKey = reflection.questions
    .map((question) => `${question.id}:${question.question_markdown}`)
    .join('|')
  return (
    <section className="guided-reflection" aria-label="AI 定向问题">
      <header className="guided-reflection__heading">
        <div>
          <strong>AI 定向追问</strong>
          <span>按顺序回答 3 个具体问题，再获取综合反馈</span>
        </div>
        <button className="text-button" type="button" disabled={busy} onClick={onRegenerate}>
          <Sparkles size={15} />重新生成问题
        </button>
      </header>
      {taskState}
      <form
        key={formKey}
        className="guided-reflection__form"
        data-dirty-key={`guided-reflection-${reflection.id}`}
        data-save-kind="guided-reflection"
        data-entity-id={reflection.id}
        onSubmit={(event) => onSubmit(event, reflection)}
      >
        {reflection.questions.map((question, index) => {
          const review = (reflection.reviews ?? []).find((item) => item.id === question.id)
          return (
          <label className="guided-question" key={question.id}>
            <span className="guided-question__meta">
              <strong>问题 {index + 1}</strong>
              <small>{question.focus}</small>
            </span>
            <MarkdownContent content={question.question_markdown} />
            <textarea
              name={`answer_${question.id}`}
              rows={5}
              defaultValue={reflection.answers[question.id] ?? ''}
              placeholder="用自己的话回答，写出判断依据或关键步骤"
              aria-label={`问题 ${index + 1} 的回答`}
            />
            {review && (
              <div className={`guided-question__review guided-question__review--${review.verdict}`}>
                <strong>{exerciseVerdictLabels[review.verdict] ?? review.verdict}</strong>
                <MarkdownContent content={review.feedback_markdown} />
              </div>
            )}
          </label>
          )
        })}
        <div className="form-actions">
          <button className="secondary-button" type="submit" disabled={busy}>
            <Save size={15} />保存回答
          </button>
          <button className="primary-button" type="submit" data-review="true" disabled={busy}>
            <Sparkles size={15} />保存并获取反馈
          </button>
        </div>
      </form>
      {((reflection.reviews ?? []).length > 0 || reflection.feedback_text) && (
        <section className="guided-reflection__feedback">
          <div><strong>综合反馈</strong><span>上方已逐题标注，下面给出整体建议</span></div>
          {reflection.feedback_text && <MarkdownContent content={reflection.feedback_text} />}
          <div className="form-actions">
            <button className="primary-button" type="button" disabled={busy} onClick={onComplete}>
              <Check size={15} />{completeLabel}
            </button>
          </div>
        </section>
      )}
    </section>
  )
}


function SourceReferences({
  references,
  materials,
}: {
  references: AiSourceReference[]
  materials: DailyRecordMaterial[]
}) {
  const available = materials.filter((material) => material.selected && material.status === 'ready')
  if (references.length === 0 && available.length === 0) return null
  const grouped = references.reduce<Map<string, AiSourceReference[]>>((result, reference) => {
    result.set(reference.task, [...(result.get(reference.task) ?? []), reference])
    return result
  }, new Map())
  return (
    <details className="source-references">
      <summary>来源依据 <span>可用 {available.length} 份 · 实际引用 {references.length} 条</span></summary>
      {references.length > 0 ? (
        <section>
          <strong>实际引用</strong>
          {[...grouped.entries()].map(([task, items]) => (
            <div key={task} className="source-reference-group">
              <span>{sourceTaskLabels[task] ?? task}</span>
              <ul>{items.map((item) => <li key={`${task}-${item.material_id}-${item.location}`}>{item.material_title} · {item.location}</li>)}</ul>
            </div>
          ))}
          <details className="source-reference-technical">
            <summary>技术信息</summary>
            <ul>{references.map((item) => (
              <li key={`technical-${item.task}-${item.material_id}-${item.location}`}>
                材料 {item.material_id}
                {item.chunk_position ? ` · 分块 ${item.chunk_position}` : ''}
                {' · '}{item.content_hash.slice(0, 12) || '无版本'}
              </li>
            ))}</ul>
          </details>
        </section>
      ) : <p>当前还没有生成结果引用材料。</p>}
      {available.length > 0 && (
        <section>
          <strong>本次可用材料</strong>
          <ul>{available.map((material) => (
            <li key={`available-${material.id}`}>
              {material.title} · {material.range_note || '完整材料'}
            </li>
          ))}</ul>
        </section>
      )}
    </details>
  )
}

function mistakePayload(form: HTMLFormElement): MistakePayload {
  const data = new FormData(form)
  const exerciseItemId = Number(data.get('exercise_item_id'))
  return {
    ...(exerciseItemId > 0 ? { exercise_item_id: exerciseItemId } : {}),
    error_content: String(data.get('error_content') ?? ''),
    error_type: String(data.get('error_type') ?? 'concept') as MistakeType,
  }
}

function MistakeFields({
  mistake,
  exerciseItem,
}: {
  mistake?: Mistake
  exerciseItem?: ExerciseItem
}) {
  const fieldId = useId().replaceAll(':', '')
  const questionTitleId = `mistake-question-title-${fieldId}`
  const answerTitleId = `mistake-answer-title-${fieldId}`
  const originalQuestion = mistake?.original_question ?? exerciseItem?.stem_markdown ?? ''
  const correctAnswer = mistake?.correct_approach ?? exerciseItem?.reference_answer_markdown ?? ''
  return (
    <div className="mistake-fields">
      {exerciseItem && <input type="hidden" name="exercise_item_id" value={exerciseItem.id} />}
      <section className="mistake-reference mistake-reference--question" aria-labelledby={questionTitleId}>
        <div><strong id={questionTitleId}>原题</strong><span>与当前批改题一致</span></div>
        <MarkdownContent content={originalQuestion || '暂无题目内容'} />
      </section>
      <section className="mistake-reference mistake-reference--answer" aria-labelledby={answerTitleId}>
        <div><strong id={answerTitleId}>正确作答</strong><span>用于对照和复习</span></div>
        <MarkdownContent content={correctAnswer || '暂无参考答案'} />
      </section>
      <div className="mistake-editor-fields">
        <FieldLabel title="错误类型" description="选择最接近的原因"><select name="error_type" defaultValue={mistake?.error_type ?? 'concept'}>{Object.entries(mistakeTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></FieldLabel>
        <FieldLabel title="注意点" description="只记下下次作答时需要特别留意的地方"><textarea required name="error_content" rows={3} defaultValue={mistake?.error_content} /></FieldLabel>
      </div>
    </div>
  )
}

function FlowNode({
  node,
  open,
  onToggle,
  children,
}: {
  node: WorkflowNode
  open: boolean
  onToggle: () => void
  children?: ReactNode
}) {
  const bodyId = `flow-node-body-${node.id}`
  const title = nodeTitles[node.node_key] ?? node.title

  return (
    <section className={`flow-node flow-node--${node.status}`}>
      <header className="flow-node-header">
        <button
          className="flow-node-toggle"
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={`${open ? '收起' : '展开'}${title}`}
          onClick={onToggle}
        >
          <span className="flow-node-index">{String(node.position).padStart(2, '0')}</span>
          <span className="flow-node-copy">
            <span className="flow-node-heading" role="heading" aria-level={2}>{title}</span>
            <span className="flow-node-description">{nodeDescriptions[node.node_key]}</span>
          </span>
          <span className="flow-node-status">
            {node.status === 'completed' ? <Check size={15} /> : <Circle size={15} />}
            {statusLabels[node.status]}
          </span>
          <ChevronDown className="flow-node-chevron" size={18} aria-hidden="true" />
        </button>
      </header>
      {children && (
        <div
          className={`flow-node-collapse${open ? ' flow-node-collapse--open' : ''}`}
          id={bodyId}
          aria-hidden={!open}
        >
          <div className="flow-node-collapse__inner">
            <div className="flow-node-body">{children}</div>
          </div>
        </div>
      )}
    </section>
  )
}

export function DailyRecordPage() {
  const routeData = useLoaderData() as DailyRecordRouteData
  const [record, setRecord] = useState<DailyRecord | null>(routeData.record)
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<number>>(() => {
    const firstPendingId = routeData.record
      ? firstPendingNodeId(routeData.record.workflow_nodes)
      : null
    return firstPendingId === null ? new Set() : new Set([firstPendingId])
  })
  const [error, setError] = useState(routeData.error)
  const [notice, setNotice] = useTransientNotice()
  const [draftRecovered, setDraftRecovered] = useState(false)
  const [busy, setBusy] = useState(false)
  const [attachmentBusyItemId, setAttachmentBusyItemId] = useState<number | null>(null)
  const [activeAiTasks, setActiveAiTasks] = useState<Partial<Record<AiTaskKey, ActiveAiTask>>>({})
  const [activeServerRuns, setActiveServerRuns] = useState<AiRun[]>(
    routeData.record?.active_ai_runs ?? [],
  )
  const [aiTaskFeedbacks, setAiTaskFeedbacks] = useState<
    Partial<Record<AiTaskKey, AiTaskFeedback & { expiresAt?: number }>>
  >({})
  const [skipConfirmOpen, setSkipConfirmOpen] = useState(false)
  const [skipError, setSkipError] = useState('')
  const [skipTrigger, setSkipTrigger] = useState<HTMLButtonElement | null>(null)
  const [newMistakeItemId, setNewMistakeItemId] = useState<number | null>(null)
  const [activeExerciseItemPosition, setActiveExerciseItemPosition] = useState(1)
  const [activeReviewItemPosition, setActiveReviewItemPosition] = useState(1)
  const [mistakeDraftDiscard, setMistakeDraftDiscard] = useState<MistakeDraftDiscardAction | null>(null)
  const [mistakeToDelete, setMistakeToDelete] = useState<Mistake | null>(null)
  const [mistakeDeleteError, setMistakeDeleteError] = useState('')
  const [mistakeDeleteTrigger, setMistakeDeleteTrigger] = useState<HTMLButtonElement | null>(null)
  const [legacyExerciseToDelete, setLegacyExerciseToDelete] = useState<Exercise | null>(null)
  const [legacyExerciseDeleteError, setLegacyExerciseDeleteError] = useState('')
  const [legacyExerciseDeleteTrigger, setLegacyExerciseDeleteTrigger] = useState<HTMLButtonElement | null>(null)
  const [pendingCompletion, setPendingCompletion] = useState<PendingCompletionAction | null>(null)
  const [completionError, setCompletionError] = useState('')
  const [dirtyFormKeys, setDirtyFormKeys] = useState<Set<string>>(new Set())
  const pageRef = useRef<HTMLElement>(null)
  const draftFormSignature = record
    ? [
        record.id,
        record.ai_interactions.map((item) => item.id).join(','),
        (record.guided_reflections ?? []).map((item) => `${item.id}:${item.questions.map((question) => question.question_markdown).join('.')}`).join(','),
        record.exercises.map((item) => `${item.id}:${(item.items ?? []).map((question) => question.id).join('.')}:${item.mistakes.map((mistake) => mistake.id).join('.')}`).join(','),
        record.preview_question_set?.id ?? '',
        (record.materials ?? []).map((material) => material.id).join(','),
        newMistakeItemId ?? '',
      ].join('|')
    : ''

  function formDraftKey(key: string) {
    return `daily-record-${record?.id ?? 'unknown'}-${key}`
  }

  async function refreshSourceReferences() {
    if (!record || (record.materials ?? []).length === 0) return
    const latest = await api.getDailyRecord(record.id)
    setRecord((current) => current ? { ...current, ai_source_refs: latest.ai_source_refs } : current)
  }

  function startAiTask(task: ActiveAiTask) {
    setActiveAiTasks((current) => ({ ...current, [task.key]: task }))
    setAiTaskFeedbacks((current) => {
      const next = { ...current }
      delete next[task.key]
      return next
    })
  }

  function finishAiTask(key: AiTaskKey) {
    setActiveAiTasks((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  function showAiTaskFeedback(feedback: AiTaskFeedback) {
    setAiTaskFeedbacks((current) => ({
      ...current,
      [feedback.key]: {
        ...feedback,
        expiresAt: feedback.tone === 'success' ? Date.now() + 3000 : undefined,
      },
    }))
  }

  function isAiTaskActive(key: AiTaskKey) {
    return Boolean(activeAiTasks[key])
  }

  const activeAiTaskCount = Object.keys(activeAiTasks).length
  const activeServerRunIds = activeServerRuns.map((run) => run.id).join(',')
  const recordId = record?.id
  useEffect(() => {
    if (!recordId || (activeAiTaskCount === 0 && !activeServerRunIds)) return
    let disposed = false
    let timer = 0
    const controller = new AbortController()
    const poll = async () => {
      try {
        const runs = await api.listAiRuns(
          { daily_record_id: recordId },
          true,
          controller.signal,
        )
        if (disposed) return
        setActiveServerRuns(runs)
        if (runs.length > 0 || activeAiTaskCount > 0) timer = window.setTimeout(poll, 1500)
      } catch {
        if (!disposed && (activeServerRunIds || activeAiTaskCount > 0)) {
          timer = window.setTimeout(poll, 5000)
        }
      }
    }
    timer = window.setTimeout(poll, activeAiTaskCount > 0 ? 500 : 1500)
    return () => {
      disposed = true
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [recordId, activeAiTaskCount, activeServerRunIds])

  async function cancelActiveAiTask(run: AiRun) {
    try {
      await api.cancelAiRun(run.id)
      setActiveServerRuns((current) => current.filter((item) => item.id !== run.id))
      const taskKey = (Object.keys(aiTaskRunKeys) as AiTaskKey[])
        .find((key) => aiTaskRunKeys[key] === run.task)
      if (taskKey) finishAiTask(taskKey)
      setNotice('生成任务已取消，可以从原操作重新生成')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '取消生成失败')
    }
  }

  useEffect(() => {
    const timers = Object.entries(aiTaskFeedbacks).flatMap(([key, feedback]) => {
      if (!feedback?.expiresAt) return []
      const delay = Math.max(0, feedback.expiresAt - Date.now())
      return [window.setTimeout(() => {
        setAiTaskFeedbacks((current) => {
          const currentFeedback = current[key as AiTaskKey]
          if (currentFeedback?.expiresAt !== feedback.expiresAt) return current
          const next = { ...current }
          delete next[key as AiTaskKey]
          return next
        })
      }, delay)]
    })
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [aiTaskFeedbacks])

  useEffect(() => {
    if (!record || !pageRef.current) return
    const restoredKeys: string[] = []
    pageRef.current.querySelectorAll<HTMLFormElement>('form[data-dirty-key]').forEach((form) => {
      const key = form.dataset.dirtyKey
      if (key && restoreFormDraft(formDraftKey(key), form) && formIsDirty(form)) restoredKeys.push(key)
    })
    if (restoredKeys.length === 0) return
    const timer = window.setTimeout(() => {
      setDirtyFormKeys((currentKeys) => {
        if (restoredKeys.every((key) => currentKeys.has(key))) return currentKeys
        return new Set([...currentKeys, ...restoredKeys])
      })
      setDraftRecovered(true)
    }, 0)
    return () => window.clearTimeout(timer)
    // The signature changes only when draft-bearing forms are added or replaced.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftFormSignature])

  function updateDirtyForm(event: FormEvent<HTMLElement>) {
    const target = event.target
    if (!(target instanceof Element)) return
    const form = target.closest<HTMLFormElement>('form[data-dirty-key]')
    const key = form?.dataset.dirtyKey
    if (!form || !key) return
    const dirty = formIsDirty(form)
    if (dirty) writeFormDraft(formDraftKey(key), form)
    else clearFormDraft(formDraftKey(key))
    setDirtyFormKeys((currentKeys) => {
      const nextKeys = new Set(currentKeys)
      if (dirty) nextKeys.add(key)
      else nextKeys.delete(key)
      return nextKeys
    })
  }

  function markFormSaved(form: HTMLFormElement) {
    updateFormBaseline(form)
    const key = form.dataset.dirtyKey
    if (!key) return
    clearFormDraft(formDraftKey(key))
    setDirtyFormKeys((currentKeys) => {
      const nextKeys = new Set(currentKeys)
      nextKeys.delete(key)
      return nextKeys
    })
  }

  function clearDirtyFormKey(key: string) {
    clearFormDraft(formDraftKey(key))
    setDirtyFormKeys((currentKeys) => {
      const nextKeys = new Set(currentKeys)
      nextKeys.delete(key)
      return nextKeys
    })
  }

  function requestMistakeDraftState(nextItemId: number | null, trigger: HTMLButtonElement) {
    if (newMistakeItemId === null) {
      setNewMistakeItemId(nextItemId)
      return
    }
    const currentKey = `mistake-new-${newMistakeItemId}`
    if (dirtyFormKeys.has(currentKey)) {
      setMistakeDraftDiscard({
        currentItemId: newMistakeItemId,
        nextItemId,
        trigger,
      })
      return
    }
    clearDirtyFormKey(currentKey)
    setNewMistakeItemId(nextItemId)
  }

  function discardMistakeDraft() {
    if (!mistakeDraftDiscard) return
    clearDirtyFormKey(`mistake-new-${mistakeDraftDiscard.currentItemId}`)
    setNewMistakeItemId(mistakeDraftDiscard.nextItemId)
    setMistakeDraftDiscard(null)
  }

  async function saveDirtyForm(form: HTMLFormElement) {
    if (!record) throw new Error('当前学习记录不可保存')
    if (!form.reportValidity()) throw new Error('请先完整填写当前表单中的必填内容')
    const data = new FormData(form)
    const id = Number(form.dataset.entityId)

    switch (form.dataset.saveKind) {
      case 'content': {
        const payload = Object.fromEntries(
          Array.from(data.entries()).map(([key, value]) => [key, String(value)]),
        ) as Partial<DailyRecordContent>
        await api.updateDailyRecord(record.id, payload)
        return
      }
      case 'interaction':
        await api.updateAiInteraction(id, String(data.get('feedback_text') ?? ''))
        return
      case 'guided-reflection': {
        const reflection = (record.guided_reflections ?? []).find((item) => item.id === id)
        if (!reflection) throw new Error('定向问题记录不存在')
        await api.updateGuidedReflectionAnswers(id, Object.fromEntries(
          reflection.questions.map((question) => [
            question.id,
            String(data.get(`answer_${question.id}`) ?? ''),
          ]),
        ))
        return
      }
      case 'exercise':
        await api.updateExercise(id, {
          ai_questions: String(data.get('ai_questions') ?? ''),
          user_answers: String(data.get('user_answers') ?? ''),
        })
        return
      case 'exercise-feedback':
        await api.updateExercise(id, { ai_feedback: String(data.get('ai_feedback') ?? '') })
        return
      case 'exercise-response':
        await api.updateExerciseResponse(id, {
          answer_markdown: String(data.get('answer_markdown') ?? ''),
          selected_options: data.getAll('selected_options').map(String),
        })
        return
      case 'mistake-create':
        await api.createMistake(id, mistakePayload(form))
        return
      case 'mistake-update':
        await api.updateMistake(id, mistakePayload(form))
        return
      case 'materials': {
        let updated = record
        for (const material of record.materials ?? []) {
          updated = await api.updateDailyRecordMaterial(
            record.id,
            material.id,
            data.get(`material_${material.id}_selected`) === 'on',
            String(data.get(`material_${material.id}_range`) ?? ''),
          )
        }
        setRecord(updated)
        return
      }
      default:
        throw new Error('存在无法识别的未保存内容')
    }
  }

  async function saveAllDirtyForms() {
    if (!record) return
    setBusy(true)
    setError('')
    try {
      const forms = Array.from(document.querySelectorAll<HTMLFormElement>('form[data-dirty-key]'))
      for (const key of dirtyFormKeys) {
        const form = forms.find((item) => item.dataset.dirtyKey === key)
        if (!form) throw new Error('有一处未保存内容已关闭，请返回检查后重试')
        await saveDirtyForm(form)
        markFormSaved(form)
      }
      setNotice('未保存的学习内容已保存')
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : '保存学习内容失败'
      setError(message)
      try {
        setRecord(await api.getDailyRecord(record.id))
      } catch {
        // Keep the current editor values when refreshing saved state also fails.
      }
      throw new Error(message, { cause: saveError })
    } finally {
      setBusy(false)
    }
  }

  function nodeByKey(key: string): WorkflowNode {
    const node = record?.workflow_nodes.find((item) => item.node_key === key)
    if (!node) throw new Error(`Missing workflow node: ${key}`)
    return node
  }

  function replaceNode(current: DailyRecord, updatedNode: WorkflowNode): DailyRecord {
    return {
      ...current,
      workflow_nodes: current.workflow_nodes.map((node) =>
        node.id === updatedNode.id ? updatedNode : node
      ),
    }
  }

  function applyUpdatedNode(baseRecord: DailyRecord, updatedNode: WorkflowNode) {
    const updatedRecord = replaceNode(baseRecord, updatedNode)
    setRecord(updatedRecord)
    setExpandedNodeIds((currentIds) => {
      const nextIds = new Set(currentIds)
      if (updatedNode.status === 'pending') {
        nextIds.add(updatedNode.id)
        return nextIds
      }

      nextIds.delete(updatedNode.id)
      const nextPendingId = firstPendingNodeId(updatedRecord.workflow_nodes, updatedNode.position)
      if (nextPendingId !== null) nextIds.add(nextPendingId)
      return nextIds
    })
  }

  function revealNode(baseRecord: DailyRecord, nodeKey: string) {
    const node = baseRecord.workflow_nodes.find((item) => item.node_key === nodeKey)
    setRecord(baseRecord)
    if (!node) return
    setExpandedNodeIds((currentIds) => new Set([...currentIds, node.id]))
  }

  function flowNodeProps(key: string) {
    const node = nodeByKey(key)
    return {
      node,
      open: expandedNodeIds.has(node.id),
      onToggle: () => setExpandedNodeIds((currentIds) => {
        const nextIds = new Set(currentIds)
        if (nextIds.has(node.id)) nextIds.delete(node.id)
        else nextIds.add(node.id)
        return nextIds
      }),
    }
  }

  async function setNodeStatus(
    key: string,
    status: WorkflowNodeStatus,
    baseRecord = record,
    confirmSkip = false,
  ) {
    if (!baseRecord) return
    const node = baseRecord.workflow_nodes.find((item) => item.node_key === key)
    if (!node) return
    const updatedNode = await api.updateWorkflowNode(node.id, status, confirmSkip)
    applyUpdatedNode(baseRecord, updatedNode)
  }

  function requestIncompleteCompletion(
    form: HTMLFormElement,
    submitter: HTMLElement | null,
    fields: Array<[name: string, label: string]>,
    onConfirm: () => Promise<string | null>,
    confirmLabel = '仍然完成',
  ) {
    const incompleteLabels = incompleteFields(form, fields)
    if (incompleteLabels.length === 0 || !submitter) return false
    setError('')
    setCompletionError('')
    setPendingCompletion({ confirmLabel, incompleteLabels, onConfirm, trigger: submitter })
    return true
  }

  async function confirmPendingCompletion() {
    if (!pendingCompletion) return
    setCompletionError('')
    const completionFailure = await pendingCompletion.onConfirm()
    if (completionFailure) {
      setCompletionError(completionFailure)
      return
    }
    setPendingCompletion(null)
  }

  async function persistContent(form: HTMLFormElement, nodeKey: string, complete: boolean) {
    if (!record) return '当前学习记录不可保存'
    const payload = Object.fromEntries(
      Array.from(new FormData(form).entries()).map(([key, value]) => [
        key,
        String(value),
      ]),
    ) as Partial<DailyRecordContent>
    setBusy(true)
    setError('')
    try {
      const updated = await api.updateDailyRecord(record.id, payload)
      setRecord(updated)
      if (complete) await setNodeStatus(nodeKey, 'completed', updated)
      markFormSaved(form)
      setNotice(complete ? '内容已保存，节点已完成' : '内容已保存')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存失败'
      setError(message)
      return message
    } finally {
      setBusy(false)
    }
  }

  async function saveContent(event: FormEvent<HTMLFormElement>, nodeKey: string) {
    event.preventDefault()
    const form = event.currentTarget
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null
    const complete = submitter?.dataset.complete === 'true'
    if (
      complete
      && requestIncompleteCompletion(
        form,
        submitter,
        completionFields[nodeKey],
        () => persistContent(form, nodeKey, true),
      )
    ) return
    await persistContent(form, nodeKey, complete)
  }

  async function saveMaterialSelections(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    setBusy(true)
    setError('')
    try {
      await saveDirtyForm(form)
      markFormSaved(form)
      setNotice('材料选择已保存')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '保存材料选择失败')
    } finally {
      setBusy(false)
    }
  }

  function replaceGuidedReflection(updated: GuidedReflection) {
    setRecord((current) => current ? {
      ...current,
      guided_reflections: [
        ...(current.guided_reflections ?? []).filter((item) => item.id !== updated.id),
        updated,
      ],
    } : current)
  }

  async function generateGuidedQuestions(kind: GuidedReflectionKind) {
    if (!record) return
    const taskKey = kind === 'recall' ? 'recall_questions' : 'reconstruction_questions'
    startAiTask({
      key: taskKey,
      label: kind === 'recall' ? '正在生成回顾问题' : '正在生成重构问题',
    })
    setError('')
    setNotice('')
    try {
      const existing = (record.guided_reflections ?? []).find((item) => item.kind === kind)
      if (existing) clearDirtyFormKey(`guided-reflection-${existing.id}`)
      replaceGuidedReflection(await api.generateGuidedReflectionQuestions(record.id, kind))
      await refreshSourceReferences()
      showAiTaskFeedback({ key: taskKey, message: '3 个定向问题已生成', tone: 'success' })
    } catch (requestError) {
      showAiTaskFeedback({
        key: taskKey,
        message: requestError instanceof Error ? requestError.message : '生成定向问题失败',
        tone: 'error',
      })
    } finally {
      finishAiTask(taskKey)
    }
  }

  async function regenerateGuidedQuestions(
    kind: GuidedReflectionKind,
    nodeKey: 'recall' | 'reconstruct',
  ) {
    const seedForm = document.querySelector<HTMLFormElement>(
      `form[data-dirty-key="content-${nodeKey}"]`,
    )
    if (seedForm && formIsDirty(seedForm) && await persistContent(seedForm, nodeKey, false)) {
      return
    }
    await generateGuidedQuestions(kind)
  }

  async function saveReflectionSeed(
    event: FormEvent<HTMLFormElement>,
    nodeKey: 'recall' | 'reconstruct',
    kind: GuidedReflectionKind,
  ) {
    event.preventDefault()
    const form = event.currentTarget
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null
    if (submitter?.dataset.generate === 'true') {
      if (await persistContent(form, nodeKey, false)) return
      await generateGuidedQuestions(kind)
      return
    }
    const complete = submitter?.dataset.complete === 'true'
    if (
      complete
      && requestIncompleteCompletion(
        form,
        submitter,
        completionFields[nodeKey],
        () => persistContent(form, nodeKey, true),
      )
    ) return
    await persistContent(form, nodeKey, complete)
  }

  async function saveGuidedReflection(
    event: FormEvent<HTMLFormElement>,
    reflection: GuidedReflection,
  ) {
    event.preventDefault()
    const form = event.currentTarget
    const shouldReview = (
      (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null
    )?.dataset.review === 'true'
    const answers = Object.fromEntries(reflection.questions.map((question) => [
      question.id,
      String(new FormData(form).get(`answer_${question.id}`) ?? ''),
    ]))
    const reviewTask = reflection.kind === 'recall' ? 'recall_review' : 'reconstruction_review'
    setError('')
    try {
      setBusy(true)
      const saved = await api.updateGuidedReflectionAnswers(reflection.id, answers)
      replaceGuidedReflection(saved)
      markFormSaved(form)
      setBusy(false)
      if (!shouldReview) {
        setNotice('3 个回答已保存')
        return
      }
      startAiTask({
        key: reviewTask,
        label: reflection.kind === 'recall' ? '正在逐题评阅闭卷回顾' : '正在逐题检查主动重构',
      })
      replaceGuidedReflection(await api.reviewGuidedReflection(reflection.id))
      await refreshSourceReferences()
      showAiTaskFeedback({ key: reviewTask, message: '逐题反馈已生成', tone: 'success' })
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存定向回答失败'
      setError(message)
      if (shouldReview) showAiTaskFeedback({ key: reviewTask, message, tone: 'error' })
    } finally {
      if (shouldReview) finishAiTask(reviewTask)
      setBusy(false)
    }
  }

  async function copyText(text: string) {
    await navigator.clipboard.writeText(text)
    setNotice('已复制到剪贴板')
  }

  async function createExercise() {
    if (!record) return
    startAiTask({ key: 'practice', label: '正在生成练习题' })
    setError('')
    setNotice('')
    try {
      const exercise = await api.generateAiPractice(record.id)
      setRecord((current) => current ? {
        ...current,
        exercises: [...current.exercises, exercise],
      } : current)
      setActiveExerciseItemPosition(1)
      await refreshSourceReferences()
      showAiTaskFeedback({ key: 'practice', message: '练习题已生成', tone: 'success' })
    } catch (requestError) {
      showAiTaskFeedback({
        key: 'practice',
        message: requestError instanceof Error ? requestError.message : '生成练习题失败',
        tone: 'error',
      })
    } finally {
      finishAiTask('practice')
    }
  }

  async function removeLegacyExercise() {
    if (!record || !legacyExerciseToDelete) return
    const exerciseId = legacyExerciseToDelete.id
    setBusy(true)
    setLegacyExerciseDeleteError('')
    try {
      await api.deleteExercise(exerciseId)
      setRecord({
        ...record,
        exercises: record.exercises.filter((item) => item.id !== exerciseId),
      })
      setActiveExerciseItemPosition(1)
      setLegacyExerciseToDelete(null)
      setNotice('旧版练习已删除')
    } catch (requestError) {
      setLegacyExerciseDeleteError(
        requestError instanceof Error ? requestError.message : '删除旧版练习失败',
      )
    } finally {
      setBusy(false)
    }
  }

  function replaceExercise(updated: Exercise) {
    setRecord((current) => current ? {
      ...current,
      exercises: current.exercises.map((item) => item.id === updated.id ? updated : item),
    } : current)
  }

  async function persistExerciseResponse(form: HTMLFormElement, itemId: number) {
    const data = new FormData(form)
    setBusy(true)
    setError('')
    try {
      replaceExercise(await api.updateExerciseResponse(itemId, {
        answer_markdown: String(data.get('answer_markdown') ?? ''),
        selected_options: data.getAll('selected_options').map(String),
      }))
      markFormSaved(form)
      setNotice('本题答案已保存')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '保存本题答案失败')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function saveStructuredResponse(event: FormEvent<HTMLFormElement>, itemId: number) {
    event.preventDefault()
    await persistExerciseResponse(event.currentTarget, itemId)
  }

  async function uploadExerciseAttachment(itemId: number, file: File) {
    setAttachmentBusyItemId(itemId)
    setError('')
    try {
      replaceExercise(await api.uploadExerciseResponseAttachment(itemId, file))
      setNotice('作答附件已添加')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '上传作答附件失败')
    } finally {
      setAttachmentBusyItemId(null)
    }
  }

  async function deleteExerciseAttachment(itemId: number, attachmentId: number) {
    setAttachmentBusyItemId(itemId)
    setError('')
    try {
      replaceExercise(await api.deleteExerciseResponseAttachment(attachmentId))
      setNotice('作答附件已移除')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '移除作答附件失败')
    } finally {
      setAttachmentBusyItemId(null)
    }
  }

  async function moveExerciseItem(nextPosition: number, itemId: number) {
    const form = document.querySelector<HTMLFormElement>(`form[data-exercise-item-id="${itemId}"]`)
    if (form && formIsDirty(form) && !(await persistExerciseResponse(form, itemId))) return
    setActiveExerciseItemPosition(nextPosition)
  }

  async function completeStructuredExercise(exerciseId: number, itemId: number) {
    if (!record) return
    const form = document.querySelector<HTMLFormElement>(`form[data-exercise-item-id="${itemId}"]`)
    if (form && formIsDirty(form) && !(await persistExerciseResponse(form, itemId))) return
    setBusy(true)
    setError('')
    try {
      await api.completeExercise(exerciseId)
      const refreshed = await api.getDailyRecord(record.id)
      const practiceNode = refreshed.workflow_nodes.find((node) => node.node_key === 'practice')
      if (practiceNode) applyUpdatedNode(refreshed, practiceNode)
      else setRecord(refreshed)
      setNotice('今日练习已完成，可以开始批改')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '完成今日练习失败')
    } finally {
      setBusy(false)
    }
  }

  async function persistExercise(form: HTMLFormElement, exerciseId: number, complete: boolean) {
    if (!record) return '当前学习记录不可保存'
    const data = new FormData(form)
    setBusy(true)
    setError('')
    try {
      const updatedExercise = await api.updateExercise(exerciseId, {
        ai_questions: String(data.get('ai_questions') ?? ''),
        user_answers: String(data.get('user_answers') ?? ''),
      })
      const updatedRecord = {
        ...record,
        exercises: record.exercises.map((item) => item.id === updatedExercise.id ? updatedExercise : item),
      }
      setRecord(updatedRecord)
      if (complete) await setNodeStatus('practice', 'completed', updatedRecord)
      markFormSaved(form)
      setNotice(complete ? '题目和答案已保存，节点已完成' : '题目和答案已保存')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存题目和答案失败'
      setError(message)
      return message
    } finally {
      setBusy(false)
    }
  }

  async function skipIncompletePractice(form: HTMLFormElement) {
    if (!record) return '当前学习记录不可保存'
    setBusy(true)
    setError('')
    try {
      await setNodeStatus('practice', 'skipped', record, true)
      form.reset()
      markFormSaved(form)
      setNotice('练习节点已跳过')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '跳过练习失败'
      setError(message)
      return message
    } finally {
      setBusy(false)
    }
  }

  async function saveExercise(event: FormEvent<HTMLFormElement>, exerciseId: number) {
    event.preventDefault()
    const form = event.currentTarget
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null
    const complete = submitter?.dataset.complete === 'true'
    if (complete) {
      const incompleteLabels = incompleteFields(form, completionFields.practice)
      if (incompleteLabels.length === completionFields.practice.length && submitter) {
        setError('')
        setCompletionError('')
        setPendingCompletion({
          confirmLabel: '改为跳过',
          incompleteLabels,
          onConfirm: () => skipIncompletePractice(form),
          trigger: submitter,
        })
        return
      }
      if (requestIncompleteCompletion(
        form,
        submitter,
        completionFields.practice,
        () => persistExercise(form, exerciseId, true),
      )) return
    }
    await persistExercise(form, exerciseId, complete)
  }

  async function createGradingPrompt(exerciseId: number) {
    startAiTask({ key: 'grading', label: '正在批改练习答案' })
    setError('')
    try {
      setNotice('')
      await api.generateAiGrading(exerciseId)
      if (record) {
        const latestRecord = await api.getDailyRecord(record.id)
        const latestExercise = latestRecord.exercises.at(-1)
        const firstNeedsReview = latestExercise?.items?.find((item) => (
          item.response?.verdict === 'incorrect' || item.response?.verdict === 'partial'
        ))
        setActiveReviewItemPosition(firstNeedsReview?.position ?? 1)
        revealNode(latestRecord, 'review')
      }
      showAiTaskFeedback({ key: 'grading', message: '批改结果已生成', tone: 'success' })
    } catch (requestError) {
      showAiTaskFeedback({
        key: 'grading',
        message: requestError instanceof Error ? requestError.message : '批改失败',
        tone: 'error',
      })
    } finally {
      finishAiTask('grading')
    }
  }

  async function completeStructuredReview() {
    if (!record) return
    const reviewNode = record.workflow_nodes.find((node) => node.node_key === 'review')
    if (!reviewNode) return
    const reviewForms = document.querySelectorAll<HTMLFormElement>(
      `#flow-node-body-${reviewNode.id} form`,
    )
    if (Array.from(reviewForms).some((form) => formIsDirty(form))) {
      setError('请先保存批改与纠错中的修改')
      return
    }
    setBusy(true)
    setError('')
    try {
      await setNodeStatus('review', 'completed', record)
      setNotice('批改与纠错已完成')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '完成批改与纠错失败')
    } finally {
      setBusy(false)
    }
  }

  async function persistExerciseFeedback(form: HTMLFormElement, exerciseId: number, complete: boolean) {
    if (!record) return '当前学习记录不可保存'
    const feedback = String(new FormData(form).get('ai_feedback') ?? '')
    setBusy(true)
    setError('')
    try {
      const updatedExercise = await api.updateExercise(exerciseId, { ai_feedback: feedback })
      const updatedRecord = {
        ...record,
        exercises: record.exercises.map((item) => item.id === updatedExercise.id ? updatedExercise : item),
      }
      setRecord(updatedRecord)
      if (complete) await setNodeStatus('review', 'completed', updatedRecord)
      markFormSaved(form)
      setNotice(complete ? '批改反馈已保存，节点已完成' : '批改反馈已保存')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存批改反馈失败'
      setError(message)
      return message
    } finally {
      setBusy(false)
    }
  }

  async function saveExerciseFeedback(event: FormEvent<HTMLFormElement>, exerciseId: number) {
    event.preventDefault()
    const form = event.currentTarget
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null
    const complete = submitter?.dataset.complete === 'true'
    if (
      complete
      && requestIncompleteCompletion(
        form,
        submitter,
        completionFields.review,
        () => persistExerciseFeedback(form, exerciseId, true),
      )
    ) return
    await persistExerciseFeedback(form, exerciseId, complete)
  }

  function replaceMistake(exerciseId: number, updated: Mistake) {
    if (!record) return
    setRecord({
      ...record,
      exercises: record.exercises.map((item) => item.id === exerciseId ? {
        ...item,
        mistakes: item.mistakes.map((mistake) =>
          mistake.id === updated.id ? updated : mistake
        ),
      } : item),
    })
  }

  async function createMistake(event: FormEvent<HTMLFormElement>, exerciseId: number) {
    event.preventDefault()
    if (!record) return
    const form = event.currentTarget
    setBusy(true)
    setError('')
    try {
      const created = await api.createMistake(exerciseId, mistakePayload(form))
      setRecord({
        ...record,
        exercises: record.exercises.map((item) =>
          item.id === exerciseId ? { ...item, mistakes: [...item.mistakes, created] } : item
        ),
      })
      markFormSaved(form)
      setNewMistakeItemId(null)
      setNotice('错题已保存')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '保存错题失败')
    } finally {
      setBusy(false)
    }
  }

  async function updateMistake(event: FormEvent<HTMLFormElement>, mistake: Mistake) {
    event.preventDefault()
    const form = event.currentTarget
    setBusy(true)
    setError('')
    try {
      replaceMistake(
        mistake.exercise_id,
        await api.updateMistake(mistake.id, mistakePayload(form)),
      )
      markFormSaved(form)
      setNotice('错题修改已保存')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '修改错题失败')
    } finally {
      setBusy(false)
    }
  }

  async function toggleMistakeStatus(mistake: Mistake) {
    try {
      replaceMistake(
        mistake.exercise_id,
        await api.updateMistake(mistake.id, {
          status: mistake.status === 'unresolved' ? 'understood' : 'unresolved',
        }),
      )
      setNotice(mistake.status === 'unresolved' ? '错题已标记为已理解' : '错题已恢复为未解决')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '更新错题状态失败')
    }
  }

  async function removeMistake() {
    if (!record || !mistakeToDelete) return
    const mistake = mistakeToDelete
    setBusy(true)
    setMistakeDeleteError('')
    try {
      await api.deleteMistake(mistake.id)
      setRecord({
        ...record,
        exercises: record.exercises.map((item) => item.id === mistake.exercise_id ? {
          ...item,
          mistakes: item.mistakes.filter((saved) => saved.id !== mistake.id),
        } : item),
      })
      setMistakeToDelete(null)
      setNotice('错题已删除')
    } catch (requestError) {
      setMistakeDeleteError(requestError instanceof Error ? requestError.message : '删除错题失败')
    } finally {
      setBusy(false)
    }
  }

  async function generatePreviewPrompt() {
    if (!record) return
    startAiTask({ key: 'preview_questions', label: '正在生成下次回顾问题' })
    setError('')
    setNotice('')
    try {
      const previewQuestionSet = await api.generateAiPreviewQuestions(record.id)
      setRecord((current) => current ? { ...current, preview_question_set: previewQuestionSet } : current)
      await refreshSourceReferences()
      showAiTaskFeedback({
        key: 'preview_questions',
        message: '下次回顾问题已生成',
        tone: 'success',
      })
    } catch (requestError) {
      showAiTaskFeedback({
        key: 'preview_questions',
        message: requestError instanceof Error ? requestError.message : '生成下次回顾问题失败',
        tone: 'error',
      })
    } finally {
      finishAiTask('preview_questions')
    }
  }

  async function confirmSkipPractice() {
    if (!record) return
    setBusy(true)
    setSkipError('')
    try {
      await setNodeStatus('practice', 'skipped', record, true)
      setNotice('练习节点已跳过')
      setError('')
      setSkipConfirmOpen(false)
    } catch (requestError) {
      setSkipError(requestError instanceof Error ? requestError.message : '跳过练习失败')
    } finally {
      setBusy(false)
    }
  }

  async function persistTodayCompletion() {
    if (!record) return '当前学习记录不可完成'
    setBusy(true)
    startAiTask({ key: 'daily_summary', label: '正在整理今日摘要与学习记忆' })
    setError('')
    try {
      const completedRecord = await api.completeDailyRecord(record.id)
      revealNode(completedRecord, 'daily_close')
      setNotice('今日学习已完成')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '完成今日学习失败'
      setError(message)
      return message
    } finally {
      finishAiTask('daily_summary')
      setBusy(false)
    }
  }

  async function completeToday(trigger: HTMLButtonElement) {
    if (!record) return
    if (dirtyFormKeys.size > 0) {
      setError('请先保存当前修改，再完成今日学习')
      return
    }
    const incompleteLabels = record.workflow_nodes
      .filter((node) => !['daily_close', 'daily_complete'].includes(node.node_key) && node.status === 'pending')
      .map((node) => nodeTitles[node.node_key] ?? node.title)
    const questions = record.preview_question_set
    if (!questions || [questions.question_1, questions.question_2, questions.question_3].some((item) => !item.trim())) {
      incompleteLabels.push('下一次衔接问题')
    }
    if (incompleteLabels.length > 0) {
      setError('')
      setCompletionError('')
      setPendingCompletion({
        confirmLabel: '仍然结束今天',
        incompleteLabels,
        onConfirm: persistTodayCompletion,
        trigger,
      })
      return
    }
    await persistTodayCompletion()
  }

  if (!record) {
    return (
      <main className="context-page">
        <PageBackBar ariaLabel="学习记录导航" to="/courses" />
        <div className="content content--flow context-page__content">
          <p className="error-banner" role="alert">{routeData.notFound ? '学习记录不存在' : error}</p>
        </div>
      </main>
    )
  }

  const completedCount = record.workflow_nodes.filter((node) => node.status !== 'pending').length
  const progress = Math.round((completedCount / record.workflow_nodes.length) * 100)
  const recallReflection = (record.guided_reflections ?? []).find((item) => item.kind === 'recall')
  const reconstructionReflection = (record.guided_reflections ?? []).find(
    (item) => item.kind === 'reconstruct',
  )
  const legacyRecallInteraction = record.ai_interactions
    .filter((item) => item.kind === 'recall_review')
    .at(-1)
  const legacyReconstructionInteraction = record.ai_interactions
    .filter((item) => item.kind === 'reconstruction_review')
    .at(-1)
  const exercise = record.exercises.at(-1)
  const structuredItems = exercise?.format_version === 2 ? (exercise.items ?? []) : []
  const activeExerciseItem = structuredItems.find(
    (item) => item.position === activeExerciseItemPosition,
  ) ?? structuredItems[0]
  const activeReviewItem = structuredItems.find(
    (item) => item.position === activeReviewItemPosition,
  ) ?? structuredItems[0]
  const mistakeDraftItem = structuredItems.find((item) => item.id === newMistakeItemId)
  const activeReviewMistake = activeReviewItem
    ? exercise?.mistakes.find((mistake) => mistake.exercise_item_id === activeReviewItem.id)
    : undefined
  const answeredExerciseItems = structuredItems.filter((item) => (
    Boolean(item.response?.answer_markdown.trim())
    || Boolean(item.response?.selected_options.length)
    || Boolean(item.response?.attachments?.length)
  )).length
  const materialScopes: MaterialScopeOption[] = [
    {
      value: `course-${record.course_id}`,
      label: '当前课程',
      course_id: record.course_id,
      chapter_id: null,
      section_id: null,
      is_primary: false,
    },
    {
      value: `chapter-${record.chapter_id}`,
      label: '当前章节',
      course_id: record.course_id,
      chapter_id: record.chapter_id,
      section_id: null,
      is_primary: false,
    },
    {
      value: `section-${record.section_id}`,
      label: '当前小节',
      course_id: record.course_id,
      chapter_id: record.chapter_id,
      section_id: record.section_id,
      is_primary: false,
    },
  ]

  function editAnswerFromReview(position: number) {
    if (!record) return
    const practiceNode = record.workflow_nodes.find((node) => node.node_key === 'practice')
    setActiveExerciseItemPosition(position)
    if (practiceNode) {
      setExpandedNodeIds((current) => new Set([...current, practiceNode.id]))
      window.requestAnimationFrame(() => {
        document.getElementById(`flow-node-body-${practiceNode.id}`)?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        })
      })
    }
  }

  const aiTaskState = (key: AiTaskKey) => {
    const activeTask = activeAiTasks[key]
    if (activeTask) {
      const matchingRun = activeServerRuns.find((run) => run.task === aiTaskRunKeys[key])
        ?? (activeAiTaskCount === 1
          ? activeServerRuns.find((run) => run.task === 'material_context')
          : undefined)
      return (
        <AiTaskStatus
          key={key}
          label={activeTask.label}
          phase={aiRunPhase(matchingRun ?? null)}
          startedAt={matchingRun?.created_at}
          onCancel={matchingRun ? () => void cancelActiveAiTask(matchingRun) : undefined}
        />
      )
    }
    const feedback = aiTaskFeedbacks[key]
    if (!feedback) return null
    const reconnectRequired = feedback.message.includes('重新连接 Codex')
      || feedback.message.includes('登录已失效')
    return (
      <div
        className={`ai-task-feedback ai-task-feedback--${feedback.tone}`}
        role={feedback.tone === 'error' ? 'alert' : 'status'}
      >
        <span>{feedback.message}</span>
        {reconnectRequired && <Link className="text-button" to="/settings">前往设置</Link>}
      </div>
    )
  }

  return (
    <main ref={pageRef} className="context-page" onInputCapture={updateDirtyForm} onChangeCapture={updateDirtyForm}>
      <PageBackBar ariaLabel="学习记录导航" to={`/courses/${record.course_id}`} />
      <div className="content content--flow context-page__content">
        <header className="page-heading">
          <p className="eyebrow">{record.study_date}</p>
          <h1>{record.section_title}</h1>
          <p className="page-summary">今日学习记录</p>
        </header>

      {error && <p className="error-banner" role="alert">{error}</p>}
      {notice && <p className="notice-banner" role="status">{notice}</p>}
      <DraftStatus
        key={draftRecovered ? 'daily-restored' : 'daily-current'}
        dirtyCount={dirtyFormKeys.size}
        recoveredLabel={draftRecovered ? '已恢复上次草稿' : undefined}
      />
      {activeServerRuns
        .filter((run) => !(Object.keys(activeAiTasks) as AiTaskKey[])
          .some((key) => aiTaskRunKeys[key] === run.task))
        .map((run) => (
          <AiTaskStatus
            key={run.id}
            label="正在继续上次的生成任务"
            phase={aiRunPhase(run)}
            startedAt={run.created_at}
            recovered
            onCancel={() => void cancelActiveAiTask(run)}
          />
        ))}
      <SourceReferences
        references={record.ai_source_refs ?? []}
        materials={record.materials ?? []}
      />

      <section className="record-progress" aria-label={`已完成 ${completedCount} 个，共 ${record.workflow_nodes.length} 个节点`}>
        <div><span>节点进度</span><strong>{completedCount}/{record.workflow_nodes.length}</strong></div>
        <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
      </section>

        <div className="flow-list">
        <FlowNode {...flowNodeProps('recall')}>
          {record.previous_preview_questions && (
            <aside className="previous-preview" aria-label="上次学习回顾">
              <div>
                <strong>上次学习回顾</strong>
                <span>
                  {record.previous_preview_questions.study_date}
                  {' · '}
                  {record.previous_preview_questions.section_title}
                </span>
              </div>
              {record.previous_preview_questions.questions.length > 0 ? (
                <ol>
                  {record.previous_preview_questions.questions.map((question) => (
                    <li key={question}><MarkdownContent content={question} /></li>
                  ))}
                </ol>
              ) : (
                <p className="muted">上次学习没有留下衔接问题。完成自由回忆后，可让 AI 根据上次学习补充 3 个问题。</p>
              )}
            </aside>
          )}
          <form className="node-form" data-dirty-key="content-recall" data-save-kind="content" onSubmit={(event) => saveReflectionSeed(event, 'recall', 'recall')}>
            <FieldLabel title="自由回忆" description="先不看材料，写下你记得的相关知识、核心概念和它们之间的关系"><textarea name="recall_last_learned" rows={7} defaultValue={record.recall_last_learned} /></FieldLabel>
            <div className="form-actions form-actions--guided">
              <button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存回忆</button>
              <button className="primary-button" type="submit" data-generate="true" disabled={busy || isAiTaskActive('recall_questions')}><Sparkles size={15} />{isAiTaskActive('recall_questions') ? '生成中' : '保存并生成 3 个问题'}</button>
              <button className="text-button" type="submit" data-complete="true" disabled={busy}>AI 不可用？仅保存并完成</button>
            </div>
          </form>
          {record.recall_last_learned.trim() && record.previous_records.length > 0 ? (
            <details className="previous-records">
              <summary>回忆后核对最近记录</summary>
              {record.previous_records.map((item) => (
                <div key={item.id}><strong>{item.study_date}</strong><p>{item.reconstruct_main_learning || item.recall_last_learned || '未填写摘要'}</p></div>
              ))}
            </details>
          ) : null}
          {aiTaskState('recall_questions')}
          {recallReflection && (
            <GuidedReflectionPanel
              reflection={recallReflection}
              busy={busy || isAiTaskActive('recall_questions') || isAiTaskActive('recall_review')}
              taskState={aiTaskState('recall_review')}
              completeLabel="完成闭卷回顾"
              onSubmit={saveGuidedReflection}
              onRegenerate={() => void regenerateGuidedQuestions('recall', 'recall')}
              onComplete={() => void setNodeStatus('recall', 'completed')}
            />
          )}
          {!recallReflection && legacyRecallInteraction?.feedback_text && (
            <details className="legacy-ai-feedback"><summary>查看旧版回顾评阅</summary><MarkdownContent content={legacyRecallInteraction.feedback_text} /></details>
          )}
        </FlowNode>

        <FlowNode {...flowNodeProps('study')}>
          <MaterialLibrary
            materials={record.materials ?? []}
            scopeOptions={[materialScopes[2]]}
            defaultScope={`section-${record.section_id}`}
            allowScopeEdit={false}
            showScopeSelect={false}
            onChanged={async () => setRecord(await api.getDailyRecord(record.id))}
          />
          {(record.materials ?? []).length > 0 && (
            <form
              className="material-selection-form"
              data-dirty-key="materials-selection"
              data-save-kind="materials"
              onSubmit={saveMaterialSelections}
            >
              <div className="material-selection-list">
                {(record.materials ?? []).map((material) => (
                  <div className="material-selection-row" key={material.id}>
                    <label className="material-selection-check">
                      <input
                        type="checkbox"
                        name={`material_${material.id}_selected`}
                        defaultChecked={material.selected}
                        disabled={material.status === 'failed'}
                      />
                      <span>
                        <strong>{material.title}</strong>
                        <small>{material.status === 'failed'
                          ? material.error_text
                          : material.last_refresh_status === 'failed'
                            ? '上次重新解析失败，继续使用已有版本'
                            : '参与本节后续评阅、出题和笔记整理'}</small>
                      </span>
                    </label>
                    <input
                      name={`material_${material.id}_range`}
                      defaultValue={material.range_note}
                      placeholder="本次页码、章节或范围"
                      aria-label={`${material.title}的本次学习范围`}
                      disabled={material.status === 'failed'}
                    />
                  </div>
                ))}
              </div>
              <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存材料选择</button></div>
            </form>
          )}
          <form className="node-form" data-dirty-key="content-study" data-save-kind="content" onSubmit={(event) => saveContent(event, 'study')}>
            <FieldLabel title="学习范围" description="记录课程、章节、页码或材料范围"><textarea name="study_material_scope" rows={4} defaultValue={record.study_material_scope} /></FieldLabel>
            <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存</button><button className="primary-button" type="submit" data-complete="true" disabled={busy}><Check size={15} />保存并完成</button></div>
          </form>
        </FlowNode>

        <FlowNode {...flowNodeProps('reconstruct')}>
          <form className="node-form" data-dirty-key="content-reconstruct" data-save-kind="content" onSubmit={(event) => saveReflectionSeed(event, 'reconstruct', 'reconstruct')}>
            <FieldLabel title="自由重构" description="合上材料，用自己的语言重建本次内容的主线、关键概念、条件和推导"><textarea name="reconstruct_main_learning" rows={9} defaultValue={record.reconstruct_main_learning} /></FieldLabel>
            <div className="form-actions form-actions--guided">
              <button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存重构</button>
              <button className="primary-button" type="submit" data-generate="true" disabled={busy || isAiTaskActive('reconstruction_questions')}><Sparkles size={15} />{isAiTaskActive('reconstruction_questions') ? '生成中' : '保存并生成 3 个问题'}</button>
              <button className="text-button" type="submit" data-complete="true" disabled={busy}>AI 不可用？仅保存并完成</button>
            </div>
          </form>
          {aiTaskState('reconstruction_questions')}
          {reconstructionReflection && (
            <GuidedReflectionPanel
              reflection={reconstructionReflection}
              busy={busy || isAiTaskActive('reconstruction_questions') || isAiTaskActive('reconstruction_review')}
              taskState={aiTaskState('reconstruction_review')}
              completeLabel="完成主动重构"
              onSubmit={saveGuidedReflection}
              onRegenerate={() => void regenerateGuidedQuestions('reconstruct', 'reconstruct')}
              onComplete={() => void setNodeStatus('reconstruct', 'completed')}
            />
          )}
          {!reconstructionReflection && legacyReconstructionInteraction?.feedback_text && (
            <details className="legacy-ai-feedback"><summary>查看旧版重构评阅</summary><MarkdownContent content={legacyReconstructionInteraction.feedback_text} /></details>
          )}
        </FlowNode>

        <FlowNode {...flowNodeProps('practice')}>
          <div className="node-actions-line">
            <div className="node-action-group">
              <button className="secondary-button" type="button" disabled={busy || isAiTaskActive('practice')} onClick={createExercise}><Sparkles size={16} />{isAiTaskActive('practice') ? '生成中' : exercise ? '生成新一组练习' : '生成练习'}</button>
              {exercise?.format_version === 1 && (
                <button
                  className="text-button text-button--danger"
                  type="button"
                  disabled={busy}
                  onClick={(event) => {
                    setLegacyExerciseDeleteError('')
                    setLegacyExerciseDeleteTrigger(event.currentTarget)
                    setLegacyExerciseToDelete(exercise)
                  }}
                >
                  <Trash2 size={15} />删除旧版练习
                </button>
              )}
            </div>
            <button
              className="text-button"
              type="button"
              onClick={(event) => {
                setSkipTrigger(event.currentTarget)
                setSkipError('')
                setSkipConfirmOpen(true)
              }}
            >
              <SkipForward size={15} />跳过
            </button>
          </div>
          {aiTaskState('practice')}
          {exercise && (
            <>
              <details className="prompt-details">
                <summary>查看本次出题提示词</summary>
                <div className="prompt-toolbar"><strong>出题提示词</strong><button className="icon-button" type="button" title="复制出题提示词" aria-label="复制出题提示词" onClick={() => copyText(exercise.generation_prompt)}><Clipboard size={16} /></button></div>
                <textarea className="prompt-output" readOnly rows={10} value={exercise.generation_prompt} />
              </details>
              {structuredItems.length > 0 && activeExerciseItem ? (
                <div className="structured-exercise">
                  <div className="exercise-question-nav" role="navigation" aria-label="练习题导航">
                    {structuredItems.map((item) => {
                      const answered = Boolean(item.response?.answer_markdown.trim())
                        || Boolean(item.response?.selected_options.length)
                        || Boolean(item.response?.attachments?.length)
                      return (
                        <button
                          className={item.position === activeExerciseItem.position ? 'active' : ''}
                          type="button"
                          title={`第 ${item.position} 题${answered ? '，已作答' : '，未作答'}`}
                          aria-current={item.position === activeExerciseItem.position ? 'step' : undefined}
                          data-answered={answered}
                          key={item.id}
                          onClick={() => void moveExerciseItem(item.position, activeExerciseItem.id)}
                        >
                          {item.position}
                        </button>
                      )
                    })}
                  </div>
                  <form
                    key={activeExerciseItem.id}
                    className="exercise-question-form"
                    data-dirty-key={`exercise-item-${activeExerciseItem.id}`}
                    data-save-kind="exercise-response"
                    data-entity-id={activeExerciseItem.id}
                    data-exercise-item-id={activeExerciseItem.id}
                    onSubmit={(event) => saveStructuredResponse(event, activeExerciseItem.id)}
                  >
                    <header className="exercise-question-header">
                      <div>
                        <span>第 {activeExerciseItem.position} / {structuredItems.length} 题</span>
                        <strong>{exerciseTypeLabels[activeExerciseItem.item_type]}</strong>
                      </div>
                      <span>{exerciseDifficultyLabels[activeExerciseItem.difficulty]}</span>
                    </header>
                    <div className="exercise-question-stem">
                      <MarkdownContent content={activeExerciseItem.stem_markdown} />
                    </div>
                    {activeExerciseItem.options.length > 0 ? (
                      <fieldset className="exercise-options">
                        <legend>{activeExerciseItem.item_type === 'multiple_choice' ? '选择所有符合的选项' : '选择一个答案'}</legend>
                        {activeExerciseItem.options.map((option) => (
                          <label key={option.id}>
                            <input
                              type={activeExerciseItem.item_type === 'multiple_choice' ? 'checkbox' : 'radio'}
                              name="selected_options"
                              value={option.id}
                              defaultChecked={activeExerciseItem.response?.selected_options.includes(option.id)}
                            />
                            <strong className="exercise-option-id">{option.id}</strong>
                            <MarkdownContent content={option.label} className="exercise-option-content" />
                          </label>
                        ))}
                      </fieldset>
                    ) : (
                      <>
                        <FieldLabel title="我的作答" description="写出完整思路、计算或推导过程">
                          <textarea name="answer_markdown" rows={12} defaultValue={activeExerciseItem.response?.answer_markdown ?? ''} />
                        </FieldLabel>
                        <div className="answer-attachments" aria-label="作答附件">
                          <div className="answer-attachments__toolbar">
                            <span>手写或长篇作答也可以附上图片/PDF</span>
                            <label className="answer-attachment-button">
                              <Paperclip size={14} aria-hidden="true" />
                              {attachmentBusyItemId === activeExerciseItem.id ? '处理中' : '添加附件'}
                              <input
                                type="file"
                                accept="application/pdf,image/png,image/jpeg,image/webp"
                                disabled={attachmentBusyItemId === activeExerciseItem.id || (activeExerciseItem.response?.attachments?.length ?? 0) >= 5}
                                onChange={(event) => {
                                  const file = event.currentTarget.files?.[0]
                                  event.currentTarget.value = ''
                                  if (file) void uploadExerciseAttachment(activeExerciseItem.id, file)
                                }}
                              />
                            </label>
                          </div>
                          {(activeExerciseItem.response?.attachments?.length ?? 0) > 0 && (
                            <ul className="answer-attachment-list">
                              {activeExerciseItem.response?.attachments?.map((attachment) => (
                                <li key={attachment.id}>
                                  <FileText size={14} aria-hidden="true" />
                                  <span>{attachment.original_name}</span>
                                  <small>{Math.max(1, Math.round(attachment.size_bytes / 1024))} KB</small>
                                  {attachment.processing_status === 'ready_truncated' && <small title="为控制批改上下文长度，仅使用前 50000 个字符">文字已截取</small>}
                                  <button type="button" disabled={attachmentBusyItemId === activeExerciseItem.id} aria-label={`移除附件 ${attachment.original_name}`} onClick={() => void deleteExerciseAttachment(activeExerciseItem.id, attachment.id)}><X size={13} /></button>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </>
                    )}
                    {activeExerciseItem.options.length > 0 && <input type="hidden" name="answer_markdown" value="" />}
                    {activeExerciseItem.response?.feedback_markdown && (
                      <div className={`exercise-item-feedback exercise-item-feedback--${activeExerciseItem.response.verdict}`}>
                        <div><strong>本题反馈</strong><span>{exerciseVerdictLabels[activeExerciseItem.response.verdict] ?? '已批改'}</span></div>
                        <MarkdownContent content={activeExerciseItem.response.feedback_markdown} />
                      </div>
                    )}
                    <div className="exercise-question-footer">
                      {activeExerciseItem.position > 1 ? (
                        <button className="secondary-button" type="button" disabled={busy} onClick={() => void moveExerciseItem(activeExerciseItem.position - 1, activeExerciseItem.id)}><ChevronLeft size={16} />上一题</button>
                      ) : <span className="exercise-nav-spacer" aria-hidden="true" />}
                      <span>已作答 {answeredExerciseItems}/{structuredItems.length}</span>
                      {activeExerciseItem.position < structuredItems.length ? (
                        <button className="secondary-button" type="button" disabled={busy} onClick={() => void moveExerciseItem(activeExerciseItem.position + 1, activeExerciseItem.id)}>下一题<ChevronRight size={16} /></button>
                      ) : <span className="exercise-nav-spacer" aria-hidden="true" />}
                    </div>
                    <div className="form-actions">
                      <button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存本题</button>
                      <button className="primary-button" type="button" disabled={busy || exercise.status === 'submitted' || exercise.status === 'graded'} onClick={() => void completeStructuredExercise(exercise.id, activeExerciseItem.id)}><Check size={15} />{exercise.status === 'submitted' || exercise.status === 'graded' ? '今日练习已完成' : '完成今日练习'}</button>
                    </div>
                  </form>
                </div>
              ) : (
                <form
                  className="node-form"
                  data-dirty-key={`exercise-${exercise.id}`}
                  data-save-kind="exercise"
                  data-entity-id={exercise.id}
                  onSubmit={(event) => saveExercise(event, exercise.id)}
                >
                  <EditableMarkdown title="练习题目" description="旧版整段练习，可继续查看和编辑" name="ai_questions" rows={18} defaultValue={exercise.ai_questions} />
                  <FieldLabel title="我的作答" description="独立完成答案、计算或推导"><textarea name="user_answers" rows={12} defaultValue={exercise.user_answers} /></FieldLabel>
                  <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存题目和答案</button><button className="primary-button" type="submit" data-complete="true" disabled={busy}><Check size={15} />保存并完成</button></div>
                </form>
              )}
            </>
          )}
        </FlowNode>

        <FlowNode {...flowNodeProps('review')}>
          {exercise ? (
            <>
              <button className="secondary-button" type="button" disabled={busy || isAiTaskActive('grading') || (structuredItems.length > 0 && exercise.status === 'draft')} onClick={() => createGradingPrompt(exercise.id)}><Sparkles size={16} />{isAiTaskActive('grading') ? '批改中' : exercise.ai_feedback ? '重新批改' : '批改答案'}</button>
              {aiTaskState('grading')}
              {exercise.grading_prompt && (
                <details className="prompt-details"><summary>查看本次批改提示词</summary><div className="prompt-toolbar"><strong>批改提示词</strong><button className="icon-button" type="button" title="复制批改提示词" aria-label="复制批改提示词" onClick={() => copyText(exercise.grading_prompt)}><Clipboard size={16} /></button></div><textarea className="prompt-output" readOnly rows={12} value={exercise.grading_prompt} /></details>
              )}
              {structuredItems.length > 0 ? (
                exercise.status === 'graded' && activeReviewItem ? (
                  <div className="structured-exercise exercise-review-workspace">
                    <div className="exercise-question-nav" role="navigation" aria-label="批改题目导航">
                      {structuredItems.map((item) => (
                        <button
                          className={item.position === activeReviewItem.position ? 'active' : ''}
                          type="button"
                          title={`第 ${item.position} 题，${exerciseVerdictLabels[item.response?.verdict ?? ''] ?? '未批改'}`}
                          aria-label={`第 ${item.position} 题，${exerciseVerdictLabels[item.response?.verdict ?? ''] ?? '未批改'}`}
                          aria-current={item.position === activeReviewItem.position ? 'step' : undefined}
                          data-verdict={item.response?.verdict || 'ungraded'}
                          key={item.id}
                          onClick={() => setActiveReviewItemPosition(item.position)}
                        >
                          {item.position}
                        </button>
                      ))}
                    </div>
                    <article className="exercise-review-item">
                      <header className="exercise-question-header">
                        <div>
                          <span>第 {activeReviewItem.position} / {structuredItems.length} 题</span>
                          <strong>{exerciseTypeLabels[activeReviewItem.item_type]}</strong>
                        </div>
                        <span className={`exercise-review-verdict exercise-review-verdict--${activeReviewItem.response?.verdict || 'ungraded'}`}>
                          {exerciseVerdictLabels[activeReviewItem.response?.verdict ?? ''] ?? '未批改'}
                        </span>
                      </header>
                      <div className="exercise-question-stem"><MarkdownContent content={activeReviewItem.stem_markdown} /></div>
                      {activeReviewItem.options.length > 0 && (
                        <div className="exercise-review-options" aria-label="本题选项">
                          {activeReviewItem.options.map((option) => {
                            const selected = activeReviewItem.response?.selected_options.includes(option.id)
                            return (
                              <div data-selected={selected} key={option.id}>
                                {selected ? <Check size={17} /> : <Circle size={17} />}
                                <strong>{option.id}</strong>
                                <MarkdownContent content={option.label} />
                              </div>
                            )
                          })}
                        </div>
                      )}
                      <section className="exercise-review-answer">
                        <div><strong>我的作答</strong><button className="text-button" type="button" onClick={() => editAnswerFromReview(activeReviewItem.position)}>修改答案</button></div>
                        <MarkdownContent content={activeReviewItem.response?.answer_markdown || (activeReviewItem.response?.selected_options.length ? `选择：${activeReviewItem.response.selected_options.join('、')}` : '未作答')} />
                      </section>
                      <section className={`exercise-item-feedback exercise-item-feedback--${activeReviewItem.response?.verdict || 'ungraded'}`}>
                        <div><strong>本题反馈</strong><span>{exerciseVerdictLabels[activeReviewItem.response?.verdict ?? ''] ?? '未批改'}</span></div>
                        <MarkdownContent content={activeReviewItem.response?.feedback_markdown || '暂无反馈'} />
                      </section>
                      {(activeReviewItem.response?.verdict === 'incorrect' || activeReviewItem.response?.verdict === 'partial') && (
                        <div className="exercise-review-mistake-action">
                          <span>{activeReviewMistake ? '本题已整理到错题记录' : '需要后续复习时，可整理当前题'}</span>
                          {activeReviewMistake ? (
                            <span className="record-status record-status--understood">已整理</span>
                          ) : (
                            <button
                              className="secondary-button"
                              type="button"
                              aria-controls="mistake-editor"
                              aria-expanded={newMistakeItemId === activeReviewItem.id}
                              onClick={(event) => requestMistakeDraftState(
                                newMistakeItemId === activeReviewItem.id ? null : activeReviewItem.id,
                                event.currentTarget,
                              )}
                            ><Plus size={15} />{newMistakeItemId === activeReviewItem.id ? '收起整理' : '整理本题'}</button>
                          )}
                        </div>
                      )}
                      <div className="exercise-question-footer">
                        {activeReviewItem.position > 1 ? (
                          <button className="secondary-button" type="button" onClick={() => setActiveReviewItemPosition(activeReviewItem.position - 1)}><ChevronLeft size={16} />上一题</button>
                        ) : <span className="exercise-nav-spacer" aria-hidden="true" />}
                        <span>逐题复核 {activeReviewItem.position}/{structuredItems.length}</span>
                        {activeReviewItem.position < structuredItems.length ? (
                          <button className="secondary-button" type="button" onClick={() => setActiveReviewItemPosition(activeReviewItem.position + 1)}>下一题<ChevronRight size={16} /></button>
                        ) : <span className="exercise-nav-spacer" aria-hidden="true" />}
                      </div>
                    </article>
                  </div>
                ) : <p className="muted">完成全部题目后即可一次批改整套练习。</p>
              ) : (
                <form
                  className="node-form"
                  data-dirty-key={`exercise-feedback-${exercise.id}`}
                  data-save-kind="exercise-feedback"
                  data-entity-id={exercise.id}
                  onSubmit={(event) => saveExerciseFeedback(event, exercise.id)}
                >
                  <EditableMarkdown title="批改反馈" description="已生成，可按需要继续编辑" name="ai_feedback" rows={18} defaultValue={exercise.ai_feedback} />
                  <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存批改反馈</button><button className="primary-button" type="submit" data-complete="true" disabled={busy}><Check size={15} />保存并完成</button></div>
                </form>
              )}
              <div className="mistakes-workspace">
                <div className="subsection-heading">
                  <div><strong>错题整理</strong><span>{exercise.mistakes.length} 条</span></div>
                  {structuredItems.length > 0 && <span>请在上方错误题中选择“整理本题”</span>}
                </div>
                {newMistakeItemId !== null && mistakeDraftItem && (
                  <form
                    id="mistake-editor"
                    className="mistake-form"
                    data-dirty-key={`mistake-new-${mistakeDraftItem.id}`}
                    data-save-kind="mistake-create"
                    data-entity-id={exercise.id}
                    onSubmit={(event) => createMistake(event, exercise.id)}
                  >
                    <MistakeFields exerciseItem={mistakeDraftItem} />
                    <div className="form-actions form-actions--equal"><button className="primary-button" type="submit" disabled={busy}><Save size={15} />保存错题</button><button className="secondary-button" type="button" onClick={(event) => requestMistakeDraftState(null, event.currentTarget)}>取消</button></div>
                  </form>
                )}
                <div className="mistake-list">
                  {exercise.mistakes.map((mistake) => (
                    <details className={`mistake-item mistake-item--${mistake.status}`} key={mistake.id}>
                      <summary><span>{mistakeTypeLabels[mistake.error_type]}</span><strong>{mistake.original_question}</strong><em>{mistake.status === 'understood' ? '已理解' : '未解决'}</em></summary>
                      <form
                        className="mistake-form"
                        data-dirty-key={`mistake-${mistake.id}`}
                        data-save-kind="mistake-update"
                        data-entity-id={mistake.id}
                        onSubmit={(event) => updateMistake(event, mistake)}
                      >
                        <MistakeFields mistake={mistake} />
                        <div className="form-actions">
                          <button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存修改</button>
                          <button className="secondary-button" type="button" onClick={() => toggleMistakeStatus(mistake)}><Check size={15} />{mistake.status === 'understood' ? '标记为未解决' : '标记为已理解'}</button>
                          <button className="text-button danger-text" type="button" onClick={(event) => { setMistakeDeleteTrigger(event.currentTarget); setMistakeDeleteError(''); setMistakeToDelete(mistake) }}><Trash2 size={15} />删除</button>
                        </div>
                      </form>
                    </details>
                  ))}
                </div>
              </div>
              {structuredItems.length > 0 && exercise.status === 'graded' && (
                <div className="form-actions">
                  <button
                    className="primary-button"
                    type="button"
                    disabled={busy || nodeByKey('review').status === 'completed'}
                    onClick={() => void completeStructuredReview()}
                  >
                    <Check size={15} />
                    {nodeByKey('review').status === 'completed'
                      ? '批改与纠错已完成'
                      : '完成批改与纠错'}
                  </button>
                </div>
              )}
            </>
          ) : <p className="muted">尚未创建练习</p>}
        </FlowNode>

        <FlowNode {...flowNodeProps('daily_close')}>
          <button className="secondary-button" type="button" disabled={busy || isAiTaskActive('preview_questions')} onClick={generatePreviewPrompt}><Sparkles size={16} />{isAiTaskActive('preview_questions') ? '生成中' : record.preview_question_set ? '重新生成问题' : '生成下次回顾问题'}</button>
          {aiTaskState('preview_questions')}
          {record.preview_question_set && (
            <>
              <details className="prompt-details">
                <summary>查看下次回顾问题提示词</summary>
                <div className="prompt-toolbar"><strong>下次回顾问题提示词</strong><button className="icon-button" type="button" title="复制下次回顾问题提示词" aria-label="复制下次回顾问题提示词" onClick={() => copyText(record.preview_question_set?.prompt_text ?? '')}><Clipboard size={16} /></button></div>
                <textarea className="prompt-output" readOnly rows={12} value={record.preview_question_set.prompt_text} />
              </details>
              <section className="node-form preview-question-form" aria-label="三个下次回顾问题">
                <div className="field-group-intro"><strong>三个下次回顾问题</strong><span>问题只读；会自动带到同一课程的下一次学习</span></div>
                <ol>
                  {[
                    record.preview_question_set.question_1,
                    record.preview_question_set.question_2,
                    record.preview_question_set.question_3,
                  ].map((question, index) => (
                    <li key={`${index}-${question}`}>
                      <strong>问题 {index + 1}</strong>
                      <MarkdownContent content={question} />
                    </li>
                  ))}
                </ol>
              </section>
            </>
          )}
          {aiTaskState('daily_summary')}
          <button className="primary-button complete-day-button" type="button" disabled={busy || record.is_completed} onClick={(event) => void completeToday(event.currentTarget)}><Check size={17} />{record.is_completed ? '今日已完成' : '今日完成'}</button>
          {record.context_summary && (
            <section className="daily-summary" aria-label="今日学习摘要">
              <MarkdownContent content={record.context_summary} />
            </section>
          )}
          {record.is_completed && (
            <div className="section-finalization-callout">
              <div><strong>这个小节已经学完了吗？</strong><span>如果还需要继续，下一次进入小节会创建新的学习记录。</span></div>
              <Link className="primary-button inline-link-button" to={`/daily-records/${record.id}/note`}><FileText size={16} />整理笔记并完成小节</Link>
            </div>
          )}
        </FlowNode>
        </div>
      </div>

      <ConfirmDialog
        open={skipConfirmOpen}
        title="跳过练习与推导？"
        description="今天的练习与推导节点会标记为已跳过，之后仍可继续查看本次学习记录。"
        confirmLabel="确认跳过"
        variant="warning"
        busy={busy}
        error={skipError}
        returnFocusTo={skipTrigger}
        onCancel={() => {
          if (busy) return
          setSkipError('')
          setSkipConfirmOpen(false)
        }}
        onConfirm={confirmSkipPractice}
      />
      {legacyExerciseToDelete && <TwoStepDeleteDialog
        key={legacyExerciseToDelete.id}
        open
        title="删除旧版练习？"
        description="这组旧版题目、答案、批改和关联错题会被删除。"
        finalDescription="即将永久删除这组旧版练习及其关联内容，删除后无法恢复。"
        busy={busy}
        error={legacyExerciseDeleteError}
        returnFocusTo={legacyExerciseDeleteTrigger}
        onCancel={() => {
          if (busy) return
          setLegacyExerciseDeleteError('')
          setLegacyExerciseToDelete(null)
        }}
        onConfirm={removeLegacyExercise}
      />}
      {mistakeToDelete && <TwoStepDeleteDialog
        key={mistakeToDelete.id}
        open
        title="删除这条错题？"
        description="错题的结构化内容和理解状态会被删除。"
        finalDescription={`即将永久删除错题“${mistakeToDelete.error_content}”，删除后无法恢复。`}
        busy={busy}
        error={mistakeDeleteError}
        returnFocusTo={mistakeDeleteTrigger}
        onCancel={() => {
          if (busy) return
          setMistakeDeleteError('')
          setMistakeToDelete(null)
        }}
        onConfirm={removeMistake}
      />}
      <ConfirmDialog
        open={mistakeDraftDiscard !== null}
        title="放弃错题草稿？"
        description="当前错题还没有保存。放弃后，已经填写的内容会丢失。"
        confirmLabel="放弃草稿"
        variant="warning"
        returnFocusTo={mistakeDraftDiscard?.trigger}
        onCancel={() => setMistakeDraftDiscard(null)}
        onConfirm={discardMistakeDraft}
      />
      <IncompleteCompletionDialog
        open={pendingCompletion !== null}
        incompleteLabels={pendingCompletion?.incompleteLabels ?? []}
        confirmLabel={pendingCompletion?.confirmLabel}
        busy={busy}
        error={completionError}
        returnFocusTo={pendingCompletion?.trigger}
        onCancel={() => {
          if (busy) return
          setCompletionError('')
          setPendingCompletion(null)
        }}
        onConfirm={confirmPendingCompletion}
      />
      <UnsavedChangesGuard
        dirty={dirtyFormKeys.size > 0}
        onDiscard={() => dirtyFormKeys.forEach((key) => clearFormDraft(formDraftKey(key)))}
        onSave={saveAllDirtyForms}
      />
    </main>
  )
}
