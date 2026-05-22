import type { ReactNode } from 'react'

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="mt-4 grid gap-2 lg:grid-cols-[150px_150px_160px_minmax(180px,1fr)_auto]">{children}</div>
}

export const dataInputClass = 'h-9 border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-row))] text-[hsl(var(--data-text))] placeholder:text-[hsl(var(--data-text-faint))]'

export const dataSelectClass = 'h-9 rounded-md border border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-row))] px-3 text-sm text-[hsl(var(--data-text))] outline-none focus:ring-2 focus:ring-ring'

export const dataOptionClass = 'bg-[hsl(var(--data-surface))] text-[hsl(var(--data-text))]'
