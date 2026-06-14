import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Eyebrow } from '../ui/eyebrow'

export function PixMetric({ label, value, tone = 'default', className }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info'; className?: string }) {
  return (
    <div className={cn('motion-panel-enter rounded-lg border border-border bg-card p-4 transition-[background-color,border-color,box-shadow,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)] hover:-translate-y-0.5 hover:shadow-[0_14px_34px_-28px_rgba(15,15,15,.48)]', tone === 'success' && 'bg-[hsl(var(--tone-success-surface))] text-[hsl(var(--pix-charcoal))] dark:border-[hsl(var(--tone-success-line))]/20 dark:bg-[hsl(var(--tone-success-line))]/12 dark:text-white', tone === 'warning' && 'bg-[hsl(var(--tone-warning-surface))] text-[hsl(var(--pix-charcoal))] dark:border-[hsl(var(--tone-warning-line))]/20 dark:bg-[hsl(var(--tone-warning-line))]/12 dark:text-white', tone === 'danger' && 'bg-[hsl(var(--destructive))]/10 dark:border-[hsl(var(--destructive))]/20 dark:bg-[hsl(var(--destructive))]/12 dark:text-white', tone === 'info' && 'bg-[hsl(var(--tone-info-surface))] text-[hsl(var(--pix-charcoal))] dark:border-[hsl(var(--tone-info-line))]/20 dark:bg-[hsl(var(--tone-info-line))]/12 dark:text-white', className)}>
      <Eyebrow className="text-muted-foreground">{label}</Eyebrow>
      <p className="mt-2 text-[28px] font-semibold leading-[1.25] tracking-tight">{value}</p>
    </div>
  )
}
