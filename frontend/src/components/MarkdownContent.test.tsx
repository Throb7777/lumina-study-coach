import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AiTaskStatus } from './AiTaskStatus'
import { EditableMarkdown } from './EditableMarkdown'
import { MarkdownContent } from './MarkdownContent'

describe('Markdown content', () => {
  it('renders Markdown and formulas instead of raw source', () => {
    const { container } = render(
      <MarkdownContent content={String.raw`## 条件概率

$$P(A\mid B)=\frac{P(A\cap B)}{P(B)}$$`} />,
    )

    expect(screen.getByRole('heading', { name: '条件概率' })).toBeInTheDocument()
    expect(container.querySelector('.katex')).not.toBeNull()
    expect(container.querySelector('.katex-html')).not.toBeNull()
  })

  it('opens generated content in reading mode and allows editing', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <form>
        <EditableMarkdown
          title="练习题目"
          description="已生成"
          name="ai_questions"
          defaultValue={'## 第一题\n\n说明条件概率。'}
        />
      </form>,
    )

    expect(screen.getByRole('heading', { name: '第一题' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '练习题目' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '编辑练习题目' }))
    expect(screen.getByRole('textbox', { name: '练习题目' })).toHaveValue('## 第一题\n\n说明条件概率。')

    rerender(
      <form>
        <EditableMarkdown
          title="练习题目"
          description="已生成"
          name="ai_questions"
          defaultValue={'## 第二题\n\n重新生成的内容。'}
        />
      </form>,
    )
    expect(screen.getByRole('heading', { name: '第二题' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '练习题目' })).not.toBeInTheDocument()
  })

  it('renders legacy display formulas nested in list items', () => {
    const { container } = render(
      <MarkdownContent content={String.raw`### 第3题

- \[
P(A)=\frac{4}{9}
\]

---

### 第4题`} />,
    )

    expect(screen.getByRole('heading', { name: '第3题' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '第4题' })).toBeInTheDocument()
    expect(container.querySelectorAll('.katex')).toHaveLength(1)
    expect(container).not.toHaveTextContent(String.raw`\[`)
  })

  it('shows a task-specific generation state', () => {
    render(<AiTaskStatus label="正在生成练习题" />)
    expect(screen.getByRole('status')).toHaveTextContent('正在生成练习题')
    expect(screen.getByRole('status')).toHaveTextContent('0 秒')
  })

  it('renders Obsidian callouts and model HTML breaks as readable blocks', () => {
    const { container } = render(
      <MarkdownContent content={'> [!warning] 使用条件\n> 分母必须非零。\n\n第一行<br>第二行'} />,
    )

    expect(container.querySelector('blockquote')).toHaveTextContent('分母必须非零。')
    expect(screen.getByText('使用条件')).toHaveClass('obsidian-callout__title--warning')
    expect(container.querySelector('br')).not.toBeNull()
  })

  it('renders GFM tables and task syntax as structured content', () => {
    const { container } = render(
      <MarkdownContent content={`| 方法 | 适用条件 | 误差 |
| :--- | :---: | ---: |
| 梯度下降 | 可微目标 | $10^{-3}$ |
| 牛顿法 | Hessian 可逆 | ~~较大~~ 较小 |

- [x] 已掌握定义
- [ ] 继续推导`} />,
    )

    const table = container.querySelector('table')
    const headers = table?.querySelectorAll('th') ?? []
    const rows = table?.querySelectorAll('tbody tr') ?? []
    const taskInputs = container.querySelectorAll<HTMLInputElement>('.task-list-item input')
    expect(table).toHaveTextContent('梯度下降')
    expect(headers[1]).toHaveStyle({ textAlign: 'center' })
    expect(rows[1].querySelectorAll('td')[2]).toHaveStyle({ textAlign: 'right' })
    expect(container.querySelector('.markdown-table-scroll')).not.toBeNull()
    expect(container.querySelector('.katex')).not.toBeNull()
    expect(container.querySelector('del')).toHaveTextContent('较大')
    expect(taskInputs[0]).toBeChecked()
    expect(taskInputs[1]).not.toBeChecked()
  })
})
