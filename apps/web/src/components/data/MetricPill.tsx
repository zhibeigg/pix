import type { ReactNode } from 'react'

export type DataTone = 'blue' | 'green' | 'rose' | 'amber' | 'slate'

const toneClasses: Record<DataTone, string> = {
  blue: 'bg-[hsl(var(--ledger-pill-blue-bg))] text-[hsl(var(--ledger-pill-blue-fg))] ring-[hsl(var(--ledger-pill-blue-ring))]',
  green: 'bg-[hsl(var(--ledger-pill-green-bg))] text-[hsl(var(--ledger-pill-green-fg))] ring-[hsl(var(--ledger-pill-green-ring))]',
  rose: 'bg-[hsl(var(--ledger-pill-rose-bg))] text-[hsl(var(--ledger-pill-rose-fg))] ring-[hsl(var(--ledger-pill-rose-ring))]',
  amber: 'bg-[hsl(var(--ledger-pill-amber-bg))] text-[hsl(var(--ledger-pill-amber-fg))] ring-[hsl(var(--ledger-pill-amber-ring))]',
  slate: 'bg-[hsl(var(--ledger-pill-slate-bg))] text-[hsl(var(--ledger-pill-slate-fg))] ring-[hsl(var(--ledger-pill-slate-ring))]',
}

export function MetricPill({ label, value, tone = 'slate' }: { label: ReactNode; value: ReactNode; tone?: DataTone }) {
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${toneClasses[tone]}`}><span className="opacity-65">{label}</span>{value}</span>
}
