import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

const IDLE_DELAY_MS = 1500

interface PageBackBarProps {
  ariaLabel: string
  to: string
}

export function PageBackBar({ ariaLabel, to }: PageBackBarProps) {
  const sentinelRef = useRef<HTMLSpanElement>(null)
  const idleTimerRef = useRef<number | null>(null)
  const [isStuck, setIsStuck] = useState(false)
  const [isIdle, setIsIdle] = useState(false)

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current)
      idleTimerRef.current = null
    }
  }, [])

  const wakeBar = useCallback(() => {
    clearIdleTimer()
    setIsIdle(false)
  }, [clearIdleTimer])

  const scheduleIdle = useCallback(() => {
    clearIdleTimer()
    if (!isStuck) {
      setIsIdle(false)
      return
    }

    setIsIdle(false)
    idleTimerRef.current = window.setTimeout(() => setIsIdle(true), IDLE_DELAY_MS)
  }, [clearIdleTimer, isStuck])

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || typeof IntersectionObserver === 'undefined') return

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsStuck(!entry.isIntersecting)
        setIsIdle(false)
      },
      { threshold: 1 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!isStuck) {
      clearIdleTimer()
      return
    }

    idleTimerRef.current = window.setTimeout(() => setIsIdle(true), IDLE_DELAY_MS)
    window.addEventListener('scroll', scheduleIdle, { passive: true })
    return () => {
      window.removeEventListener('scroll', scheduleIdle)
      clearIdleTimer()
    }
  }, [clearIdleTimer, isStuck, scheduleIdle])

  const stateClasses = [
    'page-back-bar',
    isStuck ? 'page-back-bar--stuck' : '',
    isStuck && isIdle ? 'page-back-bar--idle' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <>
      <span ref={sentinelRef} className="page-back-bar-sentinel" aria-hidden="true" />
      <nav className={stateClasses} aria-label={ariaLabel}>
        <div className="page-back-bar__inner">
          <Link
            className="back-link"
            to={to}
            onPointerEnter={wakeBar}
            onPointerLeave={scheduleIdle}
            onFocus={wakeBar}
            onBlur={scheduleIdle}
          >
            <ArrowLeft size={16} strokeWidth={1.7} aria-hidden="true" />返回
          </Link>
        </div>
      </nav>
    </>
  )
}
