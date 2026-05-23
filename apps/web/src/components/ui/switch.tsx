import * as React from 'react'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import { cn } from '../../lib/utils'

const Switch = React.forwardRef<React.ElementRef<typeof SwitchPrimitive.Root>, React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root className={cn('peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border border-transparent bg-muted transition-[background-color,box-shadow,opacity,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)] hover:shadow-[0_8px_20px_-18px_hsl(var(--primary)/.8)] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary', className)} {...props} ref={ref}>
    <SwitchPrimitive.Thumb className="pointer-events-none block h-5 w-5 rounded-full bg-card shadow-lg ring-0 transition-transform duration-[var(--motion-base)] ease-[var(--ease-out-quint)] data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0" />
  </SwitchPrimitive.Root>
))
Switch.displayName = SwitchPrimitive.Root.displayName

export { Switch }
