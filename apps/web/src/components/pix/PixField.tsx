import { useId, isValidElement, cloneElement, type ReactNode } from 'react'
import { Label } from '../ui/label'
import { cn } from '../../lib/utils'

export function PixField({ label, hint, children, className }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  const id = useId()
  const child = isValidElement(children) ? cloneElement(children as React.ReactElement<{ id?: string }>, { id: (children as React.ReactElement<{ id?: string }>).props.id ?? id }) : children
  return (
    <div className={cn('grid gap-2', className)}>
      <Label htmlFor={id}>{label}</Label>
      {child}
      {hint && <p className="text-xs leading-5 text-muted-foreground">{hint}</p>}
    </div>
  )
}
