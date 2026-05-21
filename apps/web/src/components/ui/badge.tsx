import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva('inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors', {
  variants: {
    variant: {
      default: 'border-transparent bg-primary text-primary-foreground',
      secondary: 'border-transparent bg-secondary text-secondary-foreground',
      outline: 'border-border text-foreground',
      success: 'border-emerald-500/30 bg-emerald-500/12 text-emerald-800 dark:text-emerald-200',
      warning: 'border-amber-500/30 bg-amber-500/12 text-amber-900 dark:text-amber-200',
      danger: 'border-red-500/30 bg-red-500/12 text-red-800 dark:text-red-200',
      info: 'border-sky-500/30 bg-sky-500/12 text-sky-800 dark:text-sky-200',
      muted: 'border-border bg-muted text-muted-foreground',
    },
  },
  defaultVariants: { variant: 'default' },
})

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
