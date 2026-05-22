import type { ReactNode } from 'react'

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <section className="relative overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card p-6 shadow-[0_10px_30px_-24px_rgba(15,15,15,0.28)] md:p-8 dark:border-border dark:shadow-[0_1px_2px_rgba(15,15,15,0.04)]">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          {eyebrow && <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-primary">{eyebrow}</p>}
          <h2 className="mt-2 text-4xl font-semibold leading-[1.15] tracking-[-.5px] md:text-5xl">{title}</h2>
          {description && <p className="mt-3 max-w-3xl text-base leading-[1.55] text-muted-foreground">{description}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </section>
  )
}
