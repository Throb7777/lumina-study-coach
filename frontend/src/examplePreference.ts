const exampleDismissedKey = 'lumina.example-dismissed'

export function isBundledExampleVisible() {
  return window.localStorage.getItem(exampleDismissedKey) !== 'true'
}

export function dismissBundledExample() {
  window.localStorage.setItem(exampleDismissedKey, 'true')
}
