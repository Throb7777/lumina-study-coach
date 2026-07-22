import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DraftStatus } from './DraftStatus'
import { useTransientNotice } from '../useTransientNotice'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('DraftStatus', () => {
  it('removes recovery feedback while keeping the unsaved state visible', () => {
    vi.useFakeTimers()
    render(<DraftStatus dirtyCount={1} recoveredLabel="已恢复上次草稿" />)

    expect(screen.getByText('已恢复上次草稿')).toBeInTheDocument()
    expect(screen.getByText('1 处内容未保存')).toBeInTheDocument()

    act(() => vi.advanceTimersByTime(2600))
    expect(screen.getByText('已恢复上次草稿')).toHaveClass('draft-status__recovery--leaving')

    act(() => vi.advanceTimersByTime(300))
    expect(screen.queryByText('已恢复上次草稿')).not.toBeInTheDocument()
    expect(screen.getByText('1 处内容未保存')).toBeInTheDocument()
  })

  it('renders nothing when there is no recovery or unsaved state', () => {
    const { container } = render(<DraftStatus dirtyCount={0} />)
    expect(container).toBeEmptyDOMElement()
  })
})

function NoticeHarness() {
  const [notice, setNotice] = useTransientNotice()
  return (
    <div>
      <button type="button" onClick={() => setNotice('内容已保存')}>show</button>
      {notice && <p>{notice}</p>}
    </div>
  )
}

describe('useTransientNotice', () => {
  it('clears success feedback after three seconds', () => {
    vi.useFakeTimers()
    render(<NoticeHarness />)

    fireEvent.click(screen.getByRole('button', { name: 'show' }))
    expect(screen.getByText('内容已保存')).toBeInTheDocument()

    act(() => vi.advanceTimersByTime(3000))
    expect(screen.queryByText('内容已保存')).not.toBeInTheDocument()
  })
})
