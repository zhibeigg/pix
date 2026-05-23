import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function PixMetric({ label, value, tone = 'default', className }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info'; className?: string }) {
  return (
    <div className={cn('motion-panel-enter rounded-lg border border-border bg-card p-4 transition-[background-color,border-color,box-shadow,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)] hover:-translate-y-0.5 hover:shadow-[0_14px_34px_-28px_rgba(15,15,15,.48)]', tone === 'success' && 'bg-[hsl(var(--pix-mint))] text-[hsl(var(--pix-charcoal))] dark:border-emerald-300/20 dark:bg-emerald-500/12 dark:text-white', tone === 'warning' && 'bg-[hsl(var(--pix-peach))] text-[hsl(var(--pix-charcoal))] dark:border-amber-300/20 dark:bg-amber-500/12 dark:text-white', tone === 'danger' && 'bg-red-500/10 dark:border-red-300/20 dark:bg-red-500/12 dark:text-white', tone === 'info' && 'bg-[hsl(var(--pix-sky))] text-[hsl(var(--pix-charcoal))] dark:border-sky-300/20 dark:bg-sky-500/12 dark:text-white', className)}>
      <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-muted-foreground">{label}</p>
      <p className="mt-2 text-[28px] font-semibold leading-[1.25] tracking-tight">{value}</p>
    </div>
  )
}
