import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function PixMetric({ label, value, tone = 'default', className }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info'; className?: string }) {
  return (
    <div className={cn('rounded-lg border border-border bg-card p-4', tone === 'success' && 'bg-[hsl(var(--pix-mint))]', tone === 'warning' && 'bg-[hsl(var(--pix-peach))]', tone === 'danger' && 'bg-red-500/10', tone === 'info' && 'bg-[hsl(var(--pix-sky))]', className)}>
      <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-muted-foreground">{label}</p>
      <p className="mt-2 text-[28px] font-semibold leading-[1.25] tracking-tight">{value}</p>
    </div>
  )
}
