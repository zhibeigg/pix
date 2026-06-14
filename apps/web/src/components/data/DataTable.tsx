import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Eyebrow } from '../ui/eyebrow'

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
    <section className="motion-panel-enter overflow-hidden rounded-lg border border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface))] text-[hsl(var(--data-text))] pix-shadow-ledger transition-[border-color,box-shadow,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)]">
      {(eyebrow || title || metrics || filters) && (
        <div className="border-b border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-header))] p-4">
          {(eyebrow || title || metrics) && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
                {title && <h3 className="mt-1 text-xl font-semibold">{title}</h3>}
              </div>
              {metrics && <div className="flex flex-wrap gap-2">{metrics}</div>}
            </div>
          )}
          {filters}
        </div>
      )}
      {/* 桌面：表格视图 */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead className="text-left text-xs text-[hsl(var(--data-text-faint))]">
            <tr className="border-b border-[hsl(var(--data-line))]">
              {columns.map((column) => <th key={column.key} className={cn('px-4 py-3 font-semibold', column.align === 'right' && 'text-right', column.className)}>{column.header}</th>)}
            </tr>
          </thead>
          <tbody className="motion-list-stagger">
            {rows.length === 0 ? <tr><td colSpan={columns.length} className="px-4 py-10 text-center text-[hsl(var(--data-text-faint))]">{empty}</td></tr> : rows.map((row) => <tr key={row.key} className="border-b border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-row))] transition-[background-color,box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-out-quart)] hover:bg-[hsl(var(--data-surface-row-hover))] hover:shadow-[inset_0_0_0_999px_hsl(var(--foreground)/.015)] last:border-b-0">{row.cells.map((cell, index) => <td key={`${row.key}-${columns[index]?.key ?? index}`} className={cn('px-4 py-3', columns[index]?.align === 'right' && 'text-right', columns[index]?.className)}>{cell}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
      {/* 移动：卡片视图（消除 860px 强制横滚） */}
      <div className="p-3 md:hidden">
        {rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-[hsl(var(--data-text-faint))]">{empty}</div>
        ) : (
          <div className="motion-list-stagger grid gap-3">
            {rows.map((row) => (
              <div key={row.key} className="grid gap-1.5 rounded-lg border border-[hsl(var(--data-line))] bg-[hsl(var(--data-surface-row))] p-3">
                {row.cells.map((cell, index) => (
                  <div key={`${row.key}-m-${columns[index]?.key ?? index}`} className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="shrink-0 text-xs font-medium text-[hsl(var(--data-text-faint))]">{columns[index]?.header}</span>
                    <span className={cn('min-w-0 break-words text-right', columns[index]?.className)}>{cell}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
