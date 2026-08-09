import { describe, expect, it } from 'vitest'
import { hasLegacyMathDelimiters, normalizeMarkdownMath } from './markdown'

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
})
