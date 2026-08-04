import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MaterialLibrary } from './MaterialLibrary'

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  }))
}

describe('MaterialLibrary', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('adds a URL material with the selected scope', async () => {
    const material = {
      id: 1,
      course_id: 3,
      course_name: '线性代数',
      chapter_id: 4,
      chapter_title: '第一章',
      section_id: 5,
      section_title: '向量空间',
      title: '课程网页',
      source_type: 'url',
      source_url: 'https://example.test/course',
      original_name: '课程网页',
      status: 'ready',
      error_text: '',
      is_primary: true,
      chunk_count: 3,
    } as const
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return jsonResponse(material, 201)
    })
    vi.stubGlobal('fetch', fetchMock)
    const changed = vi.fn()
    const user = userEvent.setup()

    render(
      <MaterialLibrary
        materials={[]}
        scopeOptions={[{
          value: 'section-5',
          label: '第一章 · 向量空间',
          course_id: 3,
          chapter_id: 4,
          section_id: 5,
          is_primary: false,
        }]}
        defaultScope="section-5"
        showScopeSelect={false}
        onChanged={changed}
      />,
    )

    await user.click(screen.getByRole('button', { name: '添加材料' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).queryByLabelText('可用范围')).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'URL' }))
    await user.type(within(dialog).getByLabelText('材料名称'), '课程网页')
    await user.type(within(dialog).getByLabelText('网页 URL'), 'https://example.test/course')
    await user.click(within(dialog).getByRole('button', { name: '添加' }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/materials/url',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          title: '课程网页',
          url: 'https://example.test/course',
          course_id: 3,
          chapter_id: 4,
          section_id: 5,
          is_primary: false,
        }),
      }),
    )
    expect(changed).toHaveBeenCalledOnce()
    expect(within(dialog).queryByText('设为这个范围的主材料')).not.toBeInTheDocument()
  })

  it('uses a custom PDF picker and submits the selected file', async () => {
    const material = {
      id: 2,
      course_id: 3,
      course_name: '线性代数',
      chapter_id: null,
      chapter_title: '',
      section_id: null,
      section_title: '',
      title: '教材',
      source_type: 'pdf',
      source_url: '',
      original_name: '教材.pdf',
      status: 'ready',
      error_text: '',
      is_primary: true,
      chunk_count: 2,
    } as const
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return jsonResponse(material, 201)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(
      <MaterialLibrary
        materials={[]}
        scopeOptions={[{
          value: 'course-3',
          label: '整个课程',
          course_id: 3,
          chapter_id: null,
          section_id: null,
          is_primary: false,
        }]}
      />,
    )

    await user.click(screen.getByRole('button', { name: '添加材料' }))
    const dialog = screen.getByRole('dialog')
    const file = new File(['%PDF-1.7'], '教材.pdf', { type: 'application/pdf' })
    await user.upload(within(dialog).getByLabelText('PDF 文件'), file)
    expect(within(dialog).getByText('教材.pdf')).toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('材料名称'), '教材')
    await user.click(within(dialog).getByRole('button', { name: '添加' }))

    const request = fetchMock.mock.calls[0][1] as RequestInit
    expect(request.body).toBeInstanceOf(FormData)
    expect((request.body as FormData).get('file')).toBe(file)
  })

  it('keeps a ready material usable when its latest refresh failed', async () => {
    const material = {
      id: 3,
      course_id: 3,
      course_name: '金融市场',
      chapter_id: 4,
      chapter_title: '第一讲',
      section_id: 5,
      section_title: '课程导论',
      title: 'Yale 视频字幕',
      source_type: 'video',
      source_url: 'https://example.test/video',
      original_name: 'Lecture 1',
      status: 'ready',
      error_text: '',
      last_refresh_status: 'failed',
      last_refresh_error: 'HTTP Error 429',
      last_refresh_at: '2026-07-20T12:00:00',
      last_success_at: '2026-07-20T11:00:00',
      is_primary: true,
      chunk_count: 32,
    } as const
    const fetchMock = vi.fn(() => jsonResponse({
      refresh_status: 'failed',
      using_previous_revision: true,
      error: 'HTTP Error 429',
      material,
    }))
    vi.stubGlobal('fetch', fetchMock)
    const changed = vi.fn()
    const user = userEvent.setup()

    render(<MaterialLibrary materials={[material]} onChanged={changed} />)

    expect(screen.getByText(/仍使用已有版本：HTTP Error 429/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '刷新 Yale 视频字幕' }))
    expect(await screen.findByRole('status')).toHaveTextContent(/仍在使用 Yale 视频字幕.*上次成功的版本/)
    expect(changed).toHaveBeenCalledOnce()
  })

  it('shows multiple priority materials and exposes independent toggles', async () => {
    const base = {
      course_id: 3,
      course_name: '线性代数',
      chapter_id: null,
      chapter_title: '',
      section_id: null,
      section_title: '',
      source_type: 'pdf' as const,
      source_url: '',
      status: 'ready' as const,
      error_text: '',
      warning_text: '',
      original_name: 'material.pdf',
      is_primary: true,
      chunk_count: 2,
    }
    const materials = [
      { ...base, id: 10, title: '教材 A' },
      { ...base, id: 11, title: '教材 B' },
    ]
    const fetchMock = vi.fn(() => jsonResponse({ ...materials[0], is_primary: false }))
    vi.stubGlobal('fetch', fetchMock)
    const changed = vi.fn()
    const user = userEvent.setup()

    render(<MaterialLibrary materials={materials} onChanged={changed} />)

    expect(screen.getAllByText('重点材料')).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: '取消 教材 A 的重点材料标记' }))
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/materials/10',
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ is_primary: false }) }),
    )
    expect(changed).toHaveBeenCalledOnce()
  })
})
