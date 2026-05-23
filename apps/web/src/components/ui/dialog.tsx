import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

const Dialog = DialogPrimitive.Root
const DialogTrigger = DialogPrimitive.Trigger
const DialogPortal = DialogPrimitive.Portal
const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef<React.ElementRef<typeof DialogPrimitive.Overlay>, React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay ref={ref} className={cn('motion-panel-enter fixed inset-0 z-50 bg-black/45 backdrop-blur-sm', className)} {...props} />
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName

const DialogContent = React.forwardRef<React.ElementRef<typeof DialogPrimitive.Content>, React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content ref={ref} className={cn('motion-dialog-content fixed left-1/2 top-1/2 z-50 grid w-[min(92vw,560px)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-lg border border-border bg-card p-6 shadow-[0_16px_48px_-8px_rgba(15,15,15,0.16)]', className)} {...props}>
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring">
        <X className="h-4 w-4" />
        <span className="sr-only">关闭</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitive.Content.displayName

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn('flex flex-col gap-1.5 text-left', className)} {...props} />
const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)} {...props} />
const DialogTitle = React.forwardRef<React.ElementRef<typeof DialogPrimitive.Title>, React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>>(({ className, ...props }, ref) => <DialogPrimitive.Title ref={ref} className={cn('text-lg font-bold leading-none tracking-tight', className)} {...props} />)
DialogTitle.displayName = DialogPrimitive.Title.displayName
const DialogDescription = React.forwardRef<React.ElementRef<typeof DialogPrimitive.Description>, React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>>(({ className, ...props }, ref) => <DialogPrimitive.Description ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />)
DialogDescription.displayName = DialogPrimitive.Description.displayName

export { Dialog, DialogPortal, DialogOverlay, DialogTrigger, DialogClose, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription }
