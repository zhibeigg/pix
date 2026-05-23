import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '../../lib/utils'

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef<React.ElementRef<typeof TabsPrimitive.List>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(({ className, ...props }, ref) => (
  <TabsPrimitive.List ref={ref} className={cn('inline-flex min-h-10 items-center justify-center gap-1 rounded-full border border-border bg-transparent p-1 text-muted-foreground', className)} {...props} />
))
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Trigger>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger ref={ref} className={cn('inline-flex min-h-8 items-center justify-center whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium ring-offset-background transition-[background-color,color,box-shadow,opacity,transform] duration-[var(--motion-fast)] ease-[var(--ease-out-quart)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-[hsl(var(--pix-ink))] data-[state=active]:text-white data-[state=active]:shadow-[0_8px_22px_-18px_rgba(15,15,15,.6)]', className)} {...props} />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Content>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content ref={ref} className={cn('mt-4 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', className)} {...props} />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
