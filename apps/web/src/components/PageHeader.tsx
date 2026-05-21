import type { ReactNode } from 'react'

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-border bg-card/86 p-6 shadow-[0_24px_70px_hsl(31_35%_10%/.08)] md:p-8">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/60 via-[hsl(var(--pix-sky))] to-[hsl(var(--pix-amber))]" />
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          {eyebrow && <p className="text-xs font-black uppercase tracking-[.16em] text-primary">{eyebrow}</p>}
          <h2 className="mt-2 text-3xl font-black tracking-tight md:text-5xl">{title}</h2>
          {description && <p className="mt-3 max-w-3xl text-base leading-7 text-muted-foreground">{description}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </section>
  )
}
