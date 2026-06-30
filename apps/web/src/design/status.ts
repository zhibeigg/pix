import type { PixLanguage } from '../theme'
import { jobStatusLabel } from '../labels'

export function statusTone(status: string) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'info'
  if (status === 'waiting') return 'warning'
  if (status === 'cancelled') return 'muted'
  return 'warning'
}

export function statusLabel(status: string, language: PixLanguage = 'zh-CN') {
  return jobStatusLabel(status, language)
}
