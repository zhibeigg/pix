import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva('inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-bold transition-colors', {
  variants: {
    variant: {
      default: 'border-transparent bg-primary text-primary-foreground',
      secondary: 'border-border bg-card text-foreground dark:bg-secondary dark:text-foreground',
      outline: 'border-input bg-card text-foreground dark:border-muted-foreground dark:bg-transparent dark:text-foreground',
      success: 'border-[hsl(var(--pix-brand-green))] bg-card text-foreground dark:bg-card dark:text-foreground',
      warning: 'border-[hsl(var(--pix-brand-orange))] bg-card text-foreground dark:bg-card dark:text-foreground',
      danger: 'border-destructive bg-card text-foreground dark:bg-card dark:text-foreground',
      info: 'border-[hsl(var(--pix-link-blue))] bg-card text-foreground dark:bg-card dark:text-foreground',
      muted: 'border-border bg-secondary text-foreground dark:bg-secondary dark:text-foreground',
    },
  },
  defaultVariants: { variant: 'default' },
})

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
