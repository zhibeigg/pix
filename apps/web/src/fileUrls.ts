import { API_BASE, SESSION_AUTH_MARKER } from './api'

// 文件访问票据缓存：短时效、单用途（scope=file）令牌，替代把长期登录 token 明文拼进
// <img>/下载 URL。票据在登录后主动预取并定时刷新，signedFileUrl 保持同步读取缓存。
let cachedTicket = ''
let ticketExpiresAt = 0
let inflight: Promise<string> | null = null

const TICKET_REFRESH_SKEW_MS = 60_000
const TICKETED_URL_PREFIXES = ['/files', '/shares', '/admin/shares']

export function clearFileTicket() {
  cachedTicket = ''
  ticketExpiresAt = 0
  inflight = null
}

function ticketFresh(): boolean {
  return Boolean(cachedTicket) && Date.now() < ticketExpiresAt - TICKET_REFRESH_SKEW_MS
}

/**
 * 主动获取/刷新文件票据。应在登录后与临过期前调用（见 App.tsx）。
 * 返回当前可用票据；失败时保留旧票据（可能为空）。
 */
export async function prefetchFileTicket(_sessionMarker?: string | null): Promise<string> {
  if (ticketFresh()) return cachedTicket
  if (inflight) return inflight
  inflight = (async () => {
    try {
      const response = await fetch(`${API_BASE}/files/ticket`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      })
      if (!response.ok) return cachedTicket
      const body = (await response.json()) as { ticket?: string; expires_in?: number }
      if (body.ticket) {
        cachedTicket = body.ticket
        ticketExpiresAt = Date.now() + Math.max(30, body.expires_in ?? 300) * 1000
      }
      return cachedTicket
    } catch {
      return cachedTicket
    } finally {
      inflight = null
    }
  })()
  return inflight
}

function currentTicket(): string {
  // 同步读取已缓存票据；未就绪时触发一次异步预取（不阻塞本次渲染，下次渲染即可用）。
  if (!ticketFresh() && !inflight) {
    void prefetchFileTicket()
  }
  return cachedTicket
}

export function signedFileUrl(url?: string | null, tokenOverride?: string | null, noCache = false) {
  if (!url) return ''
  if (!needsFileTicket(url)) return noCache ? appendNoCache(url) : url
  const ticket = tokenOverride && tokenOverride !== SESSION_AUTH_MARKER ? tokenOverride : currentTicket()
  const separator = url.includes('?') ? '&' : '?'
  const withToken = ticket ? `${url}${separator}token=${encodeURIComponent(ticket)}` : url
  const withCachePolicy = noCache ? appendNoCache(withToken) : withToken
  return `${API_BASE}${withCachePolicy.startsWith('/') ? withCachePolicy : `/${withCachePolicy}`}`
}

function needsFileTicket(url: string) {
  return TICKETED_URL_PREFIXES.some((prefix) => url === prefix || url.startsWith(`${prefix}/`) || url.startsWith(`${prefix}?`))
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
  const ticket = currentTicket()
  const path = `/jobs/${jobId}/sprite-actions.zip`
  return `${API_BASE}${ticket ? `${path}?token=${encodeURIComponent(ticket)}` : path}`
}

export function spriteGifUrl(jobId: number): string {
  const ticket = currentTicket()
  const path = `/jobs/${jobId}/sprite.gif`
  return `${API_BASE}${ticket ? `${path}?token=${encodeURIComponent(ticket)}` : path}`
}
