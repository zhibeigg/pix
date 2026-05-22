import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function PixPanel({ title, eyebrow, description, action, children, className }: { title?: ReactNode; eyebrow?: ReactNode; description?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <section className={cn('overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card shadow-[0_10px_30px_-24px_rgba(15,15,15,0.28)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))] dark:shadow-[0_22px_70px_-48px_rgba(0,0,0,0.95)]', className)}>
      {(title || eyebrow || description || action) && (
        <header className="flex flex-col gap-3 border-b border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper)/.45)] p-6 md:flex-row md:items-start md:justify-between dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft)/.52)]">
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
