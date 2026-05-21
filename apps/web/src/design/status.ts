import { jobStatusLabel } from '../labels'

export function statusTone(status: string) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'info'
  if (status === 'cancelled') return 'muted'
  return 'warning'
}

export function statusLabel(status: string) {
  return jobStatusLabel(status)
}

export function statusClass(status: string) {
  const tone = statusTone(status)
  if (tone === 'success') return 'border-emerald-500/30 bg-emerald-500/12 text-emerald-800 dark:text-emerald-200'
  if (tone === 'danger') return 'border-red-500/30 bg-red-500/12 text-red-800 dark:text-red-200'
  if (tone === 'info') return 'border-sky-500/30 bg-sky-500/12 text-sky-800 dark:text-sky-200'
  if (tone === 'warning') return 'border-amber-500/30 bg-amber-500/12 text-amber-900 dark:text-amber-200'
  return 'border-border bg-muted text-muted-foreground'
}
