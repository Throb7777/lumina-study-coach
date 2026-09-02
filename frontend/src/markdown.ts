const outerMarkdownFence = /^\s*```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/i
const fenceLine = /^\s*(`{3,}|~{3,})/
const listDisplayStart = /^(\s*)((?:[-+*]|\d+[.)]))\s+\\\[\s*$/
const inlineDisplayMath = /\\\[([^\n]+?)\\\]/g
const htmlBreak = /<br\s*\/?>/gi
const inlineMath = /(?<!\\)(?<!\$)\$(?!\$)(.+?)(?<!\\)\$(?!\$)/g
const duplicateLatexCommand = /(?<!\\)\\\\(?=(?:begin|end|mathrm|operatorname|text|frac|dfrac|tfrac|sqrt|mathbb|mathbf|mathcal|mathit|mathsf|mathtt|overline|underline|hat|bar|vec|sum|prod|int|lim|log|ln|sin|cos|tan|exp|omega|alpha|beta|gamma|delta|theta|lambda|mu|sigma|phi|psi|rho|varepsilon|partial|nabla)\b)/g

function controlPattern(code: number, suffix: string) {
  return new RegExp(`${String.fromCharCode(code)}${suffix}`, 'g')
}

const brokenLatexEscapes: Array<[RegExp, string]> = [
  [controlPattern(7, String.raw`omega\b`), String.raw`\omega`],
  [controlPattern(7, String.raw`(?=(?:cdots|dots)\b)`), '\\'],
  [controlPattern(7, String.raw`(?=(?:lpha|ngle|pprox|st)\b)`), String.raw`\a`],
  [controlPattern(8, String.raw`(?=(?:egin|inom|eta)\b)`), String.raw`\b`],
  [controlPattern(12, String.raw`(?=rac\b)`), String.raw`\f`],
  [controlPattern(11, String.raw`(?=(?:dots|ec)\b)`), String.raw`\v`],
  [/\t(?=(?:imes|ext|heta)(?![A-Za-z]))/g, String.raw`\t`],
  [/\r(?=(?:ight|ho)\b)/g, String.raw`\r`],
]

export function normalizeMarkdownMath(content: string) {
  for (const [pattern, replacement] of brokenLatexEscapes) {
    content = content.replace(pattern, replacement)
  }
  const outerMatch = content.match(outerMarkdownFence)
  const source = outerMatch ? outerMatch[1] : content
  let activeFence: string | null = null

  const lines = source.split(/\r?\n/)
  const normalized: string[] = []

  for (let index = 0; index < lines.length; index += 1) {
    let line = lines[index]
    const fenceMatch = line.match(fenceLine)
    if (fenceMatch) {
      const marker = fenceMatch[1][0]
      activeFence = activeFence === marker ? null : marker
      normalized.push(line)
      continue
    }
    if (activeFence !== null) {
      normalized.push(line)
      continue
    }

    line = line.replace(htmlBreak, '  \n')

    const listMatch = line.match(listDisplayStart)
    if (listMatch) {
      let closingIndex = index + 1
      while (closingIndex < lines.length && lines[closingIndex].trim() !== String.raw`\]`) {
        closingIndex += 1
      }
      if (closingIndex < lines.length) {
        const body = lines
          .slice(index + 1, closingIndex)
          .map((part) => part.trim())
          .filter(Boolean)
          .join(' ')
        normalized.push(`${listMatch[1]}${listMatch[2]} $${body}$`)
        index = closingIndex
        continue
      }
    }

    if ([String.raw`\[`, String.raw`\]`].includes(line.trim())) {
      normalized.push(`${line.match(/^\s*/)?.[0] ?? ''}$$`)
      continue
    }
    line = line.replace(inlineDisplayMath, '$$$1$')
    line = line.replaceAll(String.raw`\(`, '$').replaceAll(String.raw`\)`, '$')
    line = line.replace(inlineMath, (_match, body: string) => (
      `$${body.replace(duplicateLatexCommand, '\\')}$`
    ))
    normalized.push(line)
  }

  return normalized.join('\n').trim()
}

export function hasLegacyMathDelimiters(content: string) {
  let activeFence: string | null = null
  return content.split(/\r?\n/).some((line) => {
    const match = line.match(fenceLine)
    if (match) {
      const marker = match[1][0]
      activeFence = activeFence === marker ? null : marker
      return false
    }
    if (activeFence !== null) return false
    return line.includes(String.raw`\(`)
      || line.includes(String.raw`\)`)
      || line.trim() === String.raw`\[`
      || line.trim() === String.raw`\]`
  })
}
