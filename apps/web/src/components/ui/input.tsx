import * as React from 'react'
import { cn } from '../../lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => (
  <input
    type={type}
    className={cn('flex h-11 w-full rounded-md border border-input bg-card px-4 py-2 text-base text-foreground transition-[background-color,border-color,box-shadow,color,opacity,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)] file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[hsl(var(--pix-text-subtle))] hover:border-primary/55 focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:shadow-[0_12px_26px_-22px_hsl(var(--primary)/.72)] disabled:cursor-not-allowed disabled:bg-secondary disabled:text-muted-foreground', className)}
    ref={ref}
    {...props}
  />
))
Input.displayName = 'Input'

export { Input }
