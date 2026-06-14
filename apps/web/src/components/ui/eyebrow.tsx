import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

/**
 * 统一的 overline / eyebrow 小标签。
 * 收口全站重复的 `text-[11px] font-semibold uppercase tracking-...` 写法，统一字号、字重与字距。
 * 默认主色，可通过 className 覆盖颜色（如 text-muted-foreground）。
 */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('text-[11px] font-semibold uppercase leading-[1.4] tracking-[0.08em] text-primary', className)}>{children}</p>
}
