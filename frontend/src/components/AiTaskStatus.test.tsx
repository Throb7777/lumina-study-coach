import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AiTaskStatus } from './AiTaskStatus'
import { aiRunStartedAtMs } from './aiTaskTime'

afterEach(() => {
  vi.useRealTimers()
})

describe('AiTaskStatus', () => {
  it('treats a server timestamp without an offset as UTC', () => {
    expect(aiRunStartedAtMs('2026-07-23T00:00:00')).toBe(
      Date.parse('2026-07-23T00:00:00Z'),
    )
  })

  it('starts a new server run at zero seconds instead of the local UTC offset', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-23T00:00:00.500Z'))

    render(
      <AiTaskStatus
        label="正在生成练习题"
        startedAt="2026-07-23T00:00:00"
      />,
    )

    expect(screen.getByText('0 秒')).toBeInTheDocument()
  })

  it('falls back safely when the timestamp is invalid or in the future', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-23T00:00:00Z'))

    const { rerender } = render(
      <AiTaskStatus label="正在生成练习题" startedAt="invalid" />,
    )
    expect(screen.getByText('0 秒')).toBeInTheDocument()

    rerender(
      <AiTaskStatus label="正在生成练习题" startedAt="2026-07-23T00:01:00Z" />,
    )
    expect(screen.getByText('0 秒')).toBeInTheDocument()
  })
})
