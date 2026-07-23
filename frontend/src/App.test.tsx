import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { appRoutes } from './router'

const workflowNodes = [
  ['recall', '闭卷回顾'],
  ['study', '材料学习'],
  ['reconstruct', '主动重构'],
  ['practice', '练习与推导'],
  ['review', '批改与纠错'],
  ['daily_close', '今日收尾'],
].map(([node_key, title], index) => ({
  id: index + 1,
  node_key,
  title,
  position: index + 1,
  status: 'pending',
}))

const dailyRecord = {
  id: 1,
  section_id: 1,
  section_title: '条件概率',
  chapter_id: 1,
  course_id: 1,
  study_date: '2026-07-14',
  is_completed: false,
  recall_last_learned: '',
  recall_core_concepts: '',
  recall_clear_parts: '',
  recall_blocked_parts: '',
  study_material_scope: '',
  reconstruct_problem: '',
  reconstruct_main_learning: '',
  reconstruct_math: '',
  workflow_nodes: workflowNodes,
  previous_records: [],
  ai_interactions: [],
  exercises: [],
  preview_question_set: null,
  previous_preview_questions: null,
  section_note_prompt: null,
  materials: [],
}

const exercise = {
  id: 1,
  daily_record_id: 1,
  generation_prompt: '请生成练习题。',
  ai_questions: '',
  user_answers: '',
  grading_prompt: '请批改答案。',
  ai_feedback: '',
  format_version: 1,
  status: 'draft',
  items: [],
  mistakes: [],
}

const structuredExerciseItems = Array.from({ length: 12 }, (_, index) => {
  const position = index + 1
  const choice = position <= 4
  return {
    id: 100 + position,
    exercise_id: 2,
    position,
    item_type: choice ? 'single_choice' : 'short_answer',
    difficulty: position <= 4 ? 'basic' : 'intermediate',
    stem_markdown: `Question ${position}`,
    options: choice ? [{ id: 'A', label: 'Option A' }, { id: 'B', label: 'Option B' }] : [],
    rubric_markdown: 'Rubric',
    source_refs: [],
    response: {
      id: 200 + position,
      answer_markdown: '',
      selected_options: [],
      status: 'unanswered',
      verdict: '',
      feedback_markdown: '',
      score: null,
    },
  }
})

const structuredExercise = {
  ...exercise,
  id: 2,
  format_version: 2,
  status: 'draft',
  ai_questions: 'Structured questions',
  items: structuredExerciseItems,
}

const courseDetail = {
  id: 1,
  name: '概率论',
  description: '建立概率模型的基础。',
  learning_goal: '掌握概率推导方法。',
  chapters: [],
}

const courseWithOutline = {
  ...courseDetail,
  chapters: [
    {
      id: 1,
      course_id: 1,
      title: '第一章',
      position: 1,
      sections: [
        {
          id: 1,
          chapter_id: 1,
          title: '条件概率',
          position: 1,
          status: 'in_progress',
          daily_records: [
            { id: 2, study_date: '2026-07-15', is_completed: false },
            { id: 1, study_date: '2026-07-14', is_completed: true },
          ],
        },
      ],
    },
  ],
}

const courseWithRecordHistory = {
  ...courseDetail,
  chapters: [
    {
      ...courseWithOutline.chapters[0],
      sections: [
        {
          ...courseWithOutline.chapters[0].sections[0],
          daily_records: [
            { id: 5, study_date: '2026-07-19', is_completed: false },
            { id: 4, study_date: '2026-07-17', is_completed: false },
            { id: 3, study_date: '2026-07-16', is_completed: true },
            { id: 2, study_date: '2026-07-15', is_completed: false },
            { id: 1, study_date: '2026-07-14', is_completed: true },
          ],
        },
        {
          id: 2,
          chapter_id: 1,
          title: '全概率公式',
          position: 2,
          status: 'in_progress',
          daily_records: [
            { id: 7, study_date: '2026-07-13', is_completed: false },
            { id: 6, study_date: '2026-07-12', is_completed: true },
          ],
        },
      ],
    },
  ],
}

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

function providerSnapshot(providers: unknown[] = [], options: unknown[] = []) {
  return { providers, options }
}

function renderApp(initialEntries: string[]) {
  const router = createMemoryRouter(appRoutes, { initialEntries })
  return { router, ...render(<RouterProvider router={router} />) }
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
  delete document.documentElement.dataset.uiFontSize
  delete document.documentElement.dataset.editorFontSize
  delete document.documentElement.dataset.motion
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows the Lumina service state inside settings without a separate navigation item', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') {
        return jsonResponse({
          obsidian_vault_path: '',
          learner_profile: '',
          service_version: '0.1.0',
          desktop_launch: true,
        })
      }
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') return jsonResponse(providerSnapshot())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp(['/settings'])

    expect(await screen.findByText('Lumina 本地服务已连接')).toBeInTheDocument()
    expect(screen.getByText('v0.1.0 · 本地数据服务运行正常')).toBeInTheDocument()
    expect(screen.getByText('Lumina')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '运行状态' })).not.toBeInTheDocument()
  })

  it('redirects the old status route to the local service section in settings', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') {
        return jsonResponse({
          obsidian_vault_path: '',
          learner_profile: '',
          service_version: '0.1.0',
          desktop_launch: false,
        })
      }
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') return jsonResponse(providerSnapshot())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { router } = renderApp(['/status'])

    expect(await screen.findByText('Lumina 本地服务已连接')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/settings')
    expect(router.state.location.hash).toBe('#local-service')
  })

  it('shows the disconnected state when settings cannot reach the local service', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') return jsonResponse({ detail: 'unavailable' }, 503)
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') return jsonResponse(providerSnapshot())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp(['/settings'])

    expect(await screen.findByText('Lumina 本地服务未连接')).toBeInTheDocument()
  })

  it('opens the bundled example without API calls or writable controls', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/example'])

    expect(await screen.findByRole(
      'heading',
      { name: 'MIT 18.06 线性代数示例' },
      { timeout: 5000 },
    )).toBeInTheDocument()
    expect(screen.getByText('只读完整示例')).toBeInTheDocument()
    expect(screen.getByText('6 / 6 已完成')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()

    await user.click(screen.getByRole('tab', { name: '练习与批改' }))
    const questionNavigation = screen.getByRole('navigation', { name: '示例批改题目导航' })
    await user.click(within(questionNavigation).getByRole('button', { name: '2' }))
    expect(screen.getAllByText('错误')).toHaveLength(2)
    expect(screen.getByText('示例作答')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /保存|完成今日/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '小节笔记' }))
    expect(screen.getAllByText('小节笔记').length).toBeGreaterThanOrEqual(2)
    expect(document.querySelector('.example-note-reader')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('hides the bundled example only after two confirmations', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      throw new Error(`Unexpected request: ${input}`)
    }))
    const user = userEvent.setup()
    const { router } = renderApp(['/courses'])

    expect(await screen.findByRole('heading', { name: 'MIT 18.06 线性代数示例' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '删除示例课程' }))
    expect(screen.getByRole('dialog', { name: '删除示例课程？' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '继续删除' }))
    expect(screen.getByRole('dialog', { name: '再次确认删除' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认删除' }))

    expect(screen.queryByRole('heading', { name: 'MIT 18.06 线性代数示例' })).not.toBeInTheDocument()
    expect(screen.getByText('还没有课程')).toBeInTheDocument()
    expect(localStorage.getItem('lumina.example-dismissed')).toBe('true')

    await router.navigate('/example')
    await waitFor(() => expect(router.state.location.pathname).toBe('/courses'))
  })

  it('creates a course from the course list', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string, init?: RequestInit) => {
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      if (input === '/api/courses' && init?.method === 'POST') {
        return jsonResponse({
          id: 1,
          name: '概率论',
          description: '',
          learning_goal: '',
        }, 201)
      }
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/courses/1') return jsonResponse({ ...courseDetail, chapters: [] })
      throw new Error(`Unexpected request: ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    const { router } = renderApp(['/courses'])

    expect(await screen.findByRole('heading', { name: 'MIT 18.06 线性代数示例' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '创建课程' }))
    await user.type(screen.getByLabelText('课程名称'), '概率论')
    const createDialog = screen.getByRole('dialog', { name: '创建课程' })
    fireEvent.mouseDown(createDialog)
    expect(createDialog).toBeInTheDocument()
    expect(screen.getByLabelText('课程名称')).toHaveValue('概率论')
    await user.click(screen.getByRole('button', { name: '创建并进入' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(4)
      expect(router.state.location.pathname).toBe('/courses/1')
      expect(router.state.navigation.state).toBe('idle')
    }, { timeout: 3000 })
    expect(fetchMock).toHaveBeenCalledWith('/api/courses/1', expect.objectContaining({ signal: expect.any(AbortSignal) }))
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 200))
    })
    expect(screen.getByRole('heading', { name: '概率论' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/courses', expect.objectContaining({ method: 'POST' }))
  })

  it('collapses the sidebar and persists the preference', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      throw new Error(`Unexpected request: ${input}`)
    }))
    const user = userEvent.setup()

    const { container } = renderApp(['/courses'])
    await screen.findByRole('heading', { name: 'MIT 18.06 线性代数示例' })
    expect(container.querySelector('.app-shell')).not.toHaveClass('app-shell--sidebar-collapsed')

    await user.click(screen.getByRole('button', { name: '收起侧栏' }))
    expect(container.querySelector('.app-shell')).toHaveClass('app-shell--sidebar-collapsed')
    expect(localStorage.getItem('learning-flow-coach.sidebar-collapsed')).toBe('true')
    expect(screen.getByRole('button', { name: '展开侧栏' })).toHaveAttribute('aria-expanded', 'false')
  })

  it('keeps the current page visible while the next route is loading', async () => {
    const courses = [{
      ...courseDetail,
      total_sections: 0,
      completed_sections: 0,
      in_progress_sections: 0,
    }]
    let resolveCourseRequest: (() => void) | undefined
    const pendingCourseRequest = new Promise((resolve) => {
      resolveCourseRequest = () => resolve({
        ok: true,
        status: 200,
        json: async () => courseDetail,
      })
    })
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse(courses)
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      if (input === '/api/courses/1') return pendingCourseRequest
      throw new Error(`Unexpected request: ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses'])

    await user.click(await screen.findByRole('heading', { name: '概率论' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(screen.getByRole('heading', { name: '学习课程' })).toBeInTheDocument()
    expect(screen.queryByLabelText('正在读取课程')).not.toBeInTheDocument()

    await act(async () => resolveCourseRequest?.())
    expect(await screen.findByRole('heading', { name: '概率论' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('returns to the last course workspace route after visiting settings', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses/1') return jsonResponse(courseDetail)
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      if (input === '/api/settings') {
        return jsonResponse({
          obsidian_vault_path: '',
          learner_profile: '',
          service_version: '0.1.0',
          desktop_launch: false,
        })
      }
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') return jsonResponse(providerSnapshot())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses/1'])

    expect(await screen.findByRole('heading', { name: '概率论' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: '设置' }))
    expect(await screen.findByText('Lumina 本地服务已连接')).toBeInTheDocument()
    const courseLink = screen.getByRole('link', { name: '课程' })
    expect(courseLink).toHaveAttribute('href', '/courses/1')
    expect(courseLink).toHaveAttribute('title', '返回上次课程位置')
    await user.click(courseLink)

    expect(await screen.findByRole('heading', { name: '概率论' })).toBeInTheDocument()
    const courseHomeLink = screen.getByRole('link', { name: '课程' })
    expect(courseHomeLink).toHaveAttribute('href', '/courses')
    expect(courseHomeLink).toHaveAttribute('title', '返回全部课程')
    expect(courseHomeLink).toHaveClass('active')
    expect(courseHomeLink).toHaveAttribute('aria-current', 'page')
    await user.click(courseHomeLink)

    expect(await screen.findByRole('heading', { name: '学习课程' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/settings', expect.any(Object))
    expect(fetchMock).toHaveBeenCalledWith('/api/courses', expect.any(Object))
  })

  it('does not request browser confirmation when the current page is clean', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      throw new Error(`Unexpected request: ${input}`)
    }))

    renderApp(['/courses'])
    await screen.findByRole('heading', { name: 'MIT 18.06 线性代数示例' })
    const event = new Event('beforeunload', { cancelable: true })

    expect(window.dispatchEvent(event)).toBe(true)
    expect(event.defaultPrevented).toBe(false)
  })

  it('protects and restores an unfinished course creation dialog', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      throw new Error(`Unexpected request: ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    const firstRender = renderApp(['/courses'])
    await screen.findByRole('heading', { name: 'MIT 18.06 线性代数示例' })
    await user.click(screen.getByRole('button', { name: '创建课程' }))
    await user.type(screen.getByLabelText('课程名称'), '未保存的概率论课程')

    const dirtyEvent = new Event('beforeunload', { cancelable: true })
    expect(window.dispatchEvent(dirtyEvent)).toBe(false)
    expect(dirtyEvent.defaultPrevented).toBe(true)
    firstRender.unmount()

    renderApp(['/courses'])
    expect(await screen.findByRole('dialog', { name: '创建课程' })).toBeInTheDocument()
    expect(screen.getByLabelText('课程名称')).toHaveValue('未保存的概率论课程')
    expect(screen.getByText('已恢复课程草稿')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '取消' }))
    const cleanEvent = new Event('beforeunload', { cancelable: true })
    expect(window.dispatchEvent(cleanEvent)).toBe(true)
    expect(cleanEvent.defaultPrevented).toBe(false)
  })

  it('requests browser confirmation only while learning content is unsaved', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse({
        ...dailyRecord,
        recall_last_learned: '条件概率的直观含义',
      }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])
    const recallField = await screen.findByLabelText(/相关知识/)
    await user.type(recallField, '条件概率的直观含义')
    const dirtyEvent = new Event('beforeunload', { cancelable: true })

    expect(window.dispatchEvent(dirtyEvent)).toBe(false)
    expect(dirtyEvent.defaultPrevented).toBe(true)

    await user.click(screen.getByRole('button', { name: '保存' }))
    expect(await screen.findByText('内容已保存')).toBeInTheDocument()
    const cleanEvent = new Event('beforeunload', { cancelable: true })

    expect(window.dispatchEvent(cleanEvent)).toBe(true)
    expect(cleanEvent.defaultPrevented).toBe(false)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('restores an unfinished daily record after the page remounts', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    const firstRender = renderApp(['/daily-records/1'])
    const recallField = await screen.findByLabelText(/相关知识/)
    await user.type(recallField, '刷新后仍需恢复的学习内容')
    firstRender.unmount()

    renderApp(['/daily-records/1'])
    const restoredField = await screen.findByLabelText(/相关知识/)
    await waitFor(() => expect(restoredField).toHaveValue('刷新后仍需恢复的学习内容'))
    expect(await screen.findByText('已恢复上次草稿')).toBeInTheDocument()
    expect(screen.getByText('1 处内容未保存')).toBeInTheDocument()

    const dirtyEvent = new Event('beforeunload', { cancelable: true })
    expect(window.dispatchEvent(dirtyEvent)).toBe(false)
    expect(dirtyEvent.defaultPrevented).toBe(true)
  })

  it('filters courses and shows real section progress', async () => {
    const courses = [
      {
        id: 1,
        name: '概率论',
        description: '建立概率模型的基础。',
        learning_goal: '掌握条件概率。',
        total_sections: 4,
        completed_sections: 2,
        in_progress_sections: 1,
      },
      {
        id: 2,
        name: '线性代数',
        description: '矩阵与向量空间。',
        learning_goal: '理解线性变换。',
        total_sections: 3,
        completed_sections: 0,
        in_progress_sections: 0,
      },
    ]
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse(courses)
      if (input === '/api/onboarding') return jsonResponse({ pending: false })
      throw new Error(`Unexpected request: ${input}`)
    }))
    const user = userEvent.setup()

    renderApp(['/courses'])

    expect(await screen.findByText('已完成 2/4 个小节')).toBeInTheDocument()
    expect(screen.getByText('1 个进行中')).toBeInTheDocument()
    await user.type(screen.getByRole('searchbox', { name: '搜索课程' }), '线性变换')
    expect(screen.queryByRole('heading', { name: '概率论' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '线性代数' })).toBeInTheDocument()
  })

  it('uses the unified back bar on the course detail page', async () => {
    let intersectionCallback: IntersectionObserverCallback | undefined
    class IntersectionObserverMock {
      readonly root = null
      readonly rootMargin = ''
      readonly thresholds = [1]

      constructor(callback: IntersectionObserverCallback) {
        intersectionCallback = callback
      }

      disconnect() {}
      observe() {}
      takeRecords() { return [] }
      unobserve() {}
    }

    vi.stubGlobal('IntersectionObserver', IntersectionObserverMock)
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse(courseDetail)))

    renderApp(['/courses/1'])

    expect(await screen.findByRole('heading', { name: '概率论' })).toBeInTheDocument()
    vi.useFakeTimers()
    const navigation = screen.getByRole('navigation', { name: '课程导航' })
    const backLink = screen.getByRole('link', { name: '返回' })
    expect(navigation).toHaveClass('page-back-bar')
    expect(navigation).toContainElement(backLink)
    expect(backLink).toHaveAttribute('href', '/courses')
    expect(screen.queryByText('返回课程')).not.toBeInTheDocument()

    act(() => intersectionCallback?.(
      [{ isIntersecting: false } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    ))
    expect(navigation).toHaveClass('page-back-bar--stuck')
    expect(navigation).not.toHaveClass('page-back-bar--idle')

    act(() => vi.advanceTimersByTime(1499))
    expect(navigation).not.toHaveClass('page-back-bar--idle')

    act(() => vi.advanceTimersByTime(1))
    expect(navigation).toHaveClass('page-back-bar--idle')

    act(() => window.dispatchEvent(new Event('scroll')))
    expect(navigation).not.toHaveClass('page-back-bar--idle')

    act(() => intersectionCallback?.(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    ))
    expect(navigation).not.toHaveClass('page-back-bar--stuck')
  })

  it('keeps section learning history compact and reveals records progressively', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse(courseWithRecordHistory)))
    const user = userEvent.setup()

    renderApp(['/courses/1'])

    const firstHistory = await screen.findByRole('button', { name: /学习记录 5 次/ })
    const secondHistory = screen.getByRole('button', { name: /学习记录 2 次/ })
    expect(firstHistory).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: '2026-07-19 · 未完成' })).not.toBeInTheDocument()

    await user.click(firstHistory)
    expect(firstHistory).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: '2026-07-19 · 未完成' })).toHaveAttribute('href', '/daily-records/5')
    expect(screen.getByRole('link', { name: '2026-07-16 · 当次完成' })).toHaveAttribute('href', '/daily-records/3')
    expect(screen.queryByRole('link', { name: '2026-07-15 · 未完成' })).not.toBeInTheDocument()
    expect(sessionStorage.getItem('learning-flow-coach.course-1.expanded-history')).toBe('1')

    await user.click(screen.getByRole('button', { name: '查看全部 5 次' }))
    expect(screen.getByRole('link', { name: '2026-07-14 · 当次完成' })).toHaveAttribute('href', '/daily-records/1')

    await user.click(secondHistory)
    expect(firstHistory).toHaveAttribute('aria-expanded', 'false')
    expect(secondHistory).toHaveAttribute('aria-expanded', 'true')
    expect(screen.queryByRole('link', { name: '2026-07-19 · 未完成' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '2026-07-13 · 未完成' })).toHaveAttribute('href', '/daily-records/7')
    expect(sessionStorage.getItem('learning-flow-coach.course-1.expanded-history')).toBe('2')
  })

  it('uses continue learning when the section already has a record for today', async () => {
    const now = new Date()
    const today = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
    ].join('-')
    const courseWithToday = {
      ...courseWithOutline,
      chapters: courseWithOutline.chapters.map((chapter) => ({
        ...chapter,
        sections: chapter.sections.map((section) => ({
          ...section,
          daily_records: [{ id: 9, study_date: today, is_completed: false }],
        })),
      })),
    }
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse(courseWithToday)))

    renderApp(['/courses/1'])

    expect(await screen.findByRole('button', { name: '继续学习' })).toBeInTheDocument()
  })

  it('restores the last opened section history in the current browser session', async () => {
    sessionStorage.setItem('learning-flow-coach.course-1.expanded-history', '2')
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse(courseWithRecordHistory)))

    renderApp(['/courses/1'])

    expect(await screen.findByRole('button', { name: /学习记录 2 次/ })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: '2026-07-13 · 未完成' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /学习记录 5 次/ })).toHaveAttribute('aria-expanded', 'false')
  })

  it('renames a chapter in an in-app dialog', async () => {
    const updatedChapter = { ...courseWithOutline.chapters[0], title: '随机事件' }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(courseWithOutline))
      .mockImplementationOnce(() => jsonResponse(updatedChapter))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses/1'])

    await user.click(await screen.findByRole('button', { name: '修改章节 第一章' }))
    const dialog = await screen.findByRole('dialog', { name: '修改章节' })
    const titleInput = within(dialog).getByLabelText('章节标题')
    expect(titleInput).toHaveValue('第一章')

    await user.clear(titleInput)
    await user.type(titleInput, '随机事件')
    fireEvent.mouseDown(dialog)
    expect(dialog).toBeInTheDocument()
    expect(titleInput).toHaveValue('随机事件')
    await user.click(within(dialog).getByRole('button', { name: '保存' }))

    expect(await screen.findByRole('heading', { name: '随机事件' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/chapters/1', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ title: '随机事件' }),
    }))
  })

  it('protects and restores a chapter title draft when its editor is reopened', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(courseWithOutline))
      .mockImplementationOnce(() => jsonResponse(courseWithOutline))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    const firstRender = renderApp(['/courses/1'])
    await user.click(await screen.findByRole('button', { name: '修改章节 第一章' }))
    const firstDialog = await screen.findByRole('dialog', { name: '修改章节' })
    const firstInput = within(firstDialog).getByLabelText('章节标题')
    await user.clear(firstInput)
    await user.type(firstInput, '尚未保存的章节标题')

    const dirtyEvent = new Event('beforeunload', { cancelable: true })
    expect(window.dispatchEvent(dirtyEvent)).toBe(false)
    firstRender.unmount()

    renderApp(['/courses/1'])
    await user.click(await screen.findByRole('button', { name: '修改章节 第一章' }))
    const restoredDialog = await screen.findByRole('dialog', { name: '修改章节' })
    expect(within(restoredDialog).getByLabelText('章节标题')).toHaveValue('尚未保存的章节标题')

    await user.click(screen.getByRole('button', { name: '取消' }))
    const cleanEvent = new Event('beforeunload', { cancelable: true })
    expect(window.dispatchEvent(cleanEvent)).toBe(true)
    expect(cleanEvent.defaultPrevented).toBe(false)
  })

  it('requires two in-app confirmations before deleting a chapter', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(courseWithOutline))
      .mockImplementationOnce(() => jsonResponse(undefined, 204))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses/1'])

    const deleteButton = await screen.findByRole('button', { name: '删除章节 第一章' })
    await user.click(deleteButton)
    let dialog = await screen.findByRole('dialog', { name: '删除章节？' })
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await user.click(within(dialog).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '删除章节？' })).not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await user.click(deleteButton)
    dialog = await screen.findByRole('dialog', { name: '删除章节？' })
    await user.click(within(dialog).getByRole('button', { name: '继续删除' }))
    dialog = await screen.findByRole('dialog', { name: '再次确认删除' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(within(dialog).getByRole('button', { name: '返回' }))
    dialog = await screen.findByRole('dialog', { name: '删除章节？' })
    await user.click(within(dialog).getByRole('button', { name: '继续删除' }))
    dialog = await screen.findByRole('dialog', { name: '再次确认删除' })
    await user.click(within(dialog).getByRole('button', { name: '确认删除' }))

    await waitFor(() => expect(screen.queryByRole('heading', { name: '第一章' })).not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenLastCalledWith('/api/chapters/1', expect.objectContaining({ method: 'DELETE' }))
  })

  it('saves an inline chapter draft before leaving the course', async () => {
    const createdChapter = {
      id: 2,
      course_id: 1,
      title: '第二章',
      position: 2,
      sections: [],
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(courseDetail))
      .mockImplementationOnce(() => jsonResponse(createdChapter, 201))
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses/1'])

    await user.type(await screen.findByLabelText('章节标题'), '第二章')
    await user.click(screen.getByRole('link', { name: '设置' }))
    const dialog = await screen.findByRole('dialog', { name: '还有内容没有保存' })
    await user.click(within(dialog).getByRole('button', { name: '保存并离开' }))

    expect(await screen.findByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/courses/1/chapters', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ title: '第二章' }),
    }))
  })

  it('saves recall content and completes the workflow node', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce((_path: string, options: RequestInit) => {
        const payload = JSON.parse(String(options.body))
        return jsonResponse({ ...dailyRecord, ...payload })
      })
      .mockImplementationOnce(() => jsonResponse({ ...workflowNodes[0], status: 'completed' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await screen.findByLabelText(/相关知识/)
    expect(screen.queryByLabelText(/遗忘与卡点/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/自我讲解/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '收起闭卷回顾' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: '展开材料学习' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('navigation', { name: '学习记录导航' })).toHaveClass('page-back-bar')
    expect(screen.getByRole('link', { name: '返回' })).toHaveAttribute('href', '/courses/1')
    expect(screen.queryByText('返回课程')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText(/相关知识/), '条件概率的基本定义')
    await user.click(screen.getAllByRole('button', { name: '保存并完成' })[0])

    const incompleteDialog = await screen.findByRole('dialog', { name: '还有内容未完成' })
    expect(within(incompleteDialog).getByText('请检查：核心概念、清晰部分。')).toBeInTheDocument()
    expect(within(incompleteDialog).queryByText(/空格/)).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    fireEvent.mouseDown(incompleteDialog)
    expect(incompleteDialog).toBeInTheDocument()
    await user.click(within(incompleteDialog).getByRole('button', { name: '仍然完成' }))

    expect(await screen.findByText('内容已保存，节点已完成')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '展开闭卷回顾' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: '收起材料学习' })).toHaveAttribute('aria-expanded', 'true')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/daily-records/1', expect.objectContaining({
      method: 'PATCH',
      body: expect.stringContaining('条件概率的基本定义'),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/workflow-nodes/1', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ status: 'completed' }),
    }))
  })

  it('keeps unfinished node content when the user chooses to continue editing', async () => {
    const fetchMock = vi.fn().mockImplementationOnce(() => jsonResponse(dailyRecord))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开材料学习' }))
    const scope = screen.getByLabelText(/学习范围/)
    await user.type(scope, '   ')
    const studyForm = scope.closest('form')
    expect(studyForm).not.toBeNull()
    await user.click(within(studyForm as HTMLFormElement).getByRole('button', { name: '保存并完成' }))

    const dialog = await screen.findByRole('dialog', { name: '还有内容未完成' })
    expect(within(dialog).getByText('请检查：学习范围。')).toBeInTheDocument()
    expect(within(dialog).queryByText(/空格/)).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(within(dialog).getByRole('button', { name: '继续完成' }))

    expect(screen.queryByRole('dialog', { name: '还有内容未完成' })).not.toBeInTheDocument()
    expect(scope).toHaveValue('   ')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('saves exercise answers before completing the practice node', async () => {
    const recordWithExercise = { ...dailyRecord, exercises: [exercise] }
    const updatedExercise = {
      ...exercise,
      ai_questions: '题目一：说明条件概率。',
      user_answers: '先更新样本空间。',
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(recordWithExercise))
      .mockImplementationOnce(() => jsonResponse(updatedExercise))
      .mockImplementationOnce(() => jsonResponse({ ...workflowNodes[3], status: 'completed' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开练习与推导' }))
    const questions = screen.getByRole('textbox', { name: '练习题目' })
    const answers = screen.getByLabelText(/我的作答/)
    await user.type(questions, updatedExercise.ai_questions)
    await user.type(answers, updatedExercise.user_answers)
    const exerciseForm = questions.closest('form')
    expect(exerciseForm).not.toBeNull()
    await user.click(within(exerciseForm as HTMLFormElement).getByRole('button', { name: '保存并完成' }))

    expect(await screen.findByText('题目和答案已保存，节点已完成')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/exercises/1', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        ai_questions: updatedExercise.ai_questions,
        user_answers: updatedExercise.user_answers,
      }),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/workflow-nodes/4', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ status: 'completed' }),
    }))
  })

  it('deletes a legacy exercise only after two in-app confirmations', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ ...dailyRecord, exercises: [exercise] }))
      .mockImplementationOnce(() => jsonResponse(null, 204))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开练习与推导' }))
    await user.click(screen.getByRole('button', { name: '删除旧版练习' }))
    const dialog = await screen.findByRole('dialog', { name: '删除旧版练习？' })
    expect(within(dialog).getByText(/关联错题会被删除/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '继续删除' }))
    const finalDialog = await screen.findByRole('dialog', { name: '再次确认删除' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(within(finalDialog).getByRole('button', { name: '确认删除' }))

    expect(await screen.findByText('旧版练习已删除')).toBeInTheDocument()
    expect(screen.queryByText('旧版整段练习，可继续查看和编辑')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/exercises/1',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('saves the current structured answer before moving to the next question', async () => {
    const savedExercise = {
      ...structuredExercise,
      items: structuredExerciseItems.map((item) => item.position === 1
        ? {
            ...item,
            response: { ...item.response, selected_options: ['A'], status: 'draft' },
          }
        : item),
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ ...dailyRecord, exercises: [structuredExercise] }))
      .mockImplementationOnce(() => jsonResponse(savedExercise))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开练习与推导' }))
    expect(screen.getByText('第 1 / 12 题')).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /Option A/ }))
    await user.click(screen.getByRole('button', { name: '下一题' }))

    expect(await screen.findByText('第 2 / 12 题')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Option A/ })).not.toBeChecked()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/exercise-items/101/response', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ answer_markdown: '', selected_options: ['A'] }),
    }))
  })

  it('renders formulas inside structured exercise options', async () => {
    const formulaExercise = {
      ...structuredExercise,
      items: structuredExerciseItems.map((item) => item.position === 1
        ? {
            ...item,
            stem_markdown: String.raw`设 $P(B)>0$，选择条件概率的定义。`,
            options: [
              { id: 'A', label: String.raw`$P(A\mid B)=\frac{P(A\cap B)}{P(B)}$` },
              { id: 'B', label: String.raw`$P(A\mid B)=P(A)P(B)$` },
            ],
          }
        : item),
    }
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse({
      ...dailyRecord,
      exercises: [formulaExercise],
    })))

    const { container } = renderApp(['/daily-records/1'])

    await userEvent.setup().click(await screen.findByRole('button', { name: '展开练习与推导' }))
    expect(container.querySelectorAll('.exercise-question-stem .katex')).toHaveLength(1)
    expect(container.querySelectorAll('.exercise-option-content .katex')).toHaveLength(2)
    expect(container.querySelector('.exercise-options label')).toHaveTextContent('A')
    expect(container.querySelector('.exercise-option-content')).not.toHaveTextContent('$')
  })

  it('collapses structured practice and opens review after completing the exercise', async () => {
    const answeredItems = structuredExerciseItems.map((item) => ({
      ...item,
      response: {
        ...item.response,
        answer_markdown: item.options.length ? '' : `Answer ${item.position}`,
        selected_options: item.options.length ? ['A'] : [],
        status: 'draft',
      },
    }))
    const answeredExercise = {
      ...structuredExercise,
      items: answeredItems,
    }
    const submittedExercise = {
      ...answeredExercise,
      status: 'submitted',
      items: answeredItems.map((item) => ({
        ...item,
        response: { ...item.response, status: 'submitted' },
      })),
    }
    const completedPractice = { ...workflowNodes[3], status: 'completed' }
    const refreshedRecord = {
      ...dailyRecord,
      workflow_nodes: workflowNodes.map((node) => (
        node.node_key === 'practice' ? completedPractice : node
      )),
      exercises: [submittedExercise],
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ ...dailyRecord, exercises: [answeredExercise] }))
      .mockImplementationOnce(() => jsonResponse(submittedExercise))
      .mockImplementationOnce(() => jsonResponse(refreshedRecord))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开练习与推导' }))
    await user.click(screen.getByRole('button', { name: '完成今日练习' }))

    expect(await screen.findByRole('button', { name: '展开练习与推导' })).toHaveTextContent('已完成')
    expect(screen.getByRole('button', { name: '收起批改与纠错' })).toHaveAttribute('aria-expanded', 'true')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/exercises/2/complete', expect.objectContaining({
      method: 'POST',
    }))
  })

  it('keeps generated grading visible until the user completes the review node', async () => {
    const submittedItems = structuredExerciseItems.map((item) => ({
      ...item,
      response: {
        ...item.response,
        answer_markdown: item.options.length ? '' : `Answer ${item.position}`,
        selected_options: item.options.length ? ['A'] : [],
        status: 'submitted',
      },
    }))
    const submittedExercise = {
      ...structuredExercise,
      status: 'submitted',
      items: submittedItems,
    }
    const gradedExercise = {
      ...submittedExercise,
      status: 'graded',
      ai_feedback: '整套练习总结',
    }
    const refreshedRecord = {
      ...dailyRecord,
      workflow_nodes: workflowNodes,
      exercises: [gradedExercise],
    }
    const completedReview = { ...workflowNodes[4], status: 'completed' }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ ...dailyRecord, exercises: [submittedExercise] }))
      .mockImplementationOnce(() => jsonResponse(gradedExercise))
      .mockImplementationOnce(() => jsonResponse(refreshedRecord))
      .mockImplementationOnce(() => jsonResponse(completedReview))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开批改与纠错' }))
    await user.click(screen.getByRole('button', { name: '批改答案' }))

    expect(await screen.findByRole('button', { name: '收起批改与纠错' })).toHaveTextContent('未完成')
    expect(screen.getByText('逐题复核 1/12')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '展开今日收尾' })).toHaveAttribute('aria-expanded', 'false')
    await user.click(screen.getByRole('button', { name: '完成批改与纠错' }))

    expect(await screen.findByRole('button', { name: '展开批改与纠错' })).toHaveTextContent('已完成')
    expect(screen.getByRole('button', { name: '收起今日收尾' })).toHaveAttribute('aria-expanded', 'true')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/exercises/2/ai-grade', expect.objectContaining({
      method: 'POST',
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/daily-records/1', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/workflow-nodes/5', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ status: 'completed' }),
    }))
  })

  it('starts mistake organization from the first incorrect structured item', async () => {
    const gradedItems = structuredExerciseItems.map((item) => ({
      ...item,
      response: {
        ...item.response,
        verdict: item.position === 3 ? 'incorrect' : 'correct',
        score: item.position === 3 ? 0 : 100,
      },
    }))
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse({
      ...dailyRecord,
      exercises: [{
        ...structuredExercise,
        status: 'graded',
        ai_feedback: '整套练习总结',
        items: gradedItems,
      }],
    })))
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开批改与纠错' }))
    expect(screen.queryByText('整套练习总结')).not.toBeInTheDocument()
    const reviewNavigation = screen.getByRole('navigation', { name: '批改题目导航' })
    await user.click(within(reviewNavigation).getByRole('button', { name: /第 3 题，错误/ }))
    expect(screen.getByText('逐题复核 3/12')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '整理一条错题' }))

    const mistakeForm = document.querySelector<HTMLFormElement>('form.mistake-form')
    expect(mistakeForm?.querySelector<HTMLInputElement>('input[name="original_question"]')).toHaveValue('Question 3')
    expect(within(mistakeForm as HTMLFormElement).getByText('Question 3')).toBeInTheDocument()
  })

  it('requires confirmation before discarding a dirty mistake draft', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse({ ...dailyRecord, exercises: [exercise] })))
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开批改与纠错' }))
    await user.click(screen.getByRole('button', { name: '整理一条错题' }))
    const errorContent = screen.getByLabelText(/错误点/)
    await user.type(errorContent, '没有说明条件概率成立条件')
    const mistakeForm = errorContent.closest('form')
    expect(mistakeForm).not.toBeNull()
    await user.click(within(mistakeForm as HTMLFormElement).getByRole('button', { name: '取消' }))

    let dialog = await screen.findByRole('dialog', { name: '放弃错题草稿？' })
    await user.click(within(dialog).getByRole('button', { name: '取消' }))
    expect(errorContent).toHaveValue('没有说明条件概率成立条件')

    await user.click(within(mistakeForm as HTMLFormElement).getByRole('button', { name: '取消' }))
    dialog = await screen.findByRole('dialog', { name: '放弃错题草稿？' })
    await user.click(within(dialog).getByRole('button', { name: '放弃草稿' }))

    await waitFor(() => expect(screen.queryByLabelText(/错误点/)).not.toBeInTheDocument())
    expect(screen.queryByText('1 处内容未保存')).not.toBeInTheDocument()
  })

  it('keeps unsaved study content and can save it before leaving', async () => {
    const savedText = '条件概率与样本空间更新'
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce((_path: string, options: RequestInit) => {
        const payload = JSON.parse(String(options.body))
        return jsonResponse({ ...dailyRecord, ...payload })
      })
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    const editor = await screen.findByLabelText(/相关知识/)
    await user.type(editor, savedText)
    expect(screen.getByText('1 处内容未保存')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: '设置' }))
    let dialog = await screen.findByRole('dialog', { name: '还有内容没有保存' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(within(dialog).queryByRole('button', { name: '关闭对话框' })).not.toBeInTheDocument()
    expect(dialog.querySelector('.unsaved-dialog__actions')?.children).toHaveLength(3)
    fireEvent.mouseDown(dialog)
    expect(dialog).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '继续编辑' }))
    expect(editor).toHaveValue(savedText)

    await user.click(screen.getByRole('link', { name: '设置' }))
    dialog = await screen.findByRole('dialog', { name: '还有内容没有保存' })
    await user.click(within(dialog).getByRole('button', { name: '保存并离开' }))

    expect(await screen.findByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/daily-records/1', expect.objectContaining({
      method: 'PATCH',
      body: expect.stringContaining(savedText),
    }))
  })

  it('stays on the learning record when save-before-leaving fails', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse({ detail: '暂时无法保存学习内容' }, 500))
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.type(await screen.findByLabelText(/相关知识/), '尚未保存的内容')
    await user.click(screen.getByRole('link', { name: '设置' }))
    const dialog = await screen.findByRole('dialog', { name: '还有内容没有保存' })
    await user.click(within(dialog).getByRole('button', { name: '保存并离开' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('暂时无法保存学习内容')
    expect(screen.getByRole('heading', { name: '条件概率' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '设置' })).not.toBeInTheDocument()
  })

  it('generates a fixed prompt and confirms before skipping practice', async () => {
    const interaction = {
      id: 1,
      daily_record_id: 1,
      kind: 'recall_review',
      prompt_text: '请评价本次闭卷回忆。',
      feedback_text: '',
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(interaction, 201))
      .mockImplementationOnce(() => jsonResponse({ ...workflowNodes[3], status: 'skipped' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '评阅回顾' }))
    expect(await screen.findByDisplayValue('请评价本次闭卷回忆。')).toBeInTheDocument()
    expect(screen.queryByText('提示词已生成')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '展开练习与推导' }))
    await user.click(screen.getByRole('button', { name: '跳过' }))
    const dialog = await screen.findByRole('dialog', { name: '跳过练习与推导？' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    await user.click(within(dialog).getByRole('button', { name: '确认跳过' }))

    expect(await screen.findByText('练习节点已跳过')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/workflow-nodes/4?confirm_skip=true',
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ status: 'skipped' }) }),
    )
  })

  it('offers to skip when an unfinished practice has no completed fields', async () => {
    const recordWithExercise = { ...dailyRecord, exercises: [exercise] }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(recordWithExercise))
      .mockImplementationOnce(() => jsonResponse({ ...workflowNodes[3], status: 'skipped' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开练习与推导' }))
    const questions = screen.getByRole('textbox', { name: '练习题目' })
    const exerciseForm = questions.closest('form')
    expect(exerciseForm).not.toBeNull()
    await user.click(within(exerciseForm as HTMLFormElement).getByRole('button', { name: '保存并完成' }))

    const dialog = await screen.findByRole('dialog', { name: '还有内容未完成' })
    expect(within(dialog).getByText('请检查：练习题目、我的作答。')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '改为跳过' }))

    expect(await screen.findByText('练习节点已跳过')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/workflow-nodes/4?confirm_skip=true',
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ status: 'skipped' }) }),
    )
  })

  it('saves three handoff questions in the daily close node', async () => {
    const previewQuestionSet = {
      id: 1,
      daily_record_id: 1,
      prompt_text: '请生成恰好 3 条明日预习问题。',
      question_1: '',
      question_2: '',
      question_3: '',
    }
    const recordWithPreviousQuestions = {
      ...dailyRecord,
      previous_preview_questions: {
        study_date: '2026-07-13',
        questions: ['先理解哪个条件？', '这个公式如何推导？', '可以用于什么问题？'],
      },
    }
    const savedQuestions = {
      ...previewQuestionSet,
      question_1: '条件是什么？',
      question_2: '如何推导？',
      question_3: '怎样应用？',
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(recordWithPreviousQuestions))
      .mockImplementationOnce(() => jsonResponse(previewQuestionSet))
      .mockImplementationOnce(() => jsonResponse(savedQuestions))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    expect(await screen.findByText('先理解哪个条件？')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '展开今日收尾' }))
    await user.click(screen.getByRole('button', { name: '生成预习问题' }))
    expect(await screen.findByDisplayValue('请生成恰好 3 条明日预习问题。')).toBeInTheDocument()
    expect(screen.queryByText('提示词已生成')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('问题一'), savedQuestions.question_1)
    await user.type(screen.getByLabelText('问题二'), savedQuestions.question_2)
    await user.type(screen.getByLabelText('问题三'), savedQuestions.question_3)
    await user.click(screen.getByRole('button', { name: '保存 3 条问题' }))

    expect(await screen.findByText('3 条衔接问题已保存')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/daily-records/1/preview-questions', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        question_1: savedQuestions.question_1,
        question_2: savedQuestions.question_2,
        question_3: savedQuestions.question_3,
      }),
    }))
  })

  it('shows a reconnect action beside preview generation failures', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse({
        detail: 'Codex 登录已失效，请先在设置中重新连接 Codex。',
      }, 409))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开今日收尾' }))
    await user.click(screen.getByRole('button', { name: '生成预习问题' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Codex 登录已失效')
    expect(within(alert).getByRole('link', { name: '前往设置' })).toHaveAttribute('href', '/settings')
  })

  it('replaces visible preview questions after regeneration', async () => {
    const existingQuestions = {
      id: 1,
      daily_record_id: 1,
      prompt_text: '旧提示词',
      question_1: '旧问题一',
      question_2: '旧问题二',
      question_3: '旧问题三',
    }
    const regeneratedQuestions = {
      ...existingQuestions,
      prompt_text: '新提示词',
      question_1: '新问题一',
      question_2: '新问题二',
      question_3: '新问题三',
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({
        ...dailyRecord,
        preview_question_set: existingQuestions,
      }))
      .mockImplementationOnce(() => jsonResponse(regeneratedQuestions))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开今日收尾' }))
    expect(screen.getByLabelText('问题一')).toHaveValue('旧问题一')
    await user.click(screen.getByRole('button', { name: '重新生成问题' }))

    expect(await screen.findByLabelText('问题一')).toHaveValue('新问题一')
    expect(screen.getByRole('status')).toHaveTextContent('预习问题已生成')
  })

  it('keeps incomplete preview questions pending for later', async () => {
    const previewQuestionSet = {
      id: 1,
      daily_record_id: 1,
      prompt_text: '请生成恰好 3 条明日预习问题。',
      question_1: '',
      question_2: '',
      question_3: '',
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(previewQuestionSet))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开今日收尾' }))
    await user.click(screen.getByRole('button', { name: '生成预习问题' }))
    await user.type(await screen.findByLabelText('问题一'), '先确认哪些条件？')
    const questionForm = screen.getByLabelText('问题一').closest('form')
    expect(questionForm).not.toBeNull()
    await user.click(within(questionForm as HTMLFormElement).getByRole('button', { name: '保存 3 条问题' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('请先完成：问题二、问题三')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('button', { name: '收起今日收尾' })).toHaveAttribute('aria-expanded', 'true')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('asks before ending today while workflow nodes are unfinished', async () => {
    const completedRecord = {
      ...dailyRecord,
      is_completed: true,
      context_summary: '# 今日学习摘要\n\n- 已完成本次学习。',
      workflow_nodes: workflowNodes.map((node) =>
        node.node_key === 'daily_close' ? { ...node, status: 'completed' } : node
      ),
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(completedRecord))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])

    await user.click(await screen.findByRole('button', { name: '展开今日收尾' }))
    await user.click(screen.getByRole('button', { name: '今日完成' }))

    const dialog = await screen.findByRole('dialog', { name: '还有内容未完成' })
    expect(within(dialog).getByText(/闭卷回顾、材料学习、主动重构/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(within(dialog).getByRole('button', { name: '仍然结束今天' }))

    expect(await screen.findByText('今日学习已完成')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '收起今日收尾' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('heading', { name: '今日学习摘要' })).toBeInTheDocument()
    expect(screen.getByText('这个小节已经学完了吗？')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/daily-records/1/complete', expect.objectContaining({
      method: 'POST',
    }))
  })

  it('shows the generated daily summary without a duplicate outer label', async () => {
    const fetchMock = vi.fn().mockImplementationOnce(() => jsonResponse({
      ...dailyRecord,
      is_completed: true,
      context_summary: '# 今日学习摘要\n\n- 已完成本次学习。',
    }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1'])
    await user.click(await screen.findByRole('button', { name: '展开今日收尾' }))

    expect(await screen.findByRole('heading', { name: '今日学习摘要' })).toBeInTheDocument()
    expect(screen.queryByText('今日摘要')).not.toBeInTheDocument()
  })

  it('configures the Obsidian vault in settings', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot()))
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: 'D:\\Notes' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    await user.click(await screen.findByText('手动指定路径'))
    const input = await screen.findByLabelText('Vault 绝对路径')
    await user.type(input, 'D:\\Notes')
    await user.click(screen.getByRole('button', { name: '保存路径' }))

    expect(await screen.findByText('Obsidian Vault 已保存')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/settings/obsidian', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ obsidian_vault_path: 'D:\\Notes' }),
    }))
  })

  it('welcomes a first-run user from the course home and enters the app', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: true })
      if (input === '/api/onboarding/complete') return jsonResponse({ pending: false })
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses'])

    const dialog = await screen.findByRole('dialog', { name: '欢迎使用 Lumina' })
    expect(within(dialog).getByText('从课程和小节开始，按清晰的学习流程持续推进。')).toBeInTheDocument()
    fireEvent.mouseDown(dialog)
    expect(dialog).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '开始使用' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '欢迎使用 Lumina' })).not.toBeInTheDocument())
    expect(await screen.findByRole('heading', { name: '学习课程' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/onboarding/complete', expect.objectContaining({
      method: 'POST',
    }))
  })

  it('keeps the first-run welcome open when completion fails', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/courses') return jsonResponse([])
      if (input === '/api/onboarding') return jsonResponse({ pending: true })
      if (input === '/api/onboarding/complete') {
        return jsonResponse({ detail: '暂时无法保存首次使用状态' }, 503)
      }
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/courses'])

    const dialog = await screen.findByRole('dialog', { name: '欢迎使用 Lumina' })
    await user.click(within(dialog).getByRole('button', { name: '开始使用' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('暂时无法保存首次使用状态')
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: '开始使用' })).toBeEnabled()
  })

  it('does not expose first-run controls on the settings page', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') {
        return jsonResponse({
          obsidian_vault_path: '',
          learner_profile: '',
          service_version: '0.1.0',
          desktop_launch: true,
        })
      }
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') return jsonResponse(providerSnapshot())
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp(['/settings?setup=1'])

    expect(await screen.findByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(screen.queryByText('首次使用 Lumina')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '完成首次设置' })).not.toBeInTheDocument()
  })

  it('falls back to the previous provider endpoints during a rolling restart', async () => {
    const providers = [{
      provider: 'codex',
      installed: true,
      connected: true,
      detail: '已连接 Codex（ChatGPT 账号）',
      account: 'test@example.com',
      plan: 'plus',
      version: 'codex-cli 0.144.5',
      state: 'connected',
      preferred_model: 'GPT-5.5',
      model_available: true,
      reasoning_effort: 'medium',
      active_model: 'gpt-5.5',
    }]
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') return jsonResponse({ obsidian_vault_path: '' })
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') {
        return jsonResponse({ detail: 'not found' }, 404)
      }
      if (input === '/api/ai/providers') return jsonResponse(providers)
      if (input === '/api/ai/provider-options') return jsonResponse([])
      throw new Error(`Unexpected request: ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp(['/settings'])

    expect(await screen.findByText('已连接 Codex（ChatGPT 账号）')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/ai/providers', expect.any(Object))
    expect(fetchMock).toHaveBeenCalledWith('/api/ai/provider-options', expect.any(Object))
  })

  it('offers a guarded shutdown only for the desktop-managed service', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') {
        return jsonResponse({
          obsidian_vault_path: '',
          learner_profile: '',
          desktop_launch: true,
        })
      }
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: true })
      }
      if (input === '/api/ai/provider-snapshot') {
        return jsonResponse(providerSnapshot())
      }
      if (input === '/api/system/shutdown') return jsonResponse({ status: 'stopping' })
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    await user.click(await screen.findByRole('button', { name: '关闭服务' }))
    const dialog = screen.getByRole('dialog', { name: '关闭本地服务？' })
    await user.click(within(dialog).getByRole('button', { name: '关闭服务' }))

    expect(await screen.findByRole('heading', { name: '服务正在关闭' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/system/shutdown', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ confirm: true }),
    }))
  })

  it('connects Codex and Gemini from the settings page', async () => {
    const disconnectedProviders = [
      {
        provider: 'codex',
        installed: true,
        connected: false,
        detail: '等待连接 Codex（使用 ChatGPT 账号授权）',
        account: '',
        plan: '',
        version: '',
        state: 'disconnected',
        preferred_model: 'GPT-5.5',
        model_available: null,
        reasoning_effort: 'medium',
        active_model: '',
      },
      {
        provider: 'gemini',
        installed: true,
        connected: false,
        detail: '等待连接 Google 账号',
        account: '',
        plan: '',
        version: '0.50.0',
        state: 'disconnected',
        preferred_model: 'Gemini 3.5 Flash (High)',
        model_available: null,
        reasoning_effort: '',
        active_model: '',
      },
    ]
    const codexConnected = [
      {
        ...disconnectedProviders[0],
        connected: true,
        detail: '已连接 Codex（ChatGPT 账号）',
        account: 'test@example.com',
        plan: 'plus',
        version: 'codex-cli 0.144.5',
        model_available: true,
        active_model: 'gpt-5.5',
      },
      disconnectedProviders[1],
    ]
    const allConnected = [
      codexConnected[0],
      {
        ...disconnectedProviders[1],
        connected: true,
        detail: '已连接 Antigravity',
        account: 'gemini@example.com',
        model_available: true,
      },
    ]
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot(disconnectedProviders)))
      .mockImplementationOnce(() => jsonResponse({
        auth_url: 'https://example.test/codex-login',
        login_id: 'codex-login-1',
      }))
      .mockImplementationOnce(() => jsonResponse({ status: 'succeeded', error: '' }))
      .mockImplementationOnce(() => jsonResponse(codexConnected))
      .mockImplementationOnce(() => jsonResponse(null, 204))
      .mockImplementationOnce(() => jsonResponse(codexConnected))
      .mockImplementationOnce(() => jsonResponse({ login_id: 'gemini-login-1' }))
      .mockImplementationOnce(() => jsonResponse({ status: 'succeeded', error: '' }))
      .mockImplementationOnce(() => jsonResponse(allConnected))
    vi.stubGlobal('fetch', fetchMock)
    const loginWindow = { location: { href: '' }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(loginWindow as unknown as Window)
    const user = userEvent.setup()

    renderApp(['/settings'])

    expect(await screen.findByRole('button', { name: '连接 Codex' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '连接 Antigravity' })).toBeInTheDocument()
    expect(screen.queryByText('ChatGPT / Codex')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '连接 Codex' }))

    expect(await screen.findByText('Codex 已连接')).toBeInTheDocument()
    expect(screen.getByText('test@example.com · plus')).toBeInTheDocument()
    expect(screen.getByText('GPT-5.5 · Medium · 可用')).toBeInTheDocument()
    expect(screen.getByText('最近使用 gpt-5.5')).toBeInTheDocument()
    expect(screen.getByText('CLI 0.144.5')).toBeInTheDocument()
    expect(loginWindow.location.href).toBe('https://example.test/codex-login')
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      '/api/ai/providers/codex/login/codex-login-1',
      expect.objectContaining({ headers: expect.any(Object) }),
    )

    await user.click(screen.getByRole('button', { name: '连接 Antigravity' }))

    expect(await screen.findByText('Antigravity 已连接')).toBeInTheDocument()
    expect(screen.getByText('gemini@example.com')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      9,
      '/api/ai/providers/gemini/login',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      10,
      '/api/ai/providers/gemini/login/gemini-login-1',
      expect.objectContaining({ headers: expect.any(Object) }),
    )
    expect(screen.getByText('Gemini 3.5 Flash · High · 可用')).toBeInTheDocument()
  })

  it('changes a provider model effort from live options', async () => {
    const providers = [{
      provider: 'codex',
      installed: true,
      connected: true,
      detail: '已连接 Codex（ChatGPT 账号）',
      account: 'test@example.com',
      plan: 'plus',
      version: 'codex-cli 0.144.5',
      state: 'connected',
      preferred_model: 'GPT-5.5',
      model_available: true,
      reasoning_effort: 'medium',
      active_model: 'gpt-5.5',
    }]
    const codexOptions = {
      provider: 'codex',
      selected_model: 'gpt-5.5',
      selected_reasoning_effort: 'medium',
      default_model: 'gpt-5.5',
      default_reasoning_effort: 'medium',
      models: [{
        model: 'gpt-5.5',
        display_name: 'GPT-5.5',
        reasoning_efforts: ['low', 'medium', 'high'],
        default_reasoning_effort: 'medium',
      }],
      error: '',
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot(providers, [codexOptions])))
      .mockImplementationOnce(() => jsonResponse({
        ...codexOptions,
        selected_reasoning_effort: 'high',
      }))
      .mockImplementationOnce(() => jsonResponse([{
        ...providers[0],
        reasoning_effort: 'high',
      }]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    const effort = await screen.findByLabelText('Codex 思考强度')
    expect(effort).toHaveValue('medium')
    await user.selectOptions(effort, 'high')
    await user.click(screen.getByRole('button', { name: '应用' }))

    expect(await screen.findByText('Codex 模型设置已保存')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/settings/ai-providers/codex',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ model: 'gpt-5.5', reasoning_effort: 'high' }),
      }),
    )
  })

  it('disconnects Antigravity from this tool with an in-app confirmation', async () => {
    const connectedProvider = {
      provider: 'gemini',
      installed: true,
      connected: true,
      detail: '已连接 Antigravity',
      account: 'gemini@example.com',
      plan: '',
      version: '1.1.4',
      state: 'connected',
      preferred_model: 'Gemini 3.5 Flash (High)',
      model_available: true,
      reasoning_effort: '',
      active_model: '',
    }
    const disconnectedProvider = {
      ...connectedProvider,
      connected: false,
      detail: '已从本工具断开 Antigravity',
      state: 'disconnected',
      model_available: null,
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot([connectedProvider])))
      .mockImplementationOnce(() => jsonResponse(null, 204))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot([disconnectedProvider])))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    const providerName = await screen.findByText('Gemini · Antigravity')
    const providerRow = providerName.closest('.provider-row')
    expect(providerRow).not.toBeNull()
    await user.click(within(providerRow as HTMLElement).getByRole('button', { name: '断开' }))
    const dialog = await screen.findByRole('dialog', { name: '断开 Antigravity？' })
    expect(within(dialog).getByText(/不会删除.*Google 登录/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '断开' }))

    expect(await screen.findByText('Antigravity 已从本工具断开')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/ai/providers/gemini/disconnect',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows Antigravity login progress and allows cancelling it', async () => {
    const providers = [
      {
        provider: 'gemini',
        installed: true,
        connected: false,
        detail: '等待完成 Antigravity 登录',
        account: '',
        plan: '',
        version: '1.1.3',
        state: 'disconnected',
        preferred_model: 'Gemini 3.5 Flash (High)',
        model_available: null,
      },
    ]
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot(providers)))
      .mockImplementationOnce(() => jsonResponse(null, 204))
      .mockImplementationOnce(() => jsonResponse(providers))
      .mockImplementationOnce(() => jsonResponse({ login_id: 'gemini-login-1' }))
      .mockImplementationOnce(() => jsonResponse({
        status: 'pending',
        error: '',
        detail: '已打开登录窗口，正在等待 Google 授权',
      }))
      .mockImplementationOnce(() => jsonResponse(null, 204))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    await user.click(await screen.findByRole('button', { name: '连接 Antigravity' }))
    const dialog = await screen.findByRole('dialog', { name: '连接 Antigravity' })
    expect(within(dialog).getByText('已打开登录窗口，正在等待 Google 授权')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '取消连接' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '连接 Antigravity' })).not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      '/api/ai/providers/gemini/login/gemini-login-1/cancel',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows a Codex token exchange failure inside the settings page', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot([
        {
          provider: 'codex',
          installed: true,
          connected: false,
          detail: '等待连接 Codex（使用 ChatGPT 账号授权）',
          account: '',
          plan: '',
          version: '',
        },
      ])))
      .mockImplementationOnce(() => jsonResponse({
        auth_url: 'https://example.test/codex-login',
        login_id: 'codex-login-1',
      }))
      .mockImplementationOnce(() => jsonResponse({
        status: 'failed',
        error: 'Codex 登录失败：无法连接授权服务器，请检查本机代理后重试。',
      }))
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(window, 'open').mockReturnValue({
      location: { href: '' },
      close: vi.fn(),
    } as unknown as Window)
    const user = userEvent.setup()

    renderApp(['/settings'])

    await user.click(await screen.findByRole('button', { name: '连接 Codex' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Codex 登录失败：无法连接授权服务器，请检查本机代理后重试。',
    )
  })

  it('keeps an unsaved manual Vault path when navigation is cancelled', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot()))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    await user.click(await screen.findByText('手动指定路径'))
    const input = screen.getByLabelText('Vault 绝对路径')
    await user.type(input, 'D:\\Research Notes')
    await user.click(screen.getByRole('link', { name: '课程' }))
    const dialog = await screen.findByRole('dialog', { name: '还有内容没有保存' })
    await user.click(within(dialog).getByRole('button', { name: '继续编辑' }))

    expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(input).toHaveValue('D:\\Research Notes')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('applies appearance preferences and confirms a discovered vault', async () => {
    const discoveredVault = {
      name: 'Research Notes',
      path: 'D:\\Research Notes',
      has_obsidian_directory: true,
      writable: true,
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: '' }))
      .mockImplementationOnce(() => jsonResponse({ vaults: [discoveredVault], browse_supported: true }))
      .mockImplementationOnce(() => jsonResponse(providerSnapshot()))
      .mockImplementationOnce(() => jsonResponse({ obsidian_vault_path: discoveredVault.path }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/settings'])

    const uiSizeControl = await screen.findByRole('group', { name: '界面字号' })
    await user.click(within(uiSizeControl).getByRole('button', { name: '大' }))
    expect(document.documentElement.dataset.uiFontSize).toBe('large')

    const editorSizeControl = screen.getByRole('group', { name: '笔记编辑字号' })
    await user.click(within(editorSizeControl).getByRole('button', { name: '大' }))
    expect(document.documentElement.dataset.editorFontSize).toBe('large')

    expect(await screen.findByText('Research Notes')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '选择' }))
    expect(screen.getByRole('dialog', { name: '确认 Obsidian Vault' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认使用' }))

    expect(await screen.findByText('Obsidian Vault 已保存')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/settings/obsidian', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ obsidian_vault_path: discoveredVault.path }),
    }))
  })

  it('previews and saves a section note before completing the section', async () => {
    const openedNote = {
      section_id: 1,
      file_name: '条件概率.md',
      relative_path: '概率论/第一章/条件概率.md',
      content: '',
      modified_at_ns: null,
    }
    const markdown = '# 条件概率\n\n分母必须非零。'
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(openedNote))
      .mockImplementationOnce(() => jsonResponse({ ...openedNote, content: markdown, modified_at_ns: 123 }))
      .mockImplementationOnce(() => jsonResponse({ id: 1, status: 'completed' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1/note'])

    const editor = await screen.findByLabelText('Markdown 笔记')
    await user.type(editor, markdown)
    expect(screen.getAllByRole('heading', { name: '条件概率' })).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: '保存并完成小节' }))

    expect(await screen.findByText('笔记已保存，小节已完成')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/sections/1', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ status: 'completed' }),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/sections/1/note', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        content: markdown,
        expected_modified_at_ns: null,
        force_overwrite: false,
      }),
    }))
  })

  it('asks before completing a section note whose body is unfinished', async () => {
    const openedNote = {
      section_id: 1,
      file_name: '条件概率.md',
      relative_path: '概率论/第一章/条件概率.md',
      content: '',
      modified_at_ns: null,
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(openedNote))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1/note'])

    await screen.findByLabelText('Markdown 笔记')
    await user.click(screen.getByRole('button', { name: '保存并完成小节' }))
    const dialog = await screen.findByRole('dialog', { name: '还有内容未完成' })

    expect(within(dialog).getByText('请检查：笔记正文。')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    await user.click(within(dialog).getByRole('button', { name: '继续完成' }))
    expect(screen.queryByRole('dialog', { name: '还有内容未完成' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('offers an explicit conversion for legacy Obsidian math delimiters', async () => {
    const legacyContent = String.raw`# 条件概率

\[
P(A\mid B)=\frac{P(A\cap B)}{P(B)}
\]`
    const openedNote = {
      section_id: 1,
      file_name: '条件概率.md',
      relative_path: '概率论/第一章/条件概率.md',
      content: legacyContent,
      modified_at_ns: 1,
    }
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(openedNote)))
    const user = userEvent.setup()

    renderApp(['/daily-records/1/note'])

    expect(await screen.findByText('检测到旧公式格式')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '转换公式格式' }))
    expect(screen.getByLabelText('Markdown 笔记')).toHaveValue(String.raw`# 条件概率

$$
P(A\mid B)=\frac{P(A\cap B)}{P(B)}
$$`)
    expect(screen.queryByText('检测到旧公式格式')).not.toBeInTheDocument()
  })

  it('saves a dirty section note before returning to the learning record', async () => {
    const openedNote = {
      section_id: 1,
      file_name: '条件概率.md',
      relative_path: '概率论/第一章/条件概率.md',
      content: '',
      modified_at_ns: null,
    }
    const markdown = '# 条件概率\n\n保存后离开。'
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
      .mockImplementationOnce(() => jsonResponse(openedNote))
      .mockImplementationOnce(() => jsonResponse({ ...openedNote, content: markdown, modified_at_ns: 321 }))
      .mockImplementationOnce(() => jsonResponse(dailyRecord))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/daily-records/1/note'])

    await user.type(await screen.findByLabelText('Markdown 笔记'), markdown)
    await user.click(screen.getByRole('link', { name: '返回' }))
    const dialog = await screen.findByRole('dialog', { name: '还有内容没有保存' })
    await user.click(within(dialog).getByRole('button', { name: '保存并离开' }))

    expect(await screen.findByRole('heading', { name: '条件概率' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/sections/1/note', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        content: markdown,
        expected_modified_at_ns: null,
        force_overwrite: false,
      }),
    }))
  })

  it('summarizes and filters mistakes across the course hierarchy', async () => {
    const mistakes = [
      {
        id: 1,
        exercise_id: 1,
        daily_record_id: 1,
        study_date: '2026-07-15',
        course_id: 1,
        course_name: '概率论',
        chapter_id: 1,
        chapter_title: '第一章',
        section_id: 1,
        section_title: '条件概率',
        original_question: '何时可以使用贝叶斯公式？',
        user_answer: '任何条件下。',
        error_content: '忽略分母条件。',
        error_type: 'formula_condition',
        correct_approach: '先确认条件事件概率非零。',
        cause_analysis: '没有理解公式前提。',
        status: 'unresolved',
      },
      {
        id: 2,
        exercise_id: 2,
        daily_record_id: 2,
        study_date: '2026-07-14',
        course_id: 1,
        course_name: '概率论',
        chapter_id: 1,
        chapter_title: '第一章',
        section_id: 2,
        section_title: '全概率公式',
        original_question: '计算分组概率。',
        user_answer: '计算结果。',
        error_content: '加法计算错误。',
        error_type: 'calculation',
        correct_approach: '逐项检查。',
        cause_analysis: '计算疏忽。',
        status: 'understood',
      },
    ]
    const mistakeIndex = {
      items: mistakes,
      courses: [
        {
          id: 1,
          name: '概率论',
          chapters: [
            {
              id: 1,
              title: '第一章',
              sections: [
                { id: 1, title: '条件概率' },
                { id: 2, title: '全概率公式' },
              ],
            },
          ],
        },
      ],
    }
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse(mistakeIndex)))
    const user = userEvent.setup()

    renderApp(['/mistakes'])

    expect(await screen.findByRole('heading', { name: '错题与薄弱点' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '错题' })).toHaveClass('active')
    expect(screen.getByText('何时可以使用贝叶斯公式？')).toBeInTheDocument()
    expect(screen.getByText('计算分组概率。')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('解决状态'), 'unresolved')
    expect(screen.getByText('何时可以使用贝叶斯公式？')).toBeInTheDocument()
    expect(screen.queryByText('计算分组概率。')).not.toBeInTheDocument()
    expect(screen.getByText('1 条')).toBeInTheDocument()
  })

  it('keeps the full course hierarchy selectable when there are no mistakes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse({
      items: [],
      courses: [
        {
          id: 1,
          name: '概率论',
          chapters: [{
            id: 1,
            title: '第一章',
            sections: [{ id: 1, title: '条件概率' }],
          }],
        },
        {
          id: 2,
          name: '线性代数',
          chapters: [{
            id: 2,
            title: '向量',
            sections: [{ id: 2, title: '线性相关' }],
          }],
        },
      ],
    })))
    const user = userEvent.setup()

    renderApp(['/mistakes'])

    expect(await screen.findByText('还没有整理过错题')).toBeInTheDocument()
    const courseSelect = screen.getByLabelText('课程')
    expect(within(courseSelect).getByRole('option', { name: '概率论' })).toBeInTheDocument()
    expect(within(courseSelect).getByRole('option', { name: '线性代数' })).toBeInTheDocument()
    expect(within(screen.getByLabelText('章节')).getByRole('option', { name: '概率论 / 第一章' })).toBeInTheDocument()
    await user.selectOptions(courseSelect, '2')
    expect(within(screen.getByLabelText('章节')).getByRole('option', { name: '向量' })).toBeInTheDocument()
    expect(within(screen.getByLabelText('小节')).getByRole('option', { name: '向量 / 线性相关' })).toBeInTheDocument()
  })

  it('searches only the notes returned by the managed note index', async () => {
    const noteIndex = {
      issues: [],
      items: [
        {
          section_id: 1,
          course_id: 1,
          course_name: '概率论',
          chapter_id: 1,
          chapter_title: '第一章',
          section_title: '条件概率',
          relative_path: '概率论/第一章/条件概率.md',
          content: '# 条件概率\n\n分母必须非零。',
          modified_at_ns: 1,
        },
        {
          section_id: 2,
          course_id: 2,
          course_name: '线性代数',
          chapter_id: 2,
          chapter_title: '向量',
          section_title: '线性相关',
          relative_path: '线性代数/向量/线性相关.md',
          content: '# 线性相关\n\n秩与线性组合。',
          modified_at_ns: 2,
        },
      ],
    }
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => jsonResponse(noteIndex)))
    const user = userEvent.setup()

    const { router } = renderApp(['/notes'])

    expect(await screen.findByRole('heading', { name: '小节笔记' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '笔记' })).toHaveClass('active')
    await user.type(screen.getByRole('searchbox', { name: '搜索小节笔记' }), '分母')
    await waitFor(() => expect(router.state.location.search).toBe('?q=%E5%88%86%E6%AF%8D'))
    expect(screen.getByRole('heading', { name: '条件概率' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '线性相关' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '打开笔记' })).toHaveAttribute('href', '/notes/1?q=%E5%88%86%E6%AF%8D')
  })

  it('opens a library note without entering the learning workflow', async () => {
    const openedNote = {
      section_id: 1,
      file_name: '条件概率.md',
      relative_path: '概率论/第一章/条件概率.md',
      content: '# 条件概率\n\n分母必须非零。',
      modified_at_ns: 1,
    }
    const noteIndex = {
      issues: [],
      items: [{
        section_id: 1,
        course_id: 1,
        course_name: '概率论',
        chapter_id: 1,
        chapter_title: '第一章',
        section_title: '条件概率',
        relative_path: '概率论/第一章/条件概率.md',
        content: openedNote.content,
        modified_at_ns: 1,
      }],
    }
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(openedNote))
      .mockImplementationOnce(() => jsonResponse(noteIndex))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/notes/1?q=%E5%88%86%E6%AF%8D&course=1'])

    expect(await screen.findByLabelText('Markdown 笔记')).toHaveValue(openedNote.content)
    expect(screen.getByRole('link', { name: '笔记' })).toHaveClass('active')
    expect(screen.getByRole('link', { name: '课程' })).not.toHaveClass('active')
    expect(screen.getByRole('link', { name: '返回' })).toHaveAttribute('href', '/notes?q=%E5%88%86%E6%AF%8D&course=1')
    expect(screen.queryByRole('button', { name: '保存并完成小节' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /生成笔记整理提示词/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: '返回' }))
    expect(await screen.findByRole('searchbox', { name: '搜索小节笔记' })).toHaveValue('分母')
    expect(screen.getByRole('combobox', { name: '按课程筛选' })).toHaveValue('1')
  })

  it('saves a library note without a daily learning record', async () => {
    const openedNote = {
      section_id: 1,
      file_name: '条件概率.md',
      relative_path: '概率论/第一章/条件概率.md',
      content: '# 条件概率',
      modified_at_ns: 1,
    }
    const savedContent = '# 条件概率\n\n分母必须非零。'
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => jsonResponse(openedNote))
      .mockImplementationOnce(() => jsonResponse({ ...openedNote, content: savedContent, modified_at_ns: 2 }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    renderApp(['/notes/1'])

    const editor = await screen.findByLabelText('Markdown 笔记')
    await user.clear(editor)
    await user.type(editor, savedContent)
    await user.click(screen.getByRole('button', { name: '保存到 Obsidian' }))

    expect(await screen.findByText('笔记已保存到 Obsidian')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/sections/1/note', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        content: savedContent,
        expected_modified_at_ns: 1,
        force_overwrite: false,
      }),
    }))
  })

  it('configures the hierarchical Markdown export in settings', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') return jsonResponse({ obsidian_vault_path: '' })
      if (input === '/api/settings/obsidian-vaults') {
        return jsonResponse({ vaults: [], browse_supported: false })
      }
      if (input === '/api/courses') {
        return jsonResponse([
          {
            id: 1,
            name: '概率论',
            description: '',
            learning_goal: '',
            total_sections: 2,
            completed_sections: 0,
            in_progress_sections: 1,
          },
          {
            id: 2,
            name: '线性代数',
            description: '',
            learning_goal: '',
            total_sections: 1,
            completed_sections: 0,
            in_progress_sections: 0,
          },
        ])
      }
      throw new Error(`Unexpected request: ${input}`)
    }))
    const user = userEvent.setup()

    renderApp(['/settings'])

    expect(await screen.findByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(screen.getByText('Markdown 导出')).toBeInTheDocument()
    expect(screen.getByText('选择课程和内容，导出 Markdown 文件。')).toBeInTheDocument()
    expect(screen.queryByText('分层 Markdown 文件')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '选择并导出' }))
    const dialog = await screen.findByRole('dialog', { name: '导出 Markdown' })
    expect(within(dialog).getByLabelText('概率论')).toBeChecked()
    expect(within(dialog).getByLabelText('线性代数')).toBeChecked()
    expect(within(dialog).getByLabelText('小节笔记（未配置 Vault）')).toBeDisabled()
    expect(within(dialog).getByText('已选择 2 门课程，5 类内容')).toBeInTheDocument()
    await user.click(within(dialog).getByLabelText('线性代数'))
    expect(within(dialog).getByText('已选择 1 门课程，5 类内容')).toBeInTheDocument()
  })

  it('opens the material library from settings in a dialog', async () => {
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      if (input === '/api/settings') return jsonResponse({ obsidian_vault_path: '', learner_profile: '' })
      if (input === '/api/settings/obsidian-vaults') return jsonResponse({ vaults: [], browse_supported: true })
      if (input === '/api/ai/provider-snapshot') return jsonResponse(providerSnapshot())
      if (input === '/api/materials') return jsonResponse([])
      if (input === '/api/courses') return jsonResponse([])
      throw new Error(`Unexpected request: ${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderApp(['/settings'])

    await userEvent.setup().click(await screen.findByRole('button', { name: '打开材料库' }))
    const dialog = await screen.findByRole('dialog', { name: '材料库' })
    expect(within(dialog).getByPlaceholderText('搜索材料名称、课程或来源')).toBeInTheDocument()
    expect(within(dialog).getByText(/还没有材料/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '材料' })).not.toBeInTheDocument()
  })
})
