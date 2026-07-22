import { Circle, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'

interface DraftStatusProps {
  dirtyCount: number
  recoveredLabel?: string
}

const recoveryFadeDelayMs = 2600
const recoveryHideDelayMs = 2900

export function DraftStatus({ dirtyCount, recoveredLabel }: DraftStatusProps) {
  const [showRecovery, setShowRecovery] = useState(Boolean(recoveredLabel))
  const [recoveryLeaving, setRecoveryLeaving] = useState(false)

  useEffect(() => {
    if (!showRecovery) return
    const fadeTimer = window.setTimeout(() => setRecoveryLeaving(true), recoveryFadeDelayMs)
    const hideTimer = window.setTimeout(() => setShowRecovery(false), recoveryHideDelayMs)
    return () => {
      window.clearTimeout(fadeTimer)
      window.clearTimeout(hideTimer)
    }
  }, [showRecovery])

  if (!showRecovery && dirtyCount === 0) return null

  return (
    <div className="draft-status" role="status" aria-live="polite" aria-atomic="true">
      {showRecovery && (
        <span className={`draft-status__recovery${recoveryLeaving ? ' draft-status__recovery--leaving' : ''}`}>
          <RotateCcw size={14} aria-hidden="true" />
          {recoveredLabel}
        </span>
      )}
      {showRecovery && dirtyCount > 0 && <span className="draft-status__divider" aria-hidden="true" />}
      {dirtyCount > 0 && (
        <span className="draft-status__dirty">
          <Circle size={7} fill="currentColor" aria-hidden="true" />
          {dirtyCount} 处内容未保存
        </span>
      )}
    </div>
  )
}
