import { useEffect, useState } from 'react'
import { LoaderCircle } from 'lucide-react'

interface AiTaskStatusProps {
  label: string
  phase?: string
  startedAt?: string
  recovered?: boolean
}

export function AiTaskStatus({
  label,
  phase = '正在整理当前内容与参考材料',
  startedAt,
  recovered = false,
}: AiTaskStatusProps) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const timestamp = startedAt ? new Date(startedAt).getTime() : Date.now()
    const updateElapsed = () => {
      setSeconds(Math.max(0, Math.floor((Date.now() - timestamp) / 1000)))
    }
    updateElapsed()
    const timer = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(timer)
  }, [startedAt])

  return (
    <div className="ai-task-status" role="status" aria-live="polite">
      <LoaderCircle className="ai-task-status__spinner" size={18} aria-hidden="true" />
      <div><strong>{label}</strong><span>{phase}{recovered ? ' · 已恢复后台状态' : ''}</span></div>
      <time>{seconds} 秒</time>
    </div>
  )
}
