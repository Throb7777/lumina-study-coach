import { useState } from 'react'
import type { ReactNode } from 'react'
import { ConfirmDialog } from './ConfirmDialog'

interface TwoStepDeleteDialogProps {
  busy?: boolean
  description: ReactNode
  error?: string
  finalDescription: ReactNode
  onCancel: () => void
  onConfirm: () => void | Promise<void>
  open: boolean
  returnFocusTo?: HTMLElement | null
  title: string
}

export function TwoStepDeleteDialog({
  busy = false,
  description,
  error = '',
  finalDescription,
  onCancel,
  onConfirm,
  open,
  returnFocusTo,
  title,
}: TwoStepDeleteDialogProps) {
  const [finalStep, setFinalStep] = useState(false)

  return (
    <ConfirmDialog
      open={open}
      title={finalStep ? '再次确认删除' : title}
      description={finalStep ? finalDescription : description}
      cancelLabel={finalStep ? '返回' : '取消'}
      confirmLabel={finalStep ? '确认删除' : '继续删除'}
      variant="danger"
      busy={finalStep && busy}
      error={finalStep ? error : ''}
      closeOnBackdrop={false}
      showCloseButton={false}
      returnFocusTo={returnFocusTo}
      onCancel={() => {
        if (finalStep) setFinalStep(false)
        else onCancel()
      }}
      onConfirm={() => {
        if (finalStep) return onConfirm()
        setFinalStep(true)
      }}
    />
  )
}
