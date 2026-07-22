import { afterEach, describe, expect, it } from 'vitest'
import {
  clearDraft,
  readDraft,
  restoreFormDraft,
  writeDraft,
  writeFormDraft,
} from './draftStorage'

afterEach(() => {
  localStorage.clear()
  document.body.replaceChildren()
})

describe('draftStorage', () => {
  it('restores a draft only while its server baseline still matches', () => {
    writeDraft('note-1', 'saved content', 'unfinished content')

    expect(readDraft('note-1', 'saved content')).toBe('unfinished content')
    expect(readDraft('note-1', 'newer server content')).toBeNull()
    expect(readDraft('note-1', 'saved content')).toBeNull()
  })

  it('restores named form fields against the original form baseline', () => {
    const originalForm = document.createElement('form')
    originalForm.innerHTML = '<textarea name="answer">saved answer</textarea><select name="kind"><option value="concept" selected>Concept</option><option value="calculation">Calculation</option></select>'
    const originalAnswer = originalForm.elements.namedItem('answer') as HTMLTextAreaElement
    const originalKind = originalForm.elements.namedItem('kind') as HTMLSelectElement
    originalAnswer.value = 'unfinished answer'
    originalKind.value = 'calculation'
    writeFormDraft('form-1', originalForm)

    const restoredForm = document.createElement('form')
    restoredForm.innerHTML = '<textarea name="answer">saved answer</textarea><select name="kind"><option value="concept" selected>Concept</option><option value="calculation">Calculation</option></select>'

    expect(restoreFormDraft('form-1', restoredForm)).toBe(true)
    expect((restoredForm.elements.namedItem('answer') as HTMLTextAreaElement).value).toBe('unfinished answer')
    expect((restoredForm.elements.namedItem('kind') as HTMLSelectElement).value).toBe('calculation')
  })

  it('clears a stored draft explicitly', () => {
    writeDraft('course-1', '', 'draft')
    clearDraft('course-1')

    expect(readDraft('course-1', '')).toBeNull()
  })
})
