import { API_BASE, TOKEN_KEY } from './api'

export function signedFileUrl(url?: string | null, tokenOverride?: string | null, noCache = false) {
  if (!url) return ''
  if (!url.startsWith('/files')) return noCache ? appendNoCache(url) : url
  const token = tokenOverride ?? localStorage.getItem(TOKEN_KEY)
  const separator = url.includes('?') ? '&' : '?'
  const withToken = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url
  const withCachePolicy = noCache ? appendNoCache(withToken) : withToken
  return `${API_BASE}${withCachePolicy.startsWith('/') ? withCachePolicy : `/${withCachePolicy}`}`
}

function appendNoCache(url: string) {
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}_=${Date.now()}`
}

export function publicApiUrl(url?: string | null) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${API_BASE}${url.startsWith('/') ? url : `/${url}`}`
}

export function fileName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path
}

export function spriteActionsZipUrl(jobId: number): string {
  const token = localStorage.getItem(TOKEN_KEY)
  const path = `/jobs/${jobId}/sprite-actions.zip`
  return `${API_BASE}${token ? `${path}?token=${encodeURIComponent(token)}` : path}`
}
