import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { attemptStaleBundleRecovery, isDynamicImportFailure } from '../routeRecovery'
import { RouteErrorBoundary } from './RouteErrorBoundary'

function createStorage() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  }
}

describe('stale route bundle recovery', () => {
  it('recognizes dynamic import and chunk loading failures', () => {
    expect(isDynamicImportFailure(
      new TypeError('Failed to fetch dynamically imported module: /assets/CoursePage-old.js'),
    )).toBe(true)
    expect(isDynamicImportFailure(new Error('ChunkLoadError: Loading chunk 3 failed'))).toBe(true)
    expect(isDynamicImportFailure(new Error('ordinary loader failure'))).toBe(false)
  })

  it('reloads a stale route bundle only once during the guard window', () => {
    const storage = createStorage()
    const reload = vi.fn()
    const options = {
      error: new TypeError('Failed to fetch dynamically imported module: /assets/old.js'),
      storage,
      href: 'http://127.0.0.1:8000/courses/1',
      reload,
      now: 1000,
    }

    expect(attemptStaleBundleRecovery(options)).toBe(true)
    expect(attemptStaleBundleRecovery({ ...options, now: 2000 })).toBe(false)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does not reload for ordinary route errors', () => {
    const reload = vi.fn()

    expect(attemptStaleBundleRecovery({
      error: new Error('API request failed'),
      storage: createStorage(),
      href: 'http://127.0.0.1:8000/courses',
      reload,
    })).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })

  it('renders a branded Chinese recovery action for ordinary route errors', async () => {
    const router = createMemoryRouter([
      {
        path: '/',
        loader: () => {
          throw new Error('loader failed')
        },
        element: <p>不会显示</p>,
        errorElement: <RouteErrorBoundary />,
      },
    ])

    render(<RouterProvider router={router} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('页面暂时无法打开')
    expect(screen.getByRole('button', { name: '重新加载' })).toBeInTheDocument()
    expect(screen.queryByText('Unexpected Application Error!')).not.toBeInTheDocument()
  })
})
