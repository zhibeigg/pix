import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva('inline-flex items-center rounded-full border px-2.5 py-1 text-[13px] font-semibold leading-[1.4] transition-colors', {
  variants: {
    variant: {
      default: 'border-transparent bg-primary text-primary-foreground',
      secondary: 'border-border bg-[hsl(var(--pix-lavender))] text-[hsl(var(--pix-brand-purple-800))]',
      outline: 'border-input bg-card text-foreground dark:border-muted-foreground dark:bg-transparent dark:text-foreground',
      success: 'border-transparent bg-[hsl(var(--pix-mint))] text-[hsl(var(--pix-brand-green))]',
      warning: 'border-transparent bg-[hsl(var(--pix-peach))] text-[hsl(var(--pix-brand-orange-deep))]',
      danger: 'border-destructive/30 bg-card text-destructive dark:bg-card',
      info: 'border-transparent bg-[hsl(var(--pix-sky))] text-[hsl(var(--pix-link-blue))]',
      muted: 'border-border bg-secondary text-muted-foreground dark:bg-secondary',
    },
  },
  defaultVariants: { variant: 'default' },
})

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
