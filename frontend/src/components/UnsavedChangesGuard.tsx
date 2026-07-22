import { AlertTriangle } from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { useBlocker } from 'react-router-dom'
import { AppDialog } from './AppDialog'

interface UnsavedChangesGuardProps {
  dirty: boolean
  onDiscard?: () => void
  onSave: () => Promise<void>
}

type UnsavedSource = UnsavedChangesGuardProps

interface UnsavedRegistry {
  register: (id: string, source: UnsavedSource) => () => void
  update: (id: string, source: UnsavedSource) => void
}

const UnsavedChangesContext = createContext<UnsavedRegistry | null>(null)

export function UnsavedChangesProvider({ children }: { children: ReactNode }) {
  const sourcesRef = useRef(new Map<string, UnsavedSource>())
  const [dirtyIds, setDirtyIds] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const updateDirtyId = useCallback((id: string, dirty: boolean) => {
    setDirtyIds((current) => {
      const alreadyDirty = current.has(id)
      if (alreadyDirty === dirty) return current
      const next = new Set(current)
      if (dirty) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])
  const register = useCallback((id: string, source: UnsavedSource) => {
    sourcesRef.current.set(id, source)
    updateDirtyId(id, source.dirty)
    return () => {
      sourcesRef.current.delete(id)
      updateDirtyId(id, false)
    }
  }, [updateDirtyId])
  const update = useCallback((id: string, source: UnsavedSource) => {
    sourcesRef.current.set(id, source)
    updateDirtyId(id, source.dirty)
  }, [updateDirtyId])
  const registry = useMemo(() => ({ register, update }), [register, update])
  const hasDirtyChanges = dirtyIds.size > 0

  useEffect(() => {
    if (!hasDirtyChanges) return

    const preventUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = true
    }
    window.addEventListener('beforeunload', preventUnload)
    return () => window.removeEventListener('beforeunload', preventUnload)
  }, [hasDirtyChanges])

  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    hasDirtyChanges
    && `${currentLocation.pathname}${currentLocation.search}${currentLocation.hash}`
      !== `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`
  ))
  const open = blocker.state === 'blocked'

  function continueEditing() {
    setError('')
    blocker.reset?.()
  }

  function leaveWithoutSaving() {
    setError('')
    dirtyIds.forEach((id) => sourcesRef.current.get(id)?.onDiscard?.())
    blocker.proceed?.()
  }

  async function saveAndLeave() {
    setBusy(true)
    setError('')
    try {
      for (const id of dirtyIds) await sourcesRef.current.get(id)?.onSave()
      blocker.proceed?.()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存失败，请检查内容后重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <UnsavedChangesContext.Provider value={registry}>
      {children}
      <AppDialog
        open={open}
        title="还有内容没有保存"
        description={(
          <div className="confirm-dialog__message confirm-dialog__message--warning">
            <span className="confirm-dialog__icon"><AlertTriangle size={18} aria-hidden="true" /></span>
            <p>离开后，尚未保存的内容会丢失。你可以继续编辑、放弃修改，或先保存再离开。</p>
          </div>
        )}
        busy={busy}
        closeOnBackdrop={false}
        onClose={continueEditing}
        showCloseButton={false}
        footer={(
          <div className="unsaved-dialog__actions">
            <button
              className="secondary-button unsaved-dialog__action"
              type="button"
              data-dialog-initial-focus
              disabled={busy}
              onClick={continueEditing}
            >
              继续编辑
            </button>
            <button
              className="secondary-button unsaved-dialog__action unsaved-discard-button"
              type="button"
              disabled={busy}
              onClick={leaveWithoutSaving}
            >
              不保存离开
            </button>
            <button className="primary-button unsaved-dialog__action" type="button" disabled={busy} onClick={() => void saveAndLeave()}>
              {busy ? '正在保存...' : '保存并离开'}
            </button>
          </div>
        )}
      >
        {error && <p className="dialog-error" role="alert">{error}</p>}
      </AppDialog>
    </UnsavedChangesContext.Provider>
  )
}

export function UnsavedChangesGuard({ dirty, onDiscard, onSave }: UnsavedChangesGuardProps) {
  const registry = useContext(UnsavedChangesContext)
  const generatedId = useId()

  if (!registry) throw new Error('UnsavedChangesGuard must be used inside UnsavedChangesProvider')

  useEffect(
    () => registry.register(generatedId, { dirty, onDiscard, onSave }),
    // Later prop changes are synchronized by the update effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [generatedId, registry],
  )
  useLayoutEffect(() => {
    registry.update(generatedId, { dirty, onDiscard, onSave })
  })

  return null
}
