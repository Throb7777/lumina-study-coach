import { useEffect, useState } from 'react'

const noticeDurationMs = 3000

export function useTransientNotice() {
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), noticeDurationMs)
    return () => window.clearTimeout(timer)
  }, [notice])

  return [notice, setNotice] as const
}
