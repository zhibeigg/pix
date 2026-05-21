import type { ReactNode } from 'react'
import { Label } from '../ui/label'
import { cn } from '../../lib/utils'

export function PixField({ label, hint, children, className }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn('grid gap-2', className)}>
      <Label>{label}</Label>
      {children}
      {hint && <p className="text-xs leading-5 text-muted-foreground">{hint}</p>}
    </div>
  )
}
