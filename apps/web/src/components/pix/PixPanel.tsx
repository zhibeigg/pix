import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function PixPanel({ title, eyebrow, description, action, children, className }: { title?: ReactNode; eyebrow?: ReactNode; description?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <section className={cn('overflow-hidden rounded-lg border border-border bg-card shadow-[0_1px_2px_rgba(15,15,15,0.04)]', className)}>
      {(title || eyebrow || description || action) && (
        <header className="flex flex-col gap-3 border-b border-border p-6 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            {eyebrow && <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-primary">{eyebrow}</p>}
            {title && <h2 className="mt-1 text-[28px] font-semibold leading-[1.25] tracking-tight md:text-3xl">{title}</h2>}
            {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className="p-6">{children}</div>
    </section>
  )
}
