import { useSyncExternalStore } from 'react'
import type { PixLanguage, PixThemeMode } from '../theme'

/**
 * 全局「悬浮预览」store：让主题 / 语言切换菜单在 hover 选项时整页实时预览，
 * 移开即还原、点击才真正提交。用外部 store 订阅，避免从 main → App → header 层层透传 props。
 * 预览态不写 localStorage，不改已提交的偏好。
 */
type PreviewState = { theme: PixThemeMode | null; language: PixLanguage | null }

let state: PreviewState = { theme: null, language: null }
const listeners = new Set<() => void>()

function set(next: Partial<PreviewState>) {
  const merged: PreviewState = { ...state, ...next }
  if (merged.theme === state.theme && merged.language === state.language) return
  state = merged
  for (const listener of listeners) listener()
}

export function setPreviewTheme(theme: PixThemeMode | null) { set({ theme }) }
export function setPreviewLanguage(language: PixLanguage | null) { set({ language }) }
export function clearPreview() { set({ theme: null, language: null }) }

function subscribe(callback: () => void) {
  listeners.add(callback)
  return () => { listeners.delete(callback) }
}

function getSnapshot() { return state }

export function usePreview(): PreviewState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
