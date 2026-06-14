import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../api'
import type { AppToastState, ToastVariant } from '../components/AppOverlays'

type TextFn = (zh: string, en: string) => string

/**
 * Toast 反馈层：toast 状态、setMessage/showError 派发、按变体自动消失。
 * 从 App.tsx 抽取，集中应用内的一次性提示逻辑。
 */
export function useToast(text: TextFn) {
  const [toast, setToast] = useState<AppToastState | null>(null)

  const dismissToast = useCallback(() => setToast(null), [])

  const setMessage = useCallback((message: string, variant: ToastVariant = 'success') => {
    setToast(message ? { id: Date.now(), message, variant } : null)
  }, [])

  const showError = useCallback((error: unknown) => {
    if (error instanceof ApiError) setMessage(error.message, 'error')
    else if (error instanceof Error) setMessage(error.message, 'error')
    else setMessage(text('发生未知错误', 'Unknown error'), 'error')
  }, [setMessage, text])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), toast.variant === 'error' ? 5200 : 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  return { toast, setMessage, showError, dismissToast }
}
