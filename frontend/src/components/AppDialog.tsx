import { useEffect, useId, useLayoutEffect, useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { X } from 'lucide-react'
import { createPortal } from 'react-dom'

interface AppDialogProps {
  busy?: boolean
  children: ReactNode
  closeOnBackdrop?: boolean
  description?: ReactNode
  footer?: ReactNode
  onClose: () => void
  open: boolean
  returnFocusTo?: HTMLElement | null
  showCloseButton?: boolean
  size?: 'small' | 'medium' | 'large' | 'workspace'
  title: string
}

function closeDialogElement(dialog: HTMLDialogElement) {
  if (typeof dialog.close === 'function') dialog.close()
  else dialog.removeAttribute('open')
}

function restoreFocus(element: HTMLElement | null) {
  queueMicrotask(() => {
    if (element?.isConnected) element.focus()
  })
}

export function AppDialog({
  busy = false,
  children,
  closeOnBackdrop = true,
  description,
  footer,
  onClose,
  open,
  returnFocusTo,
  showCloseButton = true,
  size = 'small',
  title,
}: AppDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const titleId = useId()
  const descriptionId = useId()

  useLayoutEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (open) {
      returnFocusRef.current = returnFocusTo ?? (document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null)
      if (!dialog.open) {
        if (typeof dialog.showModal === 'function') dialog.showModal()
        else dialog.setAttribute('open', '')
      }
      queueMicrotask(() => {
        dialog.querySelector<HTMLElement>('[data-dialog-initial-focus]')?.focus()
      })
      return
    }

    if (dialog.open) closeDialogElement(dialog)
    restoreFocus(returnFocusRef.current)
  }, [open, returnFocusTo])

  useEffect(() => () => {
    const dialog = dialogRef.current
    if (dialog?.open) closeDialogElement(dialog)
    restoreFocus(returnFocusRef.current)
  }, [])

  function handleCancel(event: React.SyntheticEvent<HTMLDialogElement>) {
    event.preventDefault()
    if (!busy) onClose()
  }

  function handleBackdropPointerDown(event: MouseEvent<HTMLDialogElement>) {
    if (closeOnBackdrop && event.target === event.currentTarget && !busy) onClose()
  }

  return createPortal(
    <dialog
      ref={dialogRef}
      className={`app-dialog app-dialog--${size}`}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      aria-modal="true"
      onCancel={handleCancel}
      onMouseDown={handleBackdropPointerDown}
    >
      <div className="app-dialog__surface">
        <header className="app-dialog__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <div id={descriptionId} className="app-dialog__description">{description}</div>}
          </div>
          {showCloseButton && (
            <button
              className="icon-button app-dialog__close"
              type="button"
              aria-label="关闭对话框"
              title="关闭"
              disabled={busy}
              onClick={onClose}
            >
              <X size={17} aria-hidden="true" />
            </button>
          )}
        </header>
        <div className="app-dialog__body">{children}</div>
        {footer && <footer className="app-dialog__footer">{footer}</footer>}
      </div>
    </dialog>,
    document.body,
  )
}
