import { isRouteErrorResponse } from 'react-router-dom'

const recoveryStorageKey = 'lumina.route-bundle-recovery'
const recoveryWindowMs = 30_000

type RecoveryStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

interface RecoveryAttempt {
  href: string
  attemptedAt: number
}

interface RecoveryCheck {
  error: unknown
  storage: RecoveryStorage
  href: string
  now?: number
}

interface RecoveryOptions extends RecoveryCheck {
  reload: () => void
}

function errorText(error: unknown) {
  if (error instanceof Error) return `${error.name}: ${error.message}`
  if (typeof error === 'string') return error
  if (isRouteErrorResponse(error)) {
    const detail = typeof error.data === 'string' ? error.data : error.statusText
    return `${error.status} ${detail}`
  }
  return ''
}

export function isDynamicImportFailure(error: unknown) {
  const message = errorText(error).toLowerCase()
  return [
    'failed to fetch dynamically imported module',
    'error loading dynamically imported module',
    'importing a module script failed',
    'chunkloaderror',
    'loading chunk',
  ].some((pattern) => message.includes(pattern))
}

export function canAttemptStaleBundleRecovery({
  error,
  storage,
  href,
  now = Date.now(),
}: RecoveryCheck) {
  if (!isDynamicImportFailure(error)) return false

  try {
    const storedAttempt = storage.getItem(recoveryStorageKey)
    const previous = storedAttempt
      ? JSON.parse(storedAttempt) as Partial<RecoveryAttempt>
      : null
    return !(
      previous?.href === href
      && typeof previous.attemptedAt === 'number'
      && now - previous.attemptedAt < recoveryWindowMs
    )
  } catch {
    return false
  }
}

export function attemptStaleBundleRecovery({
  error,
  storage,
  href,
  reload,
  now = Date.now(),
}: RecoveryOptions) {
  if (!canAttemptStaleBundleRecovery({ error, storage, href, now })) return false

  try {
    storage.setItem(recoveryStorageKey, JSON.stringify({ href, attemptedAt: now }))
  } catch {
    return false
  }

  reload()
  return true
}

export function clearStaleBundleRecovery(storage: RecoveryStorage) {
  storage.removeItem(recoveryStorageKey)
}
