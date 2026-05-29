import { useCallback, useEffect, useRef, useState } from 'react'

const TURNSTILE_SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
const TURNSTILE_SCRIPT_ID = 'cf-turnstile-script'

type TurnstileWidgetOptions = {
  sitekey: string
  callback: (token: string) => void
  'error-callback'?: () => void
  'expired-callback'?: () => void
  'timeout-callback'?: () => void
  theme?: 'light' | 'dark' | 'auto'
  size?: 'normal' | 'compact' | 'flexible'
  appearance?: 'always' | 'execute' | 'interaction-only'
  language?: string
  'response-field'?: boolean
}

type TurnstileApi = {
  render: (container: HTMLElement, options: TurnstileWidgetOptions) => string
  reset: (widgetId?: string) => void
  remove: (widgetId?: string) => void
  getResponse: (widgetId?: string) => string | undefined
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
    onTurnstileScriptLoad?: () => void
  }
}

let scriptPromise: Promise<TurnstileApi> | null = null

function loadTurnstileScript(): Promise<TurnstileApi> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Turnstile is only available in the browser'))
  }
  if (window.turnstile) return Promise.resolve(window.turnstile)
  if (scriptPromise) return scriptPromise

  scriptPromise = new Promise<TurnstileApi>((resolve, reject) => {
    const existing = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', () => {
        if (window.turnstile) resolve(window.turnstile)
        else reject(new Error('Turnstile script loaded but global is missing'))
      })
      existing.addEventListener('error', () => reject(new Error('Failed to load Turnstile script')))
      return
    }

    const script = document.createElement('script')
    script.id = TURNSTILE_SCRIPT_ID
    script.src = TURNSTILE_SCRIPT_URL
    script.async = true
    script.defer = true
    script.addEventListener('load', () => {
      if (window.turnstile) resolve(window.turnstile)
      else reject(new Error('Turnstile script loaded but global is missing'))
    })
    script.addEventListener('error', () => {
      scriptPromise = null
      reject(new Error('Failed to load Turnstile script'))
    })
    document.head.appendChild(script)
  })

  return scriptPromise
}

export type UseTurnstileOptions = {
  enabled: boolean
  siteKey: string
  theme?: 'light' | 'dark' | 'auto'
  language?: string
}

export type UseTurnstileResult = {
  containerRef: (node: HTMLDivElement | null) => void
  token: string
  ready: boolean
  error: string | null
  reset: () => void
}

export function useTurnstile({ enabled, siteKey, theme = 'auto', language }: UseTurnstileOptions): UseTurnstileResult {
  const [token, setToken] = useState('')
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const widgetIdRef = useRef<string | null>(null)
  const containerNodeRef = useRef<HTMLDivElement | null>(null)
  const apiRef = useRef<TurnstileApi | null>(null)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  const cleanup = useCallback(() => {
    const api = apiRef.current
    const id = widgetIdRef.current
    if (api && id) {
      try { api.remove(id) } catch { /* ignore */ }
    }
    widgetIdRef.current = null
    setToken('')
    setReady(false)
  }, [])

  const mount = useCallback(() => {
    const node = containerNodeRef.current
    if (!enabled || !siteKey || !node) return
    setError(null)
    loadTurnstileScript()
      .then((api) => {
        apiRef.current = api
        if (!enabledRef.current || !containerNodeRef.current) return
        if (widgetIdRef.current) return
        try {
          const id = api.render(containerNodeRef.current, {
            sitekey: siteKey,
            theme,
            language,
            'response-field': false,
            callback: (value: string) => {
              setToken(value)
              setReady(true)
              setError(null)
            },
            'error-callback': () => {
              setToken('')
              setReady(false)
              setError('人机校验加载失败，请重试')
            },
            'expired-callback': () => {
              setToken('')
              setReady(false)
            },
            'timeout-callback': () => {
              setToken('')
              setReady(false)
            },
          })
          widgetIdRef.current = id
        } catch (renderError) {
          setError(renderError instanceof Error ? renderError.message : '人机校验渲染失败')
        }
      })
      .catch((loadError: unknown) => {
        setError(loadError instanceof Error ? loadError.message : '人机校验加载失败')
      })
  }, [enabled, siteKey, theme, language])

  const containerRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (containerNodeRef.current === node) return
      cleanup()
      containerNodeRef.current = node
      if (node && enabled && siteKey) mount()
    },
    [cleanup, enabled, siteKey, mount],
  )

  useEffect(() => {
    if (!enabled || !siteKey) {
      cleanup()
      return
    }
    if (containerNodeRef.current && !widgetIdRef.current) mount()
  }, [enabled, siteKey, mount, cleanup])

  useEffect(() => () => cleanup(), [cleanup])

  const reset = useCallback(() => {
    const api = apiRef.current
    const id = widgetIdRef.current
    setToken('')
    setReady(false)
    if (api && id) {
      try { api.reset(id) } catch { /* ignore */ }
    }
  }, [])

  return { containerRef, token, ready, error, reset }
}
