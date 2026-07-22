import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  FileText,
  Link as LinkIcon,
  Plus,
  RefreshCw,
  Star,
  Trash2,
  Upload,
  Video,
} from 'lucide-react'
import { api } from '../api'
import type { LearningMaterial, MaterialScopePayload } from '../api'
import { AppDialog } from './AppDialog'
import { TwoStepDeleteDialog } from './TwoStepDeleteDialog'

export interface MaterialScopeOption extends MaterialScopePayload {
  label: string
  value: string
}

interface MaterialLibraryProps {
  materials: LearningMaterial[]
  scopeOptions?: MaterialScopeOption[]
  defaultScope?: string
  allowAdd?: boolean
  allowScopeEdit?: boolean
  showScopeSelect?: boolean
  showCourse?: boolean
  onChanged?: () => void | Promise<void>
}

export function MaterialLibrary({
  materials: sourceMaterials,
  scopeOptions = [],
  defaultScope,
  allowAdd = true,
  allowScopeEdit = true,
  showScopeSelect = true,
  showCourse = false,
  onChanged,
}: MaterialLibraryProps) {
  const materials = Array.isArray(sourceMaterials) ? sourceMaterials : []
  const [dialogOpen, setDialogOpen] = useState(false)
  const [sourceType, setSourceType] = useState<'pdf' | 'url'>('pdf')
  const [scopeValue, setScopeValue] = useState(defaultScope ?? scopeOptions[0]?.value ?? '')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<LearningMaterial | null>(null)
  const [deleteTrigger, setDeleteTrigger] = useState<HTMLButtonElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function scopeFor(value: string) {
    return scopeOptions.find((option) => option.value === value)
  }

  function scopeLabel(material: LearningMaterial) {
    if (material.section_id) return material.section_title
    if (material.chapter_id) return material.chapter_title
    return '整个课程'
  }

  async function notifyChanged() {
    await onChanged?.()
  }

  async function createMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const scope = scopeFor(scopeValue)
    if (!scope) {
      setError('请选择材料可用范围')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const title = String(data.get('title') ?? '').trim()
      if (sourceType === 'pdf' && (!selectedFile || selectedFile.size === 0)) {
        setError('请选择 PDF 文件')
        return
      }
      const created = sourceType === 'pdf'
        ? await api.createPdfMaterial(
            title,
            selectedFile as File,
            { ...scope, is_primary: false },
          )
        : await api.createUrlMaterial({
            title,
            url: String(data.get('url') ?? '').trim(),
            course_id: scope.course_id,
            chapter_id: scope.chapter_id,
            section_id: scope.section_id,
            is_primary: false,
          })
      void created
      setDialogOpen(false)
      setSelectedFile(null)
      form.reset()
      await notifyChanged()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '添加材料失败')
    } finally {
      setBusy(false)
    }
  }

  async function updateMaterial(
    material: LearningMaterial,
    payload: Parameters<typeof api.updateMaterial>[1],
  ) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const updated = await api.updateMaterial(material.id, payload)
      void updated
      await notifyChanged()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '更新材料失败')
    } finally {
      setBusy(false)
    }
  }

  async function refreshMaterial(material: LearningMaterial) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await api.refreshMaterial(material.id)
      if (result.using_previous_revision) {
        setNotice(`重新解析失败，仍在使用 ${material.title} 上次成功的版本。`)
      } else if (result.refresh_status === 'succeeded') {
        setNotice(`${material.title} 已重新解析。`)
      }
      await notifyChanged()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '重新解析材料失败')
    } finally {
      setBusy(false)
    }
  }

  async function deleteMaterial() {
    if (!deleteTarget) return
    setBusy(true)
    setError('')
    try {
      await api.deleteMaterial(deleteTarget.id)
      setDeleteTarget(null)
      await notifyChanged()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '删除材料失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="material-library">
      <div className="subsection-heading">
        <div><strong>参考材料</strong><span>{materials.length} 项</span></div>
        {allowAdd && (
          <button
            className="secondary-button"
            type="button"
            disabled={busy || scopeOptions.length === 0}
            onClick={() => {
              setError('')
              setSourceType('pdf')
              setSelectedFile(null)
              setScopeValue(defaultScope ?? scopeOptions[0]?.value ?? '')
              setDialogOpen(true)
            }}
          >
            <Plus size={15} />添加材料
          </button>
        )}
      </div>
      {error && !dialogOpen && <p className="inline-error" role="alert">{error}</p>}
      {notice && !dialogOpen && <p className="inline-notice" role="status">{notice}</p>}
      {materials.length === 0 ? (
        <p className="muted">还没有材料。添加 PDF、网页或公开视频后，各学习节点可以按需引用。</p>
      ) : (
        <div className="material-list">
          {materials.map((material) => (
            <article className={`material-row material-row--${material.status}`} key={material.id}>
              <span className="material-row__icon">
                {material.source_type === 'pdf'
                  ? <FileText size={17} />
                  : material.source_type === 'video'
                    ? <Video size={17} />
                    : <LinkIcon size={17} />}
              </span>
              <div className="material-row__copy">
                <div>
                  <strong>{material.title}</strong>
                  {material.is_primary && <span className="material-primary"><Star size={12} />主材料</span>}
                </div>
                <span>
                  {showCourse ? `${material.course_name} · ` : ''}
                  {scopeLabel(material)} · {material.source_type === 'pdf' ? 'PDF' : material.source_type === 'video' ? '视频字幕' : '网页'} · {material.chunk_count} 个片段
                </span>
                {material.status === 'failed' && <small>{material.error_text}</small>}
                {material.status === 'ready' && material.last_refresh_status === 'failed' && (
                  <small className="material-refresh-warning">
                    上次重新解析失败，仍使用已有版本：{material.last_refresh_error}
                  </small>
                )}
              </div>
              <div className="material-row__actions">
                {allowScopeEdit && (
                  <select
                    aria-label={`调整 ${material.title} 的可用范围`}
                    value={
                      material.section_id
                        ? `section-${material.section_id}`
                        : material.chapter_id
                          ? `chapter-${material.chapter_id}`
                          : `course-${material.course_id}`
                    }
                    disabled={busy}
                    onChange={(event) => {
                      const scope = scopeFor(event.target.value)
                      if (scope) void updateMaterial(material, {
                        course_id: scope.course_id,
                        chapter_id: scope.chapter_id,
                        section_id: scope.section_id,
                      })
                    }}
                  >
                    {scopeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                )}
                <button
                  className="icon-button"
                  type="button"
                  title={material.is_primary ? '取消主材料' : '设为主材料'}
                  aria-label={material.is_primary ? `取消 ${material.title} 的主材料标记` : `将 ${material.title} 设为主材料`}
                  disabled={busy}
                  onClick={() => void updateMaterial(material, { is_primary: !material.is_primary })}
                >
                  <Star size={15} fill={material.is_primary ? 'currentColor' : 'none'} />
                </button>
                {(material.status === 'failed' || material.source_type !== 'pdf') && (
                  <button
                    className="icon-button"
                    type="button"
                    title={material.status === 'failed' ? '重新解析' : '刷新链接内容'}
                    aria-label={`${material.status === 'failed' ? '重新解析' : '刷新'} ${material.title}`}
                    disabled={busy}
                    onClick={() => void refreshMaterial(material)}
                  >
                    <RefreshCw size={15} />
                  </button>
                )}
                <button
                  className="icon-button icon-button--danger"
                  type="button"
                  title="删除材料"
                  aria-label={`删除 ${material.title}`}
                  disabled={busy}
                  onClick={(event) => {
                    setDeleteTrigger(event.currentTarget)
                    setDeleteTarget(material)
                  }}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <AppDialog
        open={dialogOpen}
        title="添加参考材料"
        description={showScopeSelect
          ? '材料会保存在本机，并按选择的课程层级持续可用。'
          : `材料会保存在本机，并固定用于${scopeFor(scopeValue)?.label ?? '当前范围'}。`}
        size="medium"
        busy={busy}
        closeOnBackdrop={false}
        onClose={() => {
          setDialogOpen(false)
          setSelectedFile(null)
        }}
        footer={null}
      >
        <form className="stack-form" onSubmit={createMaterial}>
          <div className="segmented-control material-source-control" role="group" aria-label="材料类型">
            <button type="button" aria-pressed={sourceType === 'pdf'} onClick={() => setSourceType('pdf')}><Upload size={14} />PDF</button>
            <button type="button" aria-pressed={sourceType === 'url'} onClick={() => setSourceType('url')}><LinkIcon size={14} />URL</button>
          </div>
          <label>材料名称<input name="title" required maxLength={300} placeholder="例如：线性代数教材" /></label>
          {sourceType === 'pdf'
            ? (
              <div className="material-file-field">
                <span>PDF 文件</span>
                <input
                  ref={fileInputRef}
                  className="visually-hidden"
                  name="file"
                  type="file"
                  aria-label="PDF 文件"
                  accept="application/pdf,.pdf"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                />
                <button className="material-file-picker" type="button" onClick={() => fileInputRef.current?.click()}>
                  <Upload size={18} />
                  <strong>{selectedFile ? selectedFile.name : '选择 PDF 文件'}</strong>
                  <span>{selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(1)} MB` : '最大 50 MB'}</span>
                </button>
              </div>
            )
            : <label>网页或公开视频 URL<span className="field-help">视频需提供可访问的中文或英文字幕</span><input aria-label="网页 URL" name="url" type="url" required placeholder="https://example.com/article" /></label>}
          {showScopeSelect && <label>可用范围<select value={scopeValue} onChange={(event) => setScopeValue(event.target.value)}>{scopeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>}
          {error && <p className="dialog-error" role="alert">{error}</p>}
          <div className="form-actions">
            <button className="secondary-button" type="button" disabled={busy} onClick={() => { setDialogOpen(false); setSelectedFile(null) }}>取消</button>
            <button className="primary-button" type="submit" disabled={busy}>{busy ? '处理中' : '添加'}</button>
          </div>
        </form>
      </AppDialog>

      {deleteTarget && <TwoStepDeleteDialog
        key={deleteTarget.id}
        open
        title="删除材料？"
        description={`将删除“${deleteTarget.title}”的本地副本、网页快照和检索内容。`}
        finalDescription={`即将永久删除材料“${deleteTarget.title}”，删除后无法恢复。`}
        busy={busy}
        error={error}
        returnFocusTo={deleteTrigger}
        onConfirm={() => void deleteMaterial()}
        onCancel={() => setDeleteTarget(null)}
      />}
    </section>
  )
}
