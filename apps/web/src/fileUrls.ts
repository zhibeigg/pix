import { API_BASE, TOKEN_KEY } from './api'

export function signedFileUrl(url?: string | null) {
  if (!url) return ''
  if (!url.startsWith('/files')) return url
  const token = localStorage.getItem(TOKEN_KEY)
  const separator = url.includes('?') ? '&' : '?'
  const withToken = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url
  return `${API_BASE}${withToken.startsWith('/') ? withToken : `/${withToken}`}`
}

export function fileName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path
}
