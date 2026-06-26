import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'motion-action inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium leading-[1.3] transition-[background-color,border-color,box-shadow,color,opacity,transform] duration-[var(--motion-fast)] ease-[var(--ease-out-quart)] hover:will-change-transform hover:shadow-[0_8px_22px_-18px_rgba(15,15,15,.55)] active:shadow-[0_2px_8px_-8px_rgba(15,15,15,.5)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:bg-border disabled:text-[hsl(var(--pix-text-subtle))] disabled:opacity-100 disabled:shadow-none [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:transition-transform [&_svg]:duration-[var(--motion-fast)] [&_svg]:ease-[var(--ease-out-quart)] hover:[&_svg]:translate-x-px',
  {
    variants: {
      variant: {
        default: 'bg-primary bg-[linear-gradient(180deg,hsl(var(--primary)/.92),hsl(var(--primary)))] text-primary-foreground shadow-[inset_0_1px_0_hsl(var(--primary-foreground)/.22),0_10px_22px_-14px_hsl(var(--primary)/.8)] hover:bg-[linear-gradient(180deg,hsl(var(--primary)/.98),hsl(var(--primary-pressed)))] hover:shadow-[inset_0_1px_0_hsl(var(--primary-foreground)/.26),0_16px_32px_-14px_hsl(var(--primary)/.95)] active:bg-[hsl(var(--primary-pressed))] active:shadow-[inset_0_1px_2px_hsl(var(--primary-deep)/.45)]',
        destructive: 'bg-destructive bg-[linear-gradient(180deg,hsl(var(--destructive)/.94),hsl(var(--destructive)))] text-destructive-foreground shadow-[inset_0_1px_0_rgba(255,255,255,.18),0_10px_22px_-14px_hsl(var(--destructive)/.7)] hover:brightness-[1.05] hover:shadow-[inset_0_1px_0_rgba(255,255,255,.2),0_15px_30px_-14px_hsl(var(--destructive)/.85)] active:brightness-95',
        outline: 'border border-[hsl(var(--input))] bg-transparent text-foreground hover:border-[hsl(var(--primary)/.5)] hover:bg-[hsl(var(--primary)/.06)] hover:text-[hsl(var(--primary-deep))] dark:hover:text-foreground',
        secondary: 'border border-border bg-secondary text-secondary-foreground hover:border-[hsl(var(--input))] hover:bg-muted',
        ghost: 'bg-transparent text-foreground hover:bg-secondary',
        link: 'h-auto rounded-sm px-0 text-[hsl(var(--pix-link-blue))] underline-offset-4 hover:underline',
        soft: 'border border-border bg-secondary text-secondary-foreground hover:border-[hsl(var(--input))] hover:bg-muted',
      },
      size: {
        default: 'h-10 px-[18px] py-2.5',
        sm: 'h-8 px-3 text-xs pointer-coarse:h-10 pointer-coarse:px-3.5',
        lg: 'h-11 px-5 py-2.5',
        icon: 'h-10 w-10 pointer-coarse:h-11 pointer-coarse:w-11',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : 'button'
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
})
Button.displayName = 'Button'

export { Button, buttonVariants }
