import type { ReactNode } from 'react'
import { Eyebrow } from './ui/eyebrow'

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <section className="relative overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card p-6 pix-shadow-panel md:p-8 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
          <h1 className="mt-2 text-4xl font-semibold leading-[1.15] tracking-[-.5px] md:text-5xl">{title}</h1>
          {description && <p className="mt-3 max-w-3xl text-base leading-[1.55] text-muted-foreground">{description}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </section>
  )
}
