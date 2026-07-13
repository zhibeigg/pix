import { useCallback, useEffect, useRef, useState } from 'react'

export type AdminAsyncState<T> = {
  data: T | null
  loading: boolean
  refreshing: boolean
  error: string
  loaded: boolean
  refresh: () => Promise<void>
}

export function useAdminResource<T>(enabled: boolean, loader: () => Promise<T>): AdminAsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const loadedRef = useRef(false)
  const attemptedRef = useRef(false)
  const requestRef = useRef(0)

  const refresh = useCallback(async () => {
    const requestId = ++requestRef.current
    if (loadedRef.current) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const result = await loader()
      if (requestRef.current !== requestId) return
      setData(result)
      loadedRef.current = true
    } catch (reason) {
      if (requestRef.current !== requestId) return
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      if (requestRef.current === requestId) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [loader])

  useEffect(() => {
    if (!enabled || loadedRef.current || attemptedRef.current) return
    attemptedRef.current = true
    void refresh()
  }, [enabled, refresh])

  return { data, loading, refreshing, error, loaded: loadedRef.current, refresh }
}
