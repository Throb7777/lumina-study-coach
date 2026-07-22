import { useEffect, useId, useRef, useState } from 'react'
import { Edit3, Eye } from 'lucide-react'
import { MarkdownContent } from './MarkdownContent'

interface EditableMarkdownProps {
  title: string
  description: string
  name: string
  defaultValue: string
  rows?: number
}

export function EditableMarkdown({
  title,
  description,
  name,
  defaultValue,
  rows = 14,
}: EditableMarkdownProps) {
  const labelId = useId()
  const [editing, setEditing] = useState(!defaultValue.trim())
  const [value, setValue] = useState(defaultValue)
  const previousDefaultValue = useRef(defaultValue)

  useEffect(() => {
    if (previousDefaultValue.current === defaultValue) return
    previousDefaultValue.current = defaultValue
    setValue(defaultValue)
    setEditing(!defaultValue.trim())
  }, [defaultValue])

  return (
    <div className="editable-markdown">
      <div className="editable-markdown__header">
        <span className="field-label-copy">
          <strong id={labelId}>{title}</strong>
          <span>{description}</span>
        </span>
        <button
          className="text-button editable-markdown__toggle"
          type="button"
          aria-label={editing ? `预览${title}` : `编辑${title}`}
          onClick={() => setEditing((current) => !current)}
        >
          {editing ? <Eye size={14} /> : <Edit3 size={14} />}
          {editing ? '查看预览' : '编辑内容'}
        </button>
      </div>
      {editing ? (
        <textarea
          aria-labelledby={labelId}
          name={name}
          rows={rows}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
      ) : (
        <>
          <input type="hidden" name={name} value={value} />
          <MarkdownContent content={value} className="editable-markdown__reader" />
        </>
      )}
    </div>
  )
}
