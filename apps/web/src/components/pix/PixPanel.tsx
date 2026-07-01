import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Eyebrow } from '../ui/eyebrow'

export function PixPanel({ title, eyebrow, description, action, children, className }: { title?: ReactNode; eyebrow?: ReactNode; description?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <section className={cn('motion-panel-enter overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card pix-shadow-panel transition-[border-color,box-shadow,opacity,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)] hover:pix-shadow-panel-hover dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]', className)}>
      {(title || eyebrow || description || action) && (
        <header className="flex flex-col gap-3 border-b border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper)/.45)] p-4 md:flex-row md:items-start md:justify-between md:p-6 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft)/.52)]">
          <div className="min-w-0">
            {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
            {title && <h2 className="mt-1 text-2xl font-semibold leading-[1.25] tracking-tight sm:text-[28px] md:text-3xl">{title}</h2>}
            {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className="p-4 md:p-6">{children}</div>
    </section>
  )
}
