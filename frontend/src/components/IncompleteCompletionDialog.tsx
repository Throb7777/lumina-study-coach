import { ConfirmDialog } from './ConfirmDialog'

interface IncompleteCompletionDialogProps {
  busy?: boolean
  confirmLabel?: string
  error?: string
  incompleteLabels: string[]
  onCancel: () => void
  onConfirm: () => void | Promise<void>
  open: boolean
  returnFocusTo?: HTMLElement | null
}

export function IncompleteCompletionDialog({
  busy = false,
  confirmLabel = '仍然完成',
  error = '',
  incompleteLabels,
  onCancel,
  onConfirm,
  open,
  returnFocusTo,
}: IncompleteCompletionDialogProps) {
  return (
    <ConfirmDialog
      open={open}
      title="还有内容未完成"
      description={`请检查：${incompleteLabels.join('、')}。`}
      cancelLabel="继续完成"
      confirmLabel={confirmLabel}
      variant="warning"
      busy={busy}
      error={error}
      closeOnBackdrop={false}
      showCloseButton={false}
      returnFocusTo={returnFocusTo}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  )
}
