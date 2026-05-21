import type { ReactNode } from 'react'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { PixPanel } from './pix/PixPanel'

export const authTextFieldSx = {}

export function AuthCardFrame({ eyebrow, title, subtitle, actionLabel, onAction, children }: { eyebrow: string; title: string; subtitle: string; actionLabel?: string; onAction?: () => void; children: ReactNode }) {
  return <PixPanel eyebrow={eyebrow} title={title} description={subtitle} action={actionLabel && onAction ? <Button variant="outline" onClick={onAction}>{actionLabel}</Button> : undefined}>{children}</PixPanel>
}

export function AuthInlineAlert({ severity = 'info', children }: { severity?: 'success' | 'info' | 'error' | 'warning'; children: ReactNode }) {
  return <Alert variant={severity === 'error' ? 'destructive' : severity}>{children}</Alert>
}
