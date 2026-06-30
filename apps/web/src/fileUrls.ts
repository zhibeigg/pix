import { API_BASE, TOKEN_KEY } from './api'

export function signedFileUrl(url?: string | null) {
  if (!url) return ''
  if (!url.startsWith('/files')) return url
  const token = localStorage.getItem(TOKEN_KEY)
  const separator = url.includes('?') ? '&' : '?'
  const withToken = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url
  return `${API_BASE}${withToken.startsWith('/') ? withToken : `/${withToken}`}`
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
