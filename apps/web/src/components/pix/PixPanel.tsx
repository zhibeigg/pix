import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function PixPanel({ title, eyebrow, description, action, children, className }: { title?: ReactNode; eyebrow?: ReactNode; description?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <section className={cn('overflow-hidden rounded-3xl border border-border bg-card/92 shadow-[0_24px_70px_hsl(31_35%_10%/.08)]', className)}>
      {(title || eyebrow || description || action) && (
        <header className="flex flex-col gap-3 border-b border-border/70 p-5 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            {eyebrow && <p className="text-xs font-black uppercase tracking-[.16em] text-primary">{eyebrow}</p>}
            {title && <h2 className="mt-1 text-2xl font-black tracking-tight md:text-3xl">{title}</h2>}
            {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}
