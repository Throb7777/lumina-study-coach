import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('AI provider snapshot', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('fails with a retryable error instead of loading forever', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'))
        }, { once: true })
      })
    )))

    const assertion = expect(api.getAiProviderSnapshot()).rejects.toThrow(
      '读取模型连接状态超时，请重试',
    )
    await vi.advanceTimersByTimeAsync(15_000)

    await assertion
  })
})
