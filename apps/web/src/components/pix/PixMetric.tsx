import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function PixMetric({ label, value, tone = 'default', className }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info'; className?: string }) {
  return (
    <div className={cn('rounded-2xl border border-border bg-card p-4', tone === 'success' && 'bg-emerald-500/10', tone === 'warning' && 'bg-amber-500/10', tone === 'danger' && 'bg-red-500/10', tone === 'info' && 'bg-sky-500/10', className)}>
      <p className="text-xs font-bold uppercase tracking-[.12em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-black tracking-tight">{value}</p>
    </div>
  )
}
