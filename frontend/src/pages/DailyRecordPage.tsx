import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  Clipboard,
  FileText,
  Plus,
  Save,
  SkipForward,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { Link, useLoaderData } from 'react-router-dom'
import { api } from '../api'
import type {
  AiInteractionKind,
  AiRun,
  DailyRecord,
  DailyRecordContent,
  DailyRecordMaterial,
  Exercise,
  ExerciseItem,
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
    original_question: String(data.get('original_question') ?? ''),
    user_answer: String(data.get('user_answer') ?? ''),
    error_content: String(data.get('error_content') ?? ''),
    error_type: String(data.get('error_type') ?? 'concept') as MistakeType,
    correct_approach: String(data.get('correct_approach') ?? ''),
    cause_analysis: String(data.get('cause_analysis') ?? ''),
  }
}

function MistakeFields({
  mistake,
  exerciseItem,
  legacyQuestion = '',
  legacyAnswer = '',
}: {
  mistake?: Mistake
  exerciseItem?: ExerciseItem
  legacyQuestion?: string
  legacyAnswer?: string
}) {
  const selectedAnswer = exerciseItem?.response?.selected_options.join('、') ?? ''
  const originalQuestion = mistake?.original_question ?? exerciseItem?.stem_markdown ?? legacyQuestion
  const userAnswer = mistake?.user_answer
    || exerciseItem?.response?.answer_markdown
    || selectedAnswer
    || legacyAnswer
  return (
    <div className="mistake-fields">
      {exerciseItem && <input type="hidden" name="exercise_item_id" value={exerciseItem.id} />}
      <div className="mistake-readonly-field"><strong>原题</strong><span>题目内容与练习保持一致</span><MarkdownContent content={originalQuestion || '暂无题目内容'} /><input type="hidden" name="original_question" value={originalQuestion} /></div>
      <div className="mistake-readonly-field"><strong>原始作答</strong><span>保留整理错题时的答案</span><MarkdownContent content={userAnswer || '未填写'} /><input type="hidden" name="user_answer" value={userAnswer} /></div>
      <FieldLabel title="错误点" description="具体写清错在哪里"><textarea required name="error_content" rows={3} defaultValue={mistake?.error_content} /></FieldLabel>
      <FieldLabel title="错误类型" description="选择最接近的原因"><select name="error_type" defaultValue={mistake?.error_type ?? 'concept'}>{Object.entries(mistakeTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></FieldLabel>
      <FieldLabel title="正确思路" description="记录正确的切入点和解题路径"><textarea required name="correct_approach" rows={3} defaultValue={mistake?.correct_approach} /></FieldLabel>
      <FieldLabel title="原因分析" description="说明为什么会错、哪部分没有理解到位"><textarea required name="cause_analysis" rows={3} defaultValue={mistake?.cause_analysis} /></FieldLabel>
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
  const [activeAiTask, setActiveAiTask] = useState<ActiveAiTask | null>(null)
  const [activeServerRun, setActiveServerRun] = useState<AiRun | null>(
    routeData.record?.active_ai_runs?.[0] ?? null,
  )
  const [aiTaskFeedback, setAiTaskFeedback] = useState<AiTaskFeedback | null>(null)
  const [skipConfirmOpen, setSkipConfirmOpen] = useState(false)
  const [skipError, setSkipError] = useState('')
  const [skipTrigger, setSkipTrigger] = useState<HTMLButtonElement | null>(null)
  const [newMistakeExerciseId, setNewMistakeExerciseId] = useState<number | null>(null)
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
        record.exercises.map((item) => `${item.id}:${(item.items ?? []).map((question) => question.id).join('.')}:${item.mistakes.map((mistake) => mistake.id).join('.')}`).join(','),
        record.preview_question_set?.id ?? '',
        (record.materials ?? []).map((material) => material.id).join(','),
        newMistakeExerciseId ?? '',
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

  const activeServerRunId = activeServerRun?.id
  const recordId = record?.id
  useEffect(() => {
    if (!recordId || (!activeAiTask && !activeServerRunId)) return
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
        setActiveServerRun(runs[0] ?? null)
        if (runs.length > 0 || activeAiTask) timer = window.setTimeout(poll, 1500)
      } catch {
        if (!disposed && (activeServerRunId || activeAiTask)) timer = window.setTimeout(poll, 5000)
      }
    }
    timer = window.setTimeout(poll, activeAiTask ? 500 : 1500)
    return () => {
      disposed = true
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [recordId, activeAiTask, activeServerRunId])

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

  function requestMistakeDraftState(nextExerciseId: number | null, trigger: HTMLButtonElement) {
    if (newMistakeExerciseId === null) {
      setNewMistakeExerciseId(nextExerciseId)
      return
    }
    const currentKey = `mistake-new-${newMistakeExerciseId}`
    if (dirtyFormKeys.has(currentKey)) {
      setMistakeDraftDiscard({
        currentExerciseId: newMistakeExerciseId,
        nextExerciseId,
        trigger,
      })
      return
    }
    clearDirtyFormKey(currentKey)
    setNewMistakeExerciseId(nextExerciseId)
  }

  function discardMistakeDraft() {
    if (!mistakeDraftDiscard) return
    clearDirtyFormKey(`mistake-new-${mistakeDraftDiscard.currentExerciseId}`)
    setNewMistakeExerciseId(mistakeDraftDiscard.nextExerciseId)
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
      case 'preview':
        await api.savePreviewQuestions(record.id, {
          question_1: String(data.get('question_1') ?? ''),
          question_2: String(data.get('question_2') ?? ''),
          question_3: String(data.get('question_3') ?? ''),
        })
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

  async function generateInteraction(kind: AiInteractionKind) {
    if (!record) return
    setBusy(true)
    setActiveAiTask({
      key: kind,
      label: kind === 'recall_review' ? '正在评阅闭卷回顾' : '正在检查主动重构',
    })
    setAiTaskFeedback(null)
    setError('')
    setNotice('')
    try {
      const interaction = await api.generateAiReview(record.id, kind)
      setRecord({ ...record, ai_interactions: [...record.ai_interactions, interaction] })
      await refreshSourceReferences()
      setAiTaskFeedback({ key: kind, message: '评阅结果已生成', tone: 'success' })
    } catch (requestError) {
      setAiTaskFeedback({
        key: kind,
        message: requestError instanceof Error ? requestError.message : '评阅失败',
        tone: 'error',
      })
    } finally {
      setActiveAiTask(null)
      setBusy(false)
    }
  }

  async function saveInteractionFeedback(
    event: FormEvent<HTMLFormElement>,
    interactionId: number,
  ) {
    event.preventDefault()
    if (!record) return
    const form = event.currentTarget
    const feedback = String(new FormData(form).get('feedback_text') ?? '')
    const updated = await api.updateAiInteraction(interactionId, feedback)
    setRecord({
      ...record,
      ai_interactions: record.ai_interactions.map((item) =>
        item.id === updated.id ? updated : item
      ),
    })
    markFormSaved(form)
    setNotice('反馈已保存')
  }

  async function copyText(text: string) {
    await navigator.clipboard.writeText(text)
    setNotice('已复制到剪贴板')
  }

  async function createExercise() {
    if (!record) return
    setBusy(true)
    setActiveAiTask({ key: 'practice', label: '正在生成练习题' })
    setAiTaskFeedback(null)
    setError('')
    setNotice('')
    try {
      const exercise = await api.generateAiPractice(record.id)
      setRecord({ ...record, exercises: [...record.exercises, exercise] })
      setActiveExerciseItemPosition(1)
      await refreshSourceReferences()
      setAiTaskFeedback({ key: 'practice', message: '练习题已生成', tone: 'success' })
    } catch (requestError) {
      setAiTaskFeedback({
        key: 'practice',
        message: requestError instanceof Error ? requestError.message : '生成练习题失败',
        tone: 'error',
      })
    } finally {
      setActiveAiTask(null)
      setBusy(false)
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
    if (!record) return
    setRecord({
      ...record,
      exercises: record.exercises.map((item) => item.id === updated.id ? updated : item),
    })
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
      setRecord(refreshed)
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
    setBusy(true)
    setActiveAiTask({ key: 'grading', label: '正在批改练习答案' })
    setAiTaskFeedback(null)
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
        const reviewNode = latestRecord.workflow_nodes.find((node) => node.node_key === 'review')
        if (reviewNode) applyUpdatedNode(latestRecord, reviewNode)
        else setRecord(latestRecord)
      }
      setAiTaskFeedback({ key: 'grading', message: '批改结果已生成', tone: 'success' })
    } catch (requestError) {
      setAiTaskFeedback({
        key: 'grading',
        message: requestError instanceof Error ? requestError.message : '批改失败',
        tone: 'error',
      })
    } finally {
      setActiveAiTask(null)
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
      setNewMistakeExerciseId(null)
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
    setBusy(true)
    setActiveAiTask({ key: 'preview_questions', label: '正在生成预习问题' })
    setAiTaskFeedback(null)
    setError('')
    setNotice('')
    try {
      const previewQuestionSet = await api.generateAiPreviewQuestions(record.id)
      setRecord({ ...record, preview_question_set: previewQuestionSet })
      await refreshSourceReferences()
      setAiTaskFeedback({
        key: 'preview_questions',
        message: '预习问题已生成',
        tone: 'success',
      })
    } catch (requestError) {
      setAiTaskFeedback({
        key: 'preview_questions',
        message: requestError instanceof Error ? requestError.message : '生成预习问题失败',
        tone: 'error',
      })
    } finally {
      setActiveAiTask(null)
      setBusy(false)
    }
  }

  async function persistPreviewQuestions(form: HTMLFormElement) {
    if (!record) return '当前学习记录不可保存'
    const data = new FormData(form)
    setBusy(true)
    setError('')
    try {
      const previewQuestionSet = await api.savePreviewQuestions(record.id, {
        question_1: String(data.get('question_1') ?? ''),
        question_2: String(data.get('question_2') ?? ''),
        question_3: String(data.get('question_3') ?? ''),
      })
      const updatedRecord = { ...record, preview_question_set: previewQuestionSet }
      setRecord(updatedRecord)
      markFormSaved(form)
      setNotice('3 条衔接问题已保存')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '保存预习问题失败'
      setError(message)
      return message
    } finally {
      setBusy(false)
    }
  }

  async function savePreviewQuestions(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const incompleteLabels = incompleteFields(form, completionFields.preview_questions)
    if (incompleteLabels.length > 0) {
      setError(`请先完成：${incompleteLabels.join('、')}`)
      return
    }
    await persistPreviewQuestions(form)
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
    setActiveAiTask({ key: 'daily_summary', label: '正在整理今日摘要与学习记忆' })
    setError('')
    try {
      setRecord(await api.completeDailyRecord(record.id))
      setExpandedNodeIds(new Set())
      setNotice('今日学习已完成')
      return null
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '完成今日学习失败'
      setError(message)
      return message
    } finally {
      setActiveAiTask(null)
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
  const latestInteraction = (kind: AiInteractionKind) =>
    record.ai_interactions.filter((item) => item.kind === kind).at(-1)
  const recallInteraction = latestInteraction('recall_review')
  const reconstructionInteraction = latestInteraction('reconstruction_review')
  const exercise = record.exercises.at(-1)
  const structuredItems = exercise?.format_version === 2 ? (exercise.items ?? []) : []
  const activeExerciseItem = structuredItems.find(
    (item) => item.position === activeExerciseItemPosition,
  ) ?? structuredItems[0]
  const activeReviewItem = structuredItems.find(
    (item) => item.position === activeReviewItemPosition,
  ) ?? structuredItems[0]
  const answeredExerciseItems = structuredItems.filter((item) => (
    Boolean(item.response?.answer_markdown.trim())
    || Boolean(item.response?.selected_options.length)
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
    if (activeAiTask?.key === key) {
      const matchingRun = activeServerRun?.task === 'material_context'
        || activeServerRun?.task === aiTaskRunKeys[key]
        ? activeServerRun
        : null
      return (
        <AiTaskStatus
          key={key}
          label={activeAiTask.label}
          phase={aiRunPhase(matchingRun)}
          startedAt={matchingRun?.created_at}
        />
      )
    }
    if (aiTaskFeedback?.key !== key) return null
    const reconnectRequired = aiTaskFeedback.message.includes('重新连接 Codex')
      || aiTaskFeedback.message.includes('登录已失效')
    return (
      <div
        className={`ai-task-feedback ai-task-feedback--${aiTaskFeedback.tone}`}
        role={aiTaskFeedback.tone === 'error' ? 'alert' : 'status'}
      >
        <span>{aiTaskFeedback.message}</span>
        {reconnectRequired && <Link className="text-button" to="/settings">前往设置</Link>}
      </div>
    )
  }

  const aiReviewPanel = (
    kind: AiInteractionKind,
    interaction: typeof recallInteraction,
    buttonLabel: string,
    feedbackDescription: string,
  ) => (
    <div className="ai-workspace">
      <button className="secondary-button" type="button" disabled={busy} onClick={() => generateInteraction(kind)}>
        <Sparkles size={16} />{activeAiTask?.key === kind ? '生成中' : interaction ? '重新评阅' : buttonLabel}
      </button>
      {aiTaskState(kind)}
      {interaction && (
        <>
          <details className="prompt-details">
            <summary>查看本次提示词</summary>
            <div className="prompt-toolbar">
              <strong>评阅提示词</strong>
              <button className="icon-button" type="button" title="复制提示词" aria-label="复制提示词" onClick={() => copyText(interaction.prompt_text)}><Clipboard size={16} /></button>
            </div>
            <textarea className="prompt-output" readOnly rows={10} value={interaction.prompt_text} />
          </details>
          <form
            className="stack-form"
            data-dirty-key={`interaction-${interaction.id}`}
            data-save-kind="interaction"
            data-entity-id={interaction.id}
            onSubmit={(event) => saveInteractionFeedback(event, interaction.id)}
          >
            <EditableMarkdown title="评阅反馈" description={feedbackDescription} name="feedback_text" rows={14} defaultValue={interaction.feedback_text} />
            <button className="secondary-button" type="submit"><Save size={15} />保存反馈</button>
          </form>
        </>
      )}
    </div>
  )

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
      {!activeAiTask && activeServerRun && (
        <AiTaskStatus
          label="正在继续上次的生成任务"
          phase={aiRunPhase(activeServerRun)}
          startedAt={activeServerRun.created_at}
          recovered
        />
      )}
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
            <aside className="previous-preview" aria-label="上次留下的预习问题">
              <div><strong>上次留下的预习问题</strong><span>{record.previous_preview_questions.study_date}</span></div>
              <ol>{record.previous_preview_questions.questions.map((question) => <li key={question}>{question}</li>)}</ol>
            </aside>
          )}
          <form className="node-form" data-dirty-key="content-recall" data-save-kind="content" onSubmit={(event) => saveContent(event, 'recall')}>
            <FieldLabel title="相关知识" description="回忆上次学习、前一小节或当前内容需要的先修知识"><textarea name="recall_last_learned" rows={3} defaultValue={record.recall_last_learned} /></FieldLabel>
            <FieldLabel title="核心概念" description="写下仍能记得的关键概念"><textarea name="recall_core_concepts" rows={3} defaultValue={record.recall_core_concepts} /></FieldLabel>
            <FieldLabel title="清晰部分" description="哪些内容还能完整说明"><textarea name="recall_clear_parts" rows={3} defaultValue={record.recall_clear_parts} /></FieldLabel>
            <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存</button><button className="primary-button" type="submit" data-complete="true" disabled={busy}><Check size={15} />保存并完成</button></div>
          </form>
          {record.previous_records.length > 0 && (
            <details className="previous-records">
              <summary>回忆后核对最近记录</summary>
              {record.previous_records.map((item) => (
                <div key={item.id}><strong>{item.study_date}</strong><p>{item.reconstruct_main_learning || item.recall_last_learned || '未填写摘要'}</p></div>
              ))}
            </details>
          )}
          {aiReviewPanel('recall_review', recallInteraction, '评阅回顾', '可继续编辑并保存本次评阅结果')}
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
          <form className="node-form" data-dirty-key="content-reconstruct" data-save-kind="content" onSubmit={(event) => saveContent(event, 'reconstruct')}>
            <FieldLabel title="问题与目标" description="这部分内容主要解决什么问题"><textarea name="reconstruct_problem" rows={3} defaultValue={record.reconstruct_problem} /></FieldLabel>
            <FieldLabel title="主要内容" description="用自己的语言概括本次学到的内容"><textarea name="reconstruct_main_learning" rows={4} defaultValue={record.reconstruct_main_learning} /></FieldLabel>
            <FieldLabel title="定义与推导" description="记录关键定义、公式和推导过程"><textarea name="reconstruct_math" rows={5} defaultValue={record.reconstruct_math} /></FieldLabel>
            <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存</button><button className="primary-button" type="submit" data-complete="true" disabled={busy}><Check size={15} />保存并完成</button></div>
          </form>
          {aiReviewPanel('reconstruction_review', reconstructionInteraction, '检查重构', '可继续编辑并保存本次检查结果')}
        </FlowNode>

        <FlowNode {...flowNodeProps('practice')}>
          <div className="node-actions-line">
            <div className="node-action-group">
              <button className="secondary-button" type="button" disabled={busy} onClick={createExercise}><Sparkles size={16} />{activeAiTask?.key === 'practice' ? '生成中' : exercise ? '生成新一组练习' : '生成练习'}</button>
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
                      <FieldLabel title="我的作答" description="写出完整思路、计算或推导过程">
                        <textarea name="answer_markdown" rows={12} defaultValue={activeExerciseItem.response?.answer_markdown ?? ''} />
                      </FieldLabel>
                    )}
                    {activeExerciseItem.options.length > 0 && <input type="hidden" name="answer_markdown" value="" />}
                    {activeExerciseItem.source_refs.length > 0 && <p className="exercise-source">依据：{activeExerciseItem.source_refs.join('；')}</p>}
                    {activeExerciseItem.response?.feedback_markdown && (
                      <div className={`exercise-item-feedback exercise-item-feedback--${activeExerciseItem.response.verdict}`}>
                        <div><strong>本题反馈</strong><span>{exerciseVerdictLabels[activeExerciseItem.response.verdict] ?? '已批改'}</span></div>
                        <MarkdownContent content={activeExerciseItem.response.feedback_markdown} />
                      </div>
                    )}
                    <div className="exercise-question-footer">
                      <button className="secondary-button" type="button" disabled={busy || activeExerciseItem.position === 1} onClick={() => void moveExerciseItem(activeExerciseItem.position - 1, activeExerciseItem.id)}><ChevronLeft size={16} />上一题</button>
                      <span>已作答 {answeredExerciseItems}/{structuredItems.length}</span>
                      <button className="secondary-button" type="button" disabled={busy || activeExerciseItem.position === structuredItems.length} onClick={() => void moveExerciseItem(activeExerciseItem.position + 1, activeExerciseItem.id)}>下一题<ChevronRight size={16} /></button>
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
              <button className="secondary-button" type="button" disabled={busy || (structuredItems.length > 0 && exercise.status === 'draft')} onClick={() => createGradingPrompt(exercise.id)}><Sparkles size={16} />{activeAiTask?.key === 'grading' ? '批改中' : exercise.ai_feedback ? '重新批改' : '批改答案'}</button>
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
                      {activeReviewItem.source_refs.length > 0 && <p className="exercise-source">依据：{activeReviewItem.source_refs.join('；')}</p>}
                      <div className="exercise-question-footer">
                        <button className="secondary-button" type="button" disabled={activeReviewItem.position === 1} onClick={() => setActiveReviewItemPosition(activeReviewItem.position - 1)}><ChevronLeft size={16} />上一题</button>
                        <span>逐题复核 {activeReviewItem.position}/{structuredItems.length}</span>
                        <button className="secondary-button" type="button" disabled={activeReviewItem.position === structuredItems.length} onClick={() => setActiveReviewItemPosition(activeReviewItem.position + 1)}>下一题<ChevronRight size={16} /></button>
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
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={(event) => {
                      if (newMistakeExerciseId !== exercise.id) {
                        const firstIncorrectItem = structuredItems.find((item) => (
                          item.response?.verdict === 'incorrect'
                          || item.response?.verdict === 'partial'
                        ))
                        if (firstIncorrectItem) {
                          setActiveExerciseItemPosition(firstIncorrectItem.position)
                        }
                      }
                      requestMistakeDraftState(
                        newMistakeExerciseId === exercise.id ? null : exercise.id,
                        event.currentTarget,
                      )
                    }}
                  ><Plus size={15} />整理一条错题</button>
                </div>
                {newMistakeExerciseId === exercise.id && (
                  <form
                    className="mistake-form"
                    data-dirty-key={`mistake-new-${exercise.id}`}
                    data-save-kind="mistake-create"
                    data-entity-id={exercise.id}
                    onSubmit={(event) => createMistake(event, exercise.id)}
                  >
                    <MistakeFields exerciseItem={activeExerciseItem} legacyQuestion={exercise.ai_questions} legacyAnswer={exercise.user_answers} />
                    <div className="form-actions"><button className="primary-button" type="submit" disabled={busy}><Save size={15} />保存错题</button><button className="text-button" type="button" onClick={(event) => requestMistakeDraftState(null, event.currentTarget)}>取消</button></div>
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
            </>
          ) : <p className="muted">尚未创建练习</p>}
        </FlowNode>

        <FlowNode {...flowNodeProps('daily_close')}>
          <button className="secondary-button" type="button" disabled={busy} onClick={generatePreviewPrompt}><Sparkles size={16} />{activeAiTask?.key === 'preview_questions' ? '生成中' : record.preview_question_set ? '重新生成问题' : '生成预习问题'}</button>
          {aiTaskState('preview_questions')}
          {record.preview_question_set && (
            <>
              <details className="prompt-details">
                <summary>查看本次预习提示词</summary>
                <div className="prompt-toolbar"><strong>预习问题提示词</strong><button className="icon-button" type="button" title="复制预习问题提示词" aria-label="复制预习问题提示词" onClick={() => copyText(record.preview_question_set?.prompt_text ?? '')}><Clipboard size={16} /></button></div>
                <textarea className="prompt-output" readOnly rows={12} value={record.preview_question_set.prompt_text} />
              </details>
              <form
                key={[
                  record.preview_question_set.prompt_text,
                  record.preview_question_set.question_1,
                  record.preview_question_set.question_2,
                  record.preview_question_set.question_3,
                ].join('|')}
                className="node-form preview-question-form"
                data-dirty-key={`preview-${record.id}`}
                data-save-kind="preview"
                onSubmit={savePreviewQuestions}
              >
                <div className="field-group-intro"><strong>三个预习问题</strong><span>为下次学习保留三个启动问题</span></div>
                <label>问题一<textarea name="question_1" rows={2} defaultValue={record.preview_question_set.question_1} /></label>
                <label>问题二<textarea name="question_2" rows={2} defaultValue={record.preview_question_set.question_2} /></label>
                <label>问题三<textarea name="question_3" rows={2} defaultValue={record.preview_question_set.question_3} /></label>
                <div className="form-actions"><button className="secondary-button" type="submit" disabled={busy}><Save size={15} />保存 3 条问题</button></div>
              </form>
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
