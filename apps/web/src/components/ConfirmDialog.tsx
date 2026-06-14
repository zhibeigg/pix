import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { CircleAlert, X } from 'lucide-react'
import { useI18n } from '../i18n'
import { Button } from './ui/button'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogOverlay, DialogPortal, DialogTitle } from './ui/dialog'
import { Eyebrow } from './ui/eyebrow'

/**
 * Promise 式确认对话框，取代散落的原生 window.confirm。
 * 用法：const confirm = useConfirm(); if (!(await confirm({ title, ... }))) return
 * 视觉延续 DeleteConfirmDialog（Radix 焦点管理 + aria + 移动端友好）。
 */
export type ConfirmOptions = {
  title: string
  description?: string
  /** 结构化影响说明（每条一行），用于退款/批量等高风险动作。 */
  impactItems?: string[]
  confirmText?: string
  cancelText?: string
  eyebrow?: string
  tone?: 'default' | 'danger'
}

type ConfirmState = ConfirmOptions & { resolve: (value: boolean) => void }

const ConfirmContext = createContext<(options: ConfirmOptions) => Promise<boolean>>(() => Promise.resolve(false))

export function useConfirm() {
  return useContext(ConfirmContext)
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const [state, setState] = useState<ConfirmState | null>(null)

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => setState({ ...options, resolve }))
  }, [])

  const settle = useCallback((result: boolean) => {
    setState((current) => { current?.resolve(result); return null })
  }, [])

  const tone = state?.tone ?? 'default'
  const danger = tone === 'danger'

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog open={Boolean(state)} onOpenChange={(open) => { if (!open) settle(false) }}>
        <DialogPortal>
          <DialogOverlay />
          <DialogPrimitive.Content
            className="fixed left-1/2 top-1/2 z-50 w-[min(500px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card p-0 pix-shadow-dialog focus:outline-none dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]"
            style={{ maxHeight: 'calc(100dvh - 32px)' }}
          >
            {state && (
              <div className="relative grid gap-5 p-6">
                <div className={`pointer-events-none absolute inset-x-0 top-0 h-28 ${danger
                  ? 'bg-[radial-gradient(circle_at_18%_0%,hsl(var(--destructive)/.18),transparent_36%),linear-gradient(180deg,hsl(var(--pix-cream)/.86),transparent)] dark:bg-[radial-gradient(circle_at_18%_0%,hsl(var(--destructive)/.34),transparent_34%),linear-gradient(180deg,hsl(var(--pix-navy)/.82),transparent)]'
                  : 'bg-[radial-gradient(circle_at_20%_0%,hsl(var(--primary)/.18),transparent_38%),linear-gradient(180deg,hsl(var(--pix-mint)/.5),transparent)] dark:bg-[radial-gradient(circle_at_20%_0%,hsl(var(--primary)/.32),transparent_38%),linear-gradient(180deg,hsl(var(--pix-navy)/.72),transparent)]'}`} />
                <DialogHeader className="relative grid grid-cols-[auto_minmax(0,1fr)] gap-3 pr-8">
                  <div className={`grid h-12 w-12 place-items-center rounded-lg border ${danger
                    ? 'border-destructive/24 bg-destructive/10 text-destructive dark:border-[hsl(var(--destructive)/.24)] dark:bg-[hsl(var(--destructive)/.12)] dark:text-[hsl(0_74%_80%)]'
                    : 'border-primary/20 bg-primary/10 text-primary dark:border-primary/30 dark:bg-primary/18'}`}>
                    <CircleAlert className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    {state.eyebrow && <Eyebrow className={danger ? 'text-destructive/75 dark:text-[hsl(0_74%_80%/.78)]' : undefined}>{state.eyebrow}</Eyebrow>}
                    <DialogTitle className="mt-1 text-xl leading-tight">{state.title}</DialogTitle>
                    {state.description && <DialogDescription className="mt-2 leading-6">{state.description}</DialogDescription>}
                  </div>
                </DialogHeader>
                {state.impactItems && state.impactItems.length > 0 && (
                  <div className={`relative grid gap-2 rounded-lg border p-3 text-sm ${danger
                    ? 'border-destructive/18 bg-destructive/7 dark:border-[hsl(var(--destructive)/.18)] dark:bg-[hsl(var(--destructive)/.10)]'
                    : 'border-border bg-muted/40 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]'}`}>
                    {state.impactItems.map((item) => (
                      <div key={item} className="flex items-center gap-2 rounded-md bg-card/72 px-3 py-2 text-muted-foreground dark:bg-black/12 dark:text-white/68">
                        <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-sm text-[10px] font-bold ${danger
                          ? 'bg-destructive/10 text-destructive dark:bg-[hsl(var(--destructive)/.12)] dark:text-[hsl(0_74%_80%)]'
                          : 'bg-primary/10 text-primary'}`}>!</span>
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                )}
                <DialogFooter className="relative">
                  <Button type="button" variant="outline" onClick={() => settle(false)}>{state.cancelText ?? t('common.cancel')}</Button>
                  <Button type="button" variant={danger ? 'destructive' : 'default'} onClick={() => settle(true)}>{state.confirmText ?? t('common.confirm')}</Button>
                </DialogFooter>
              </div>
            )}
            <DialogPrimitive.Close
              className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring"
              onClick={() => settle(false)}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">{t('common.close')}</span>
            </DialogPrimitive.Close>
          </DialogPrimitive.Content>
        </DialogPortal>
      </Dialog>
    </ConfirmContext.Provider>
  )
}
