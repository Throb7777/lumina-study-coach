import { useEffect, useRef } from 'react'
import { CircleAlert, RefreshCw } from 'lucide-react'
import { useRouteError } from 'react-router-dom'
import {
  attemptStaleBundleRecovery,
  canAttemptStaleBundleRecovery,
  clearStaleBundleRecovery,
  isDynamicImportFailure,
} from '../routeRecovery'

export function RouteErrorBoundary() {
  const error = useRouteError()
  const attemptedRef = useRef(false)
  const recovering = canAttemptStaleBundleRecovery({
    error,
    storage: window.sessionStorage,
    href: window.location.href,
  })

  useEffect(() => {
    if (attemptedRef.current) return
    attemptedRef.current = true
    attemptStaleBundleRecovery({
      error,
      storage: window.sessionStorage,
      href: window.location.href,
      reload: () => window.location.reload(),
    })
  }, [error, recovering])

  function retry() {
    clearStaleBundleRecovery(window.sessionStorage)
    window.location.reload()
  }

  return (
    <main className="route-error-page">
      <div className="route-error-brand" aria-label="Lumina">
        <img src="/favicon-192.png" alt="" aria-hidden="true" />
        <span>Lumina</span>
      </div>
      <div className="route-error-content" role={recovering ? 'status' : 'alert'}>
        {recovering
          ? <RefreshCw className="route-error-icon route-error-icon--loading" size={28} aria-hidden="true" />
          : <CircleAlert className="route-error-icon" size={30} aria-hidden="true" />}
        <h1>{recovering ? '正在同步应用资源' : '页面暂时无法打开'}</h1>
        <p>
          {recovering
            ? '检测到应用刚刚更新，正在重新载入当前页面。'
            : isDynamicImportFailure(error)
              ? '应用资源仍未完整载入，请重新加载当前页面。'
              : '当前页面遇到错误，请重新加载后再试。'}
        </p>
        {!recovering && (
          <button className="primary-button" type="button" onClick={retry}>
            <RefreshCw size={16} aria-hidden="true" />
            重新加载
          </button>
        )}
      </div>
    </main>
  )
}
