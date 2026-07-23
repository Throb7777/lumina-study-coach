import { useEffect, useState } from 'react'
import { Check, Clipboard, Edit3, Eye, Save, Sparkles } from 'lucide-react'
import { Link, useLoaderData, useLocation } from 'react-router-dom'
import { ApiError, api } from '../api'
import type { AiGeneratedText, AiRun, DailyRecord, MarkdownValidation, SectionNote } from '../api'
import { AppDialog } from '../components/AppDialog'
import { AiTaskStatus } from '../components/AiTaskStatus'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DraftStatus } from '../components/DraftStatus'
import { IncompleteCompletionDialog } from '../components/IncompleteCompletionDialog'
import { MarkdownContent } from '../components/MarkdownContent'
import { PageBackBar } from '../components/PageBackBar'
import { UnsavedChangesGuard } from '../components/UnsavedChangesGuard'
import { clearDraft, readDraft, writeDraft } from '../draftStorage'
import { hasLegacyMathDelimiters, normalizeMarkdownMath } from '../markdown'
import type { SectionNoteRouteData } from '../routeData'
import { useTransientNotice } from '../useTransientNotice'

export function SectionNotePage() {
  const routeData = useLoaderData() as SectionNoteRouteData
  const location = useLocation()
  const noteDraftKey = `section-note-${routeData.note?.section_id ?? routeData.record?.section_id ?? 'unknown'}`
  const noteRunKey = `${noteDraftKey}-active-run`
  const [restoredContent] = useState<string | null>(() => readDraft(noteDraftKey, routeData.note?.content ?? ''))
  const [record, setRecord] = useState<DailyRecord | null>(routeData.record)
  const [note, setNote] = useState<SectionNote | null>(routeData.note)
  const [content, setContent] = useState(restoredContent ?? routeData.note?.content ?? '')
  const [error, setError] = useState(routeData.error)
  const [notice, setNotice] = useTransientNotice()
  const [busy, setBusy] = useState(false)
  const [activeAiTask, setActiveAiTask] = useState('')
  const [activeServerRun, setActiveServerRun] = useState<AiRun | null>(
    routeData.record?.active_ai_runs?.find((run) => [
      'material_context',
      'section_note_draft',
      'section_note_polish',
    ].includes(run.task)) ?? null,
  )
  const [pendingDraftRunId, setPendingDraftRunId] = useState<number | null>(() => {
    const run = routeData.record?.active_ai_runs?.find((item) => item.task === 'section_note_draft')
    const stored = Number(window.localStorage.getItem(noteRunKey))
    return run?.id ?? (Number.isInteger(stored) && stored > 0 ? stored : null)
  })
  const [mobileView, setMobileView] = useState<'edit' | 'preview'>('edit')
  const [vaultMissing] = useState(routeData.vaultMissing)
  const [overwriteOpen, setOverwriteOpen] = useState(false)
  const [completeAfterOverwrite, setCompleteAfterOverwrite] = useState(false)
  const [incompleteOpen, setIncompleteOpen] = useState(false)
  const [incompleteTrigger, setIncompleteTrigger] = useState<HTMLButtonElement | null>(null)
  const [pendingDraft, setPendingDraft] = useState<AiGeneratedText | null>(null)
  const [aiOutputNeedsValidation, setAiOutputNeedsValidation] = useState(false)

  const activeServerRunId = activeServerRun?.id
  useEffect(() => {
    const sectionId = note?.section_id ?? record?.section_id
    if (!sectionId || (!activeAiTask && !activeServerRunId)) return
    let disposed = false
    let timer = 0
    const controller = new AbortController()
    const poll = async () => {
      try {
        const runs = await api.listAiRuns({ section_id: sectionId }, true, controller.signal)
        if (disposed) return
        const noteRun = runs.find((run) => [
          'material_context',
          'section_note_draft',
          'section_note_polish',
        ].includes(run.task)) ?? null
        setActiveServerRun(noteRun)
        if (noteRun || activeAiTask) timer = window.setTimeout(poll, 1500)
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
  }, [activeAiTask, activeServerRunId, note?.section_id, record?.section_id])

  useEffect(() => {
    if (pendingDraftRunId) window.localStorage.setItem(noteRunKey, String(pendingDraftRunId))
    else window.localStorage.removeItem(noteRunKey)
  }, [noteRunKey, pendingDraftRunId])

  useEffect(() => {
    if (!pendingDraftRunId || pendingDraft) return
    let disposed = false
    let timer = 0
    const controller = new AbortController()
    const pollResult = async () => {
      try {
        const payload = await api.getAiRunResult(pendingDraftRunId, controller.signal)
        if (disposed) return
        setActiveServerRun(payload.run.status === 'running' ? payload.run : null)
        if (payload.run.status === 'completed' && payload.result) {
          setPendingDraft(payload.result)
          setNotice('笔记初稿已生成，请检查后应用')
          return
        }
        if (payload.run.status === 'failed') {
          setError(payload.run.error_text || '生成笔记初稿失败')
          setPendingDraftRunId(null)
          return
        }
        timer = window.setTimeout(pollResult, 1500)
      } catch (requestError) {
        if (!disposed) {
          if (requestError instanceof ApiError && requestError.status === 404) {
            setError('笔记生成任务不存在，请重新生成')
            setPendingDraftRunId(null)
          } else {
            timer = window.setTimeout(pollResult, 5000)
          }
        }
      }
    }
    void pollResult()
    return () => {
      disposed = true
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [pendingDraft, pendingDraftRunId, setNotice])

  async function cancelActiveAiTask() {
    if (!activeServerRun) return
    try {
      await api.cancelAiRun(activeServerRun.id)
      setActiveServerRun(null)
      setActiveAiTask('')
      setPendingDraftRunId(null)
      setNotice('生成任务已取消，可以从原操作重新生成')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '取消生成失败')
    }
  }

  const [pendingValidation, setPendingValidation] = useState<{
    result: MarkdownValidation
    complete: boolean
    forceOverwrite: boolean
    showConflictDialog: boolean
  } | null>(null)

  useEffect(() => {
    const baseline = note?.content ?? ''
    if (content === baseline) clearDraft(noteDraftKey)
    else writeDraft(noteDraftKey, baseline, content)
  }, [content, note?.content, noteDraftKey])

  async function copyText(text: string) {
    await navigator.clipboard.writeText(text)
    setNotice('已复制到剪贴板')
  }

  async function generatePrompt() {
    if (!record) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const mode = content.trim() ? 'revise' : 'create'
      const prompt = await api.createSectionNotePrompt(record.id, content, mode)
      setRecord({ ...record, section_note_prompt: prompt })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '生成整理提示词失败')
    } finally {
      setBusy(false)
    }
  }

  async function generateDraft() {
    if (!record) return
    setBusy(true)
    setActiveAiTask('正在生成笔记初稿')
    setError('')
    setNotice('')
    try {
      const mode = content.trim() ? 'revise' : 'create'
      const run = await api.startAiSectionNote(record.id, content, mode)
      setActiveServerRun(run)
      setPendingDraftRunId(run.id)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '生成笔记初稿失败')
    } finally {
      setActiveAiTask('')
      setBusy(false)
    }
  }

  async function polishDraft() {
    if (!note || !content.trim()) return
    setBusy(true)
    setActiveAiTask('正在润色笔记')
    setError('')
    setNotice('')
    try {
      const result = await api.polishSectionNote(note.section_id, content)
      setContent(result.text)
      setAiOutputNeedsValidation(true)
      setNotice('Gemini 润色已完成，请检查后保存')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Gemini 润色失败')
    } finally {
      setActiveAiTask('')
      setBusy(false)
    }
  }

  async function persistNote(
    complete: boolean,
    forceOverwrite = false,
    showConflictDialog = true,
    validatedContent?: string,
  ) {
    if (!note) return '当前笔记不可保存'
    setBusy(true)
    setError('')
    try {
      let contentToSave = validatedContent ?? (content.trim() ? content : '')
      if (validatedContent === undefined && contentToSave && aiOutputNeedsValidation) {
        const validation = await api.validateMarkdown(contentToSave)
        contentToSave = validation.normalized_content
        if (validation.issues.length > 0) {
          setPendingValidation({
            result: validation,
            complete,
            forceOverwrite,
            showConflictDialog,
          })
          return '笔记格式需要确认'
        }
      }
      const saved = await api.saveSectionNote(
        note.section_id,
        contentToSave,
        note.modified_at_ns,
        forceOverwrite,
      )
      setNote(saved)
      setContent(saved.content)
      setAiOutputNeedsValidation(false)
      if (complete && record) {
        await api.updateSection(record.section_id, { status: 'completed' })
      }
      setOverwriteOpen(false)
      setNotice(complete ? '笔记已保存，小节已完成' : '笔记已保存到 Obsidian')
      return ''
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 409) {
        if (showConflictDialog) {
          setCompleteAfterOverwrite(complete)
          setOverwriteOpen(true)
        }
        return 'Obsidian 文件已在外部修改，请先留在当前页面处理覆盖确认'
      } else {
        const message = requestError instanceof Error ? requestError.message : '保存笔记失败'
        setError(message)
        return message
      }
    } finally {
      setBusy(false)
    }
  }

  function requestNoteCompletion(trigger: HTMLButtonElement) {
    if (content.trim()) {
      void persistNote(true)
      return
    }
    setError('')
    setIncompleteTrigger(trigger)
    setIncompleteOpen(true)
  }

  async function confirmIncompleteNote() {
    setIncompleteOpen(false)
    await persistNote(true)
  }

  const returnTarget = routeData.mode === 'workflow'
    ? record ? `/daily-records/${record.id}` : '/courses'
    : `/notes${location.search}`

  if (!note && !vaultMissing) {
    return (
      <main className="context-page note-page">
        <PageBackBar ariaLabel="笔记导航" to={returnTarget} />
        <div className="content content--wide context-page__content">
          <p className="error-banner" role="alert">
            {routeData.notFound
              ? routeData.mode === 'workflow' ? '学习记录或小节不存在' : '笔记或小节不存在'
              : error}
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="context-page note-page">
      <PageBackBar ariaLabel="笔记导航" to={returnTarget} />
      <div className="content content--wide context-page__content">
        <header className="note-toolbar">
          <div><p className="eyebrow">{record?.section_title ?? '小节笔记'}</p><h1>{note?.file_name ?? '小节笔记'}</h1><p>{note?.relative_path ?? '尚未配置 Obsidian 路径'}</p></div>
          <div className="note-toolbar__actions">
            <span className={content === note?.content ? 'save-state' : 'save-state save-state--dirty'}>{content === note?.content ? '已保存' : '未保存'}</span>
            <button className="secondary-button" type="button" disabled={busy || !note} onClick={() => persistNote(false)}><Save size={15} />保存到 Obsidian</button>
            {record && <button className="primary-button" type="button" disabled={busy || !note} onClick={(event) => requestNoteCompletion(event.currentTarget)}><Check size={15} />保存并完成小节</button>}
          </div>
        </header>
        <DraftStatus
          dirtyCount={0}
          recoveredLabel={restoredContent === null ? undefined : '已恢复上次笔记草稿'}
        />
        {error && <p className="error-banner" role="alert">{error}</p>}
        {notice && <p className="notice-banner" role="status">{notice}</p>}
        {(activeAiTask || activeServerRun) && (
          <AiTaskStatus
            key={activeAiTask || activeServerRun?.id}
            label={activeAiTask || '正在继续上次的笔记任务'}
            phase={activeServerRun?.task === 'material_context'
              ? '正在完整读取本节材料'
              : `正在等待 ${activeServerRun?.provider === 'gemini' ? 'Gemini' : 'Codex'} 生成结果`}
            startedAt={activeServerRun?.created_at}
            recovered={!activeAiTask}
            onCancel={activeServerRun ? cancelActiveAiTask : undefined}
          />
        )}
        {vaultMissing && <p><Link className="primary-button inline-link-button" to="/settings">配置 Obsidian 路径</Link></p>}
        {record && (
          <section className="note-prompt-panel">
            <div className="note-ai-actions">
              <button className="primary-button" type="button" disabled={busy || pendingDraftRunId !== null} onClick={generateDraft}><Sparkles size={15} />{pendingDraftRunId !== null || activeAiTask === '正在生成笔记初稿' ? '生成中' : content.trim() ? 'GPT 修订笔记' : 'GPT 生成初稿'}</button>
              <button className="secondary-button" type="button" disabled={busy || !content.trim()} onClick={polishDraft}><Sparkles size={15} />{activeAiTask === '正在润色笔记' ? '润色中' : 'Gemini 润色'}</button>
              <button className="text-button" type="button" disabled={busy} onClick={generatePrompt}>{record.section_note_prompt ? '更新手动提示词' : '查看手动提示词'}</button>
            </div>
            {record.section_note_prompt && <details className="note-prompt-details"><summary>查看整理提示词</summary><div className="prompt-toolbar"><strong>整理提示词</strong><button className="icon-button" type="button" title="复制整理提示词" aria-label="复制整理提示词" onClick={() => copyText(record.section_note_prompt?.prompt_text ?? '')}><Clipboard size={16} /></button></div><textarea className="prompt-output" readOnly rows={10} value={record.section_note_prompt.prompt_text} /></details>}
          </section>
        )}
        {hasLegacyMathDelimiters(content) && (
          <div className="note-format-notice" role="status">
            <span><strong>检测到旧公式格式</strong><small>转换后可在 Web 和 Obsidian 中一致显示</small></span>
            <button className="secondary-button" type="button" onClick={() => setContent(normalizeMarkdownMath(content))}>转换公式格式</button>
          </div>
        )}
        <div className="note-view-tabs segmented-control" role="group" aria-label="笔记视图">
          <button type="button" aria-pressed={mobileView === 'edit'} onClick={() => setMobileView('edit')}><Edit3 size={14} />编辑</button>
          <button type="button" aria-pressed={mobileView === 'preview'} onClick={() => setMobileView('preview')}><Eye size={14} />预览</button>
        </div>
        <section className="note-workspace">
          <label className={`note-editor note-pane--${mobileView === 'edit' ? 'active' : 'inactive'}`}><span className="field-label-copy"><strong>笔记正文</strong><span>编辑并保存本小节的 Markdown 笔记</span></span><textarea aria-label="Markdown 笔记" value={content} disabled={!note} onChange={(event) => setContent(event.target.value)} /></label>
          <div className={`note-preview note-pane--${mobileView === 'preview' ? 'active' : 'inactive'}`}><span>预览</span><div className="note-preview__content"><MarkdownContent content={content} /></div></div>
        </section>
      </div>
      <ConfirmDialog
        open={overwriteOpen}
        title="覆盖外部修改？"
        description="这份笔记在 Web 打开后已被 Obsidian 或其他程序修改。继续会用当前编辑器内容覆盖文件。"
        confirmLabel="确认覆盖"
        variant="warning"
        busy={busy}
        onCancel={() => setOverwriteOpen(false)}
        onConfirm={async () => {
          await persistNote(completeAfterOverwrite, true, true, content)
        }}
      />
      <AppDialog
        open={pendingValidation !== null}
        title="保存前检查"
        description="检测到可能影响 Web 与 Obsidian 阅读的格式问题。"
        size="small"
        closeOnBackdrop={false}
        onClose={() => setPendingValidation(null)}
        footer={pendingValidation ? (
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={() => setPendingValidation(null)}>继续修改</button>
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                const pending = pendingValidation
                setPendingValidation(null)
                setContent(pending.result.normalized_content)
                void persistNote(
                  pending.complete,
                  pending.forceOverwrite,
                  pending.showConflictDialog,
                  pending.result.normalized_content,
                )
              }}
            >
              应用修正并保存
            </button>
          </div>
        ) : null}
      >
        {pendingValidation && (
          <ul className="validation-issue-list">
            {pendingValidation.result.issues.map((issue, index) => (
              <li key={`${issue.code}-${index}`}>
                {issue.line ? `第 ${issue.line} 行：` : ''}{issue.message}
              </li>
            ))}
          </ul>
        )}
      </AppDialog>
      <IncompleteCompletionDialog
        open={incompleteOpen}
        incompleteLabels={['笔记正文']}
        busy={busy}
        returnFocusTo={incompleteTrigger}
        onCancel={() => {
          if (busy) return
          setIncompleteOpen(false)
        }}
        onConfirm={confirmIncompleteNote}
      />
      <AppDialog
        open={pendingDraft !== null}
        title={content.trim() ? '预览修订结果' : '预览笔记初稿'}
        description="确认后才会替换编辑器内容，当前笔记不会自动覆盖。"
        size="large"
        closeOnBackdrop={false}
        onClose={() => {
          setPendingDraft(null)
          setPendingDraftRunId(null)
        }}
        footer={(
          <>
            <button className="secondary-button" type="button" onClick={() => {
              setPendingDraft(null)
              setPendingDraftRunId(null)
            }}>取消</button>
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                if (pendingDraft === null) return
                setContent(pendingDraft.text)
                setAiOutputNeedsValidation(true)
                setPendingDraft(null)
                setPendingDraftRunId(null)
                setNotice('已应用生成结果，请检查后保存')
              }}
            >
              应用到编辑器
            </button>
          </>
        )}
      >
        <div className="generated-note-preview">
          {pendingDraft && pendingDraft.material_revision > 0 && (
            <p className="generated-note-preview__meta">
              基于本小节材料版本 {pendingDraft.material_revision}
            </p>
          )}
          <MarkdownContent content={pendingDraft?.text ?? ''} />
        </div>
      </AppDialog>
      <UnsavedChangesGuard
        dirty={content !== note?.content}
        onDiscard={() => clearDraft(noteDraftKey)}
        onSave={async () => {
          const saveError = await persistNote(false, false, false)
          if (saveError) throw new Error(saveError)
        }}
      />
    </main>
  )
}
