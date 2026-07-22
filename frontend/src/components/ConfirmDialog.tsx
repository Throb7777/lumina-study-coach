import type { ReactNode } from 'react'
import { AlertTriangle, Info } from 'lucide-react'
import { AppDialog } from './AppDialog'

export type ConfirmDialogVariant = 'default' | 'warning' | 'danger'

interface ConfirmDialogProps {
  busy?: boolean
  cancelLabel?: string
  closeOnBackdrop?: boolean
  confirmLabel: string
  description: ReactNode
  error?: string
  onCancel: () => void
  onConfirm: () => void | Promise<void>
  open: boolean
  returnFocusTo?: HTMLElement | null
  showCloseButton?: boolean
  title: string
  variant?: ConfirmDialogVariant
}

export function ConfirmDialog({
  busy = false,
  cancelLabel = '取消',
  closeOnBackdrop = true,
  confirmLabel,
  description,
  error = '',
  onCancel,
  onConfirm,
  open,
  returnFocusTo,
  showCloseButton = true,
  title,
  variant = 'default',
}: ConfirmDialogProps) {
  const Icon = variant === 'default' ? Info : AlertTriangle

  return (
    <AppDialog
      open={open}
      title={title}
      description={(
        <div className={`confirm-dialog__message confirm-dialog__message--${variant}`}>
          <span className="confirm-dialog__icon"><Icon size={18} aria-hidden="true" /></span>
          <p>{description}</p>
        </div>
      )}
      busy={busy}
      closeOnBackdrop={closeOnBackdrop}
      onClose={onCancel}
      returnFocusTo={returnFocusTo}
      showCloseButton={showCloseButton}
      footer={(
        <div className="confirm-dialog__actions">
          <button
            className="secondary-button"
            type="button"
            data-dialog-initial-focus
            disabled={busy}
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button
            className={variant === 'danger' ? 'danger-button' : 'primary-button'}
            type="button"
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            {busy ? '处理中...' : confirmLabel}
          </button>
        </div>
      )}
    >
      {error && <p className="dialog-error" role="alert">{error}</p>}
    </AppDialog>
  )
}
