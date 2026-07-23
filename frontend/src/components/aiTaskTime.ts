export function aiRunStartedAtMs(startedAt: string | undefined, now = Date.now()) {
  if (!startedAt) return now
  const value = startedAt.trim()
  const zonedValue = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
  const timestamp = Date.parse(zonedValue)
  return Number.isFinite(timestamp) ? timestamp : now
}
