import { describe, expect, it } from 'vitest'
import { hasLegacyMathDelimiters, normalizeCompactFeedbackMath, normalizeMarkdownMath } from './markdown'

describe('Compact feedback formulas', () => {
  it.each([
    '正文\n\n```text\n$$x=1$$\n```',
    '示例 `$$x=1$$` 不变。',
    '正文\n\n    $$x=1$$',
    '$$\nx=1\ny=2\n$$',
    String.raw`$$\begin{cases}x&=1\\y&=2\end{cases}$$`,
    `$$${'x+'.repeat(100)}1$$`,
    '$$\nx=1',
    '可得\n\n$x=1$',
  ])('preserves code and explicit structure: %s', (source) => {
    expect(normalizeCompactFeedbackMath(source)).toBe(source)
  })

  it.each(['# 定义：', '---', '独立段落。', '```text\ncode\n```', '> 引用：'])(
    'keeps unrelated blocks separate: %s', (prefix) => {
      expect(normalizeCompactFeedbackMath(`${prefix}\n\n$$x=1$$`)).toBe(`${prefix}\n\n$x=1$`)
    },
  )

  it('joins short formulas to their introduction and is idempotent', () => {
    const result = normalizeCompactFeedbackMath('- 可得\n\n$$x=1$$\n\n最大化它等价于最大化\n\n$$L=x$$')
    expect(result).toBe('- 可得 $x=1$\n\n最大化它等价于最大化 $L=x$')
    expect(normalizeCompactFeedbackMath(result)).toBe(result)
  })
})

describe('Markdown math normalization', () => {
  it('converts legacy delimiters outside code fences', () => {
    const source = [
      String.raw`\[`,
      String.raw`P(A\mid B)=\frac{P(A\cap B)}{P(B)}`,
      String.raw`\]`,
      '',
      String.raw`正文 \(x+y\)`,
      '',
      '```text',
      String.raw`\(keep\)`,
      '```',
    ].join('\n')

    expect(normalizeMarkdownMath(source)).toBe([
      '$$',
      String.raw`P(A\mid B)=\frac{P(A\cap B)}{P(B)}`,
      '$$',
      '',
      '正文 $x+y$',
      '',
      '```text',
      String.raw`\(keep\)`,
      '```',
    ].join('\n'))
    expect(hasLegacyMathDelimiters(source)).toBe(true)
    expect(hasLegacyMathDelimiters(normalizeMarkdownMath(source))).toBe(false)
  })

  it('keeps list formulas from consuming later Markdown sections', () => {
    const source = [
      '### 第3题',
      '',
      String.raw`- \[`,
      String.raw`P(A)=\frac{4}{9}`,
      String.raw`\]`,
      String.raw`- \[P(B\mid A)=\frac{3}{8}\]`,
      '',
      '---',
      '',
      '### 第4题',
    ].join('\n')

    expect(normalizeMarkdownMath(source)).toBe([
      '### 第3题',
      '',
      String.raw`- $P(A)=\frac{4}{9}$`,
      String.raw`- $P(B\mid A)=\frac{3}{8}$`,
      '',
      '---',
      '',
      '### 第4题',
    ].join('\n'))
  })

  it('normalizes HTML breaks only outside fenced code', () => {
    expect(normalizeMarkdownMath('第一行<br>第二行\n\n```html\n<br>\n```')).toBe(
      '第一行  \n第二行\n\n```html\n<br>\n```',
    )
  })

  it('repairs JSON control characters that replaced common LaTeX escapes', () => {
    const source = '$P(\x07omega)=\x0crac{1}{2}$ and $\x08inom{n}{k}$'

    expect(normalizeMarkdownMath(source)).toBe(
      String.raw`$P(\omega)=\frac{1}{2}$ and $\binom{n}{k}$`,
    )
  })

  it('repairs duplicate command escapes only inside inline math', () => {
    const source = [
      String.raw`协方差 $\\mathrm{Cov}(X,Y)$。`,
      '',
      '$$',
      String.raw`\\begin{aligned}x&=1\\y&=2\\end{aligned}`,
      '$$',
    ].join('\n')

    expect(normalizeMarkdownMath(source)).toBe([
      String.raw`协方差 $\mathrm{Cov}(X,Y)$。`,
      '',
      '$$',
      String.raw`\\begin{aligned}x&=1\\y&=2\\end{aligned}`,
      '$$',
    ].join('\n'))
  })
})
