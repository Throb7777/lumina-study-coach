import type {
  AiInteractionKind,
  AiRun,
  MistakeType,
  WorkflowNode,
  WorkflowNodeStatus,
} from '../api'

export const statusLabels: Record<WorkflowNodeStatus, string> = {
  pending: '未完成',
  completed: '已完成',
  skipped: '已跳过',
}

export const mistakeTypeLabels: Record<MistakeType, string> = {
  concept: '概念理解错误',
  formula_condition: '公式适用条件错误',
  derivation: '推导步骤错误',
  calculation: '计算错误',
  question_understanding: '题意理解错误',
  expression: '表达不清',
  cannot_solve: '不会做',
  other: '其他',
}

export const exerciseTypeLabels: Record<string, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  short_answer: '概念简答',
  derivation: '推导题',
  proof: '证明题',
  calculation: '计算题',
  application: '应用题',
  extension: '思维延伸',
}

export const exerciseDifficultyLabels: Record<string, string> = {
  basic: '基础',
  intermediate: '中等',
  challenge: '挑战',
}

export const exerciseVerdictLabels: Record<string, string> = {
  correct: '正确',
  partial: '部分正确',
  incorrect: '错误',
}

export const nodeDescriptions: Record<string, string> = {
  recall: '不看材料，回顾与本次学习相关的已有知识',
  study: '完成本次课程、教材或论文阅读',
  reconstruct: '合上材料，用自己的语言重建内容',
  practice: '根据题目独立完成作答或推导',
  review: '对照反馈，定位并修正错误',
  daily_close: '生成下次回顾问题并结束今天的学习',
  preview_questions: '为同一课程的下一次学习留下三个回顾问题',
  section_note: '整理并保存本小节的学习成果',
  daily_complete: '确认并结束今天的学习记录',
}

export const nodeTitles: Record<string, string> = {
  recall: '闭卷回顾',
  study: '材料学习',
  reconstruct: '主动重构',
  practice: '练习与推导',
  review: '批改与纠错',
  daily_close: '今日收尾',
  preview_questions: '下次回顾问题',
  section_note: '小节笔记',
  daily_complete: '完成今日学习',
}

export const completionFields: Record<string, Array<[name: string, label: string]>> = {
  recall: [
    ['recall_last_learned', '自由回忆'],
  ],
  study: [['study_material_scope', '学习范围']],
  reconstruct: [
    ['reconstruct_main_learning', '自由重构'],
  ],
  practice: [
    ['ai_questions', '练习题目'],
    ['user_answers', '我的作答'],
  ],
  review: [['ai_feedback', '批改反馈']],
  preview_questions: [
    ['question_1', '问题一'],
    ['question_2', '问题二'],
    ['question_3', '问题三'],
  ],
  daily_close: [
    ['question_1', '问题一'],
    ['question_2', '问题二'],
    ['question_3', '问题三'],
  ],
}

export function incompleteFields(
  form: HTMLFormElement,
  fields: Array<[name: string, label: string]>,
) {
  const data = new FormData(form)
  return fields
    .filter(([name]) => !String(data.get(name) ?? '').trim())
    .map(([, label]) => label)
}

export interface MistakeDraftDiscardAction {
  currentItemId: number
  nextItemId: number | null
  trigger: HTMLButtonElement
}

export interface PendingCompletionAction {
  confirmLabel: string
  incompleteLabels: string[]
  onConfirm: () => Promise<string | null>
  trigger: HTMLElement
}

export type AiTaskKey =
  | AiInteractionKind
  | 'recall_questions'
  | 'reconstruction_questions'
  | 'practice'
  | 'grading'
  | 'preview_questions'
  | 'daily_summary'

export interface ActiveAiTask {
  key: AiTaskKey
  label: string
}

export interface AiTaskFeedback {
  key: AiTaskKey
  message: string
  tone: 'success' | 'error'
}

export const aiTaskRunKeys: Record<AiTaskKey, AiRun['task']> = {
  recall_questions: 'recall_questions',
  recall_review: 'recall_review',
  reconstruction_questions: 'reconstruction_questions',
  reconstruction_review: 'reconstruction_review',
  practice: 'practice_generation',
  grading: 'exercise_grading',
  preview_questions: 'preview_questions',
  daily_summary: 'daily_summary',
}

export function aiRunPhase(run: AiRun | null) {
  if (!run) return '正在准备上下文'
  if (run.task === 'material_context') return '正在完整读取本节材料'
  return `正在等待 ${run.provider === 'gemini' ? 'Gemini' : 'Codex'} 生成结果`
}

export const sourceTaskLabels: Record<string, string> = {
  recall_questions: '回顾定向问题',
  recall_review: '回顾评阅',
  reconstruction_questions: '重构定向问题',
  reconstruction_review: '重构检查',
  practice_generation: '练习生成',
  exercise_grading: '练习批改',
  preview_questions: '下次回顾问题',
  section_note_draft: '笔记整理',
  daily_summary: '今日摘要',
}

export function firstPendingNodeId(nodes: WorkflowNode[], afterPosition = 0) {
  const orderedNodes = [...nodes].sort((left, right) => left.position - right.position)
  return orderedNodes.find((node) => node.status === 'pending' && node.position > afterPosition)?.id
    ?? orderedNodes.find((node) => node.status === 'pending')?.id
    ?? null
}
