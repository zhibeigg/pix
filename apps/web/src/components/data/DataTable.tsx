import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export type DataColumn = {
  key: string
  header: ReactNode
  align?: 'left' | 'right'
  className?: string
}

export type DataRow = {
  key: string | number
  cells: ReactNode[]
}

type DataTableProps = {
  eyebrow?: ReactNode
  title?: ReactNode
  metrics?: ReactNode
  filters?: ReactNode
  columns: DataColumn[]
  rows: DataRow[]
  empty: ReactNode
}

export function DataTable({ eyebrow, title, metrics, filters, columns, rows, empty }: DataTableProps) {
  return (
    <section className="overflow-hidden rounded-lg border border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface))] text-[hsl(var(--data-text))] shadow-[var(--data-shadow)]">
      {(eyebrow || title || metrics || filters) && (
        <div className="border-b border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-header))] p-4">
          {(eyebrow || title || metrics) && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                {eyebrow && <p className="text-xs font-semibold tracking-[.14em] text-primary">{eyebrow}</p>}
                {title && <h3 className="mt-1 text-xl font-semibold">{title}</h3>}
              </div>
              {metrics && <div className="flex flex-wrap gap-2">{metrics}</div>}
            </div>
          )}
          {filters}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-collapse text-sm">
          <thead className="text-left text-xs text-[hsl(var(--data-text-faint))]">
            <tr className="border-b border-[hsl(var(--data-line))]">
              {columns.map((column) => <th key={column.key} className={cn('px-4 py-3 font-semibold', column.align === 'right' && 'text-right', column.className)}>{column.header}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={columns.length} className="px-4 py-10 text-center text-[hsl(var(--data-text-faint))]">{empty}</td></tr> : rows.map((row) => <tr key={row.key} className="border-b border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-row))] transition hover:bg-[hsl(var(--data-surface-row-hover))] last:border-b-0">{row.cells.map((cell, index) => <td key={`${row.key}-${columns[index]?.key ?? index}`} className={cn('px-4 py-3', columns[index]?.align === 'right' && 'text-right', columns[index]?.className)}>{cell}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
    </section>
  )
}
