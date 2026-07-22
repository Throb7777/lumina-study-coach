import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Check } from 'lucide-react'
import { AppDialog } from './AppDialog'
import { DraftStatus } from './DraftStatus'
import { clearDraft, readDraft, writeDraft } from '../draftStorage'

interface TextEditDialogProps {
  busy?: boolean
  draftKey?: string
  error?: string
  initialValue: string
  label: string
  onClose: () => void
  onDirtyChange?: (dirty: boolean, value: string) => void
  onSubmit: (value: string) => void | Promise<void>
  open: boolean
  returnFocusTo?: HTMLElement | null
  title: string
}

export function TextEditDialog({
  busy = false,
  draftKey,
  error = '',
  initialValue,
  label,
  onClose,
  onDirtyChange,
  onSubmit,
  open,
  returnFocusTo,
  title,
}: TextEditDialogProps) {
  const [restoredValue] = useState<string | null>(() => (
    draftKey ? readDraft(draftKey, initialValue) : null
  ))
  const [value, setValue] = useState(restoredValue ?? initialValue)
  const formId = useId()
  const inputId = useId()
  const trimmedValue = value.trim()
  const cannotSave = busy || !trimmedValue || trimmedValue === initialValue.trim()
  const dirty = value !== initialValue

  useEffect(() => {
    onDirtyChange?.(dirty, value)
    if (!draftKey) return
    if (dirty) writeDraft(draftKey, initialValue, value)
    else clearDraft(draftKey)
  }, [dirty, draftKey, initialValue, onDirtyChange, value])

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (cannotSave) return
    void onSubmit(trimmedValue)
  }

  return (
    <AppDialog
      open={open}
      title={title}
      busy={busy}
      closeOnBackdrop={false}
      onClose={onClose}
      returnFocusTo={returnFocusTo}
      footer={(
        <>
          <button className="secondary-button" type="button" disabled={busy} onClick={onClose}>取消</button>
          <button className="primary-button" type="submit" form={formId} disabled={cannotSave}>
            <Check size={16} aria-hidden="true" />{busy ? '保存中...' : '保存'}
          </button>
        </>
      )}
    >
      <form id={formId} className="dialog-form" onSubmit={handleSubmit}>
        <DraftStatus
          dirtyCount={dirty ? 1 : 0}
          recoveredLabel={restoredValue === null ? undefined : '已恢复标题草稿'}
        />
        <label htmlFor={inputId}>{label}</label>
        <input
          id={inputId}
          data-dialog-initial-focus
          value={value}
          required
          maxLength={200}
          disabled={busy}
          onChange={(event) => setValue(event.target.value)}
          onFocus={(event) => event.currentTarget.select()}
        />
        {error && <p className="dialog-error" role="alert">{error}</p>}
      </form>
    </AppDialog>
  )
}
