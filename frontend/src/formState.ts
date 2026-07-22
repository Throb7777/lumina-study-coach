export function formIsDirty(form: HTMLFormElement) {
  return Array.from(form.elements).some((element) => {
    if (element instanceof HTMLInputElement) {
      if (element.type === 'checkbox' || element.type === 'radio') {
        return element.checked !== element.defaultChecked
      }
      return element.value !== element.defaultValue
    }
    if (element instanceof HTMLTextAreaElement) return element.value !== element.defaultValue
    if (element instanceof HTMLSelectElement) {
      return Array.from(element.options).some((option) => option.selected !== option.defaultSelected)
    }
    return false
  })
}

export function updateFormBaseline(form: HTMLFormElement) {
  Array.from(form.elements).forEach((element) => {
    if (element instanceof HTMLInputElement) {
      element.defaultValue = element.value
      element.defaultChecked = element.checked
    } else if (element instanceof HTMLTextAreaElement) {
      element.defaultValue = element.value
    } else if (element instanceof HTMLSelectElement) {
      Array.from(element.options).forEach((option) => {
        option.defaultSelected = option.selected
      })
    }
  })
}
