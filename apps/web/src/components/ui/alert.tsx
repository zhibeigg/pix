import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const alertVariants = cva('motion-panel-enter relative w-full rounded-md border p-4 text-sm leading-6 transition-[background-color,border-color,box-shadow,opacity,transform] duration-[var(--motion-base)] ease-[var(--ease-out-quart)]', {
  variants: {
    variant: {
      default: 'border-border bg-card text-card-foreground',
      info: 'border-[hsl(var(--tone-info-line))]/30 bg-[hsl(var(--tone-info-surface))]/70 text-foreground',
      success: 'border-[hsl(var(--tone-success-line))]/30 bg-[hsl(var(--tone-success-surface))]/80 text-foreground',
      warning: 'border-[hsl(var(--tone-warning-line))]/30 bg-[hsl(var(--tone-warning-surface))]/80 text-foreground',
      destructive: 'border-destructive/35 bg-destructive/10 text-destructive dark:text-[hsl(0_90%_92%)]',
    },
  },
  defaultVariants: { variant: 'default' },
})

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof alertVariants> {}

export function Alert({ className, variant, ...props }: AlertProps) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn('mb-1 font-bold leading-none tracking-tight', className)} {...props} />
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('text-sm leading-relaxed opacity-90', className)} {...props} />
}
