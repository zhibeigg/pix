import type { PixLanguage } from './theme'
import { i18n } from './i18n'

export function jobTypeLabel(type: string, language: PixLanguage = 'zh-CN') {
  return i18n.getFixedT(language)(`jobs.type.${type}`, { defaultValue: type })
}

export const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'primary',
  waiting: 'warning',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function jobStatusLabel(status: string, language: PixLanguage = 'zh-CN') {
  return i18n.getFixedT(language)(`jobs.status.${status}`, { defaultValue: status })
}
