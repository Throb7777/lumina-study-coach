import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'
import { normalizeMarkdownMath } from '../markdown'

const calloutLabels: Record<string, string> = {
  abstract: '概要',
  info: '补充说明',
  note: '提示',
  tip: '要点',
  warning: '注意',
  example: '示例',
}

function normalizeObsidianCallouts(content: string) {
  return content.replace(
    /^(\s*>\s*)\[!([a-z-]+)\](?:[+-])?\s*(.*)$/gim,
    (_, prefix: string, type: string, title: string) => (
      `${prefix}**@@callout:${type.toLowerCase()}@@${title.trim() || calloutLabels[type.toLowerCase()] || '提示'}**`
    ),
  )
}

export function MarkdownContent({ content, className = '' }: { content: string; className?: string }) {
  return (
    <div className={`markdown-content ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false }]]}
        components={{
          table: ({ children, ...props }) => (
            <div className="markdown-table-scroll" role="region" aria-label="Markdown 表格" tabIndex={0}>
              <table {...props}>{children}</table>
            </div>
          ),
          strong: ({ children, ...props }) => {
            const value = String(children)
            const match = value.match(/^@@callout:([a-z-]+)@@([\s\S]*)$/)
            if (!match) return <strong {...props}>{children}</strong>
            return (
              <strong className={`obsidian-callout__title obsidian-callout__title--${match[1]}`}>
                {match[2]}
              </strong>
            )
          },
        }}
      >
        {normalizeMarkdownMath(normalizeObsidianCallouts(content))}
      </ReactMarkdown>
    </div>
  )
}
