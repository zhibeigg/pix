import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva('inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors', {
  variants: {
    variant: {
      default: 'border-transparent bg-primary text-primary-foreground',
      secondary: 'border-transparent bg-secondary text-secondary-foreground',
      outline: 'border-border text-foreground',
      success: 'border-emerald-700/30 bg-emerald-100 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/12 dark:text-emerald-200',
      warning: 'border-amber-700/35 bg-amber-100 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/12 dark:text-amber-200',
      danger: 'border-red-700/30 bg-red-100 text-red-950 dark:border-red-500/30 dark:bg-red-500/12 dark:text-red-200',
      info: 'border-sky-700/35 bg-sky-100 text-sky-950 dark:border-sky-500/30 dark:bg-sky-500/12 dark:text-sky-200',
      muted: 'border-border bg-muted text-foreground/75 dark:text-muted-foreground',
    },
  },
  defaultVariants: { variant: 'default' },
})

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
