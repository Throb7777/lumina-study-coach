const draftPrefix = 'learning-flow-coach.draft.v1.'

interface DraftEnvelope<T> {
  baseline: T
  updatedAt: string
  value: T
  version: 1
}

type FormDraft = Record<string, boolean | string>

function sameValue(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right)
}

function storageKey(key: string) {
  return `${draftPrefix}${key}`
}

export function readDraft<T>(key: string, baseline: T): T | null {
  try {
    const rawDraft = localStorage.getItem(storageKey(key))
    if (!rawDraft) return null
    const draft = JSON.parse(rawDraft) as Partial<DraftEnvelope<T>>
    if (draft.version !== 1 || !('baseline' in draft) || !('value' in draft)) {
      localStorage.removeItem(storageKey(key))
      return null
    }
    if (!sameValue(draft.baseline, baseline)) {
      localStorage.removeItem(storageKey(key))
      return null
    }
    return draft.value as T
  } catch {
    localStorage.removeItem(storageKey(key))
    return null
  }
}

export function writeDraft<T>(key: string, baseline: T, value: T) {
  const draft: DraftEnvelope<T> = {
    baseline,
    updatedAt: new Date().toISOString(),
    value,
    version: 1,
  }
  localStorage.setItem(storageKey(key), JSON.stringify(draft))
}

export function clearDraft(key: string) {
  localStorage.removeItem(storageKey(key))
}

function readForm(form: HTMLFormElement, defaults: boolean): FormDraft {
  const values: FormDraft = {}
  Array.from(form.elements).forEach((element) => {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement)) return
    if (!element.name) return
    if (element instanceof HTMLInputElement && (element.type === 'checkbox' || element.type === 'radio')) {
      values[element.name] = defaults ? element.defaultChecked : element.checked
      return
    }
    if (element instanceof HTMLSelectElement) {
      values[element.name] = defaults
        ? Array.from(element.options).find((option) => option.defaultSelected)?.value ?? element.value
        : element.value
      return
    }
    values[element.name] = defaults ? element.defaultValue : element.value
  })
  return values
}

export function writeFormDraft(key: string, form: HTMLFormElement) {
  writeDraft<FormDraft>(key, readForm(form, true), readForm(form, false))
}

export function clearFormDraft(key: string) {
  clearDraft(key)
}

export function restoreFormDraft(key: string, form: HTMLFormElement) {
  const draft = readDraft<FormDraft>(key, readForm(form, true))
  if (!draft) return false

  Array.from(form.elements).forEach((element) => {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement)) return
    if (!element.name || !(element.name in draft)) return
    const value = draft[element.name]
    if (element instanceof HTMLInputElement && (element.type === 'checkbox' || element.type === 'radio')) {
      element.checked = Boolean(value)
    } else {
      element.value = String(value)
    }
  })
  return true
}
