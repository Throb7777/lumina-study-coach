export type UiFontSize = 'small' | 'standard' | 'large'
export type EditorFontSize = 'small' | 'standard' | 'large'

export interface AppearancePreferences {
  uiFontSize: UiFontSize
  editorFontSize: EditorFontSize
  reduceMotion: boolean
}

export const defaultAppearancePreferences: AppearancePreferences = {
  uiFontSize: 'standard',
  editorFontSize: 'standard',
  reduceMotion: false,
}

const preferencesKey = 'learning-flow-coach.appearance'

function isFontSize(value: unknown): value is UiFontSize {
  return value === 'small' || value === 'standard' || value === 'large'
}

export function readAppearancePreferences(): AppearancePreferences {
  try {
    const saved = JSON.parse(localStorage.getItem(preferencesKey) ?? '{}') as Partial<AppearancePreferences>
    return {
      uiFontSize: isFontSize(saved.uiFontSize) ? saved.uiFontSize : 'standard',
      editorFontSize: isFontSize(saved.editorFontSize) ? saved.editorFontSize : 'standard',
      reduceMotion: saved.reduceMotion === true,
    }
  } catch {
    return defaultAppearancePreferences
  }
}

export function saveAppearancePreferences(preferences: AppearancePreferences) {
  localStorage.setItem(preferencesKey, JSON.stringify(preferences))
}

export function applyAppearancePreferences(preferences: AppearancePreferences) {
  const root = document.documentElement
  root.dataset.uiFontSize = preferences.uiFontSize
  root.dataset.editorFontSize = preferences.editorFontSize
  root.dataset.motion = preferences.reduceMotion ? 'reduced' : 'standard'
}
