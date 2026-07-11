import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SESSION_AUTH_MARKER } from './api'
import { clearFileTicket, prefetchFileTicket, signedFileUrl } from './fileUrls'

describe('Cookie-session file tickets', () => {
  beforeEach(() => {
    clearFileTicket()
  })

  afterEach(() => {
    clearFileTicket()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uses the cached short-lived ticket instead of the non-secret session marker', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ticket: 'real-file-ticket', expires_in: 300 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await prefetchFileTicket(SESSION_AUTH_MARKER)
    const url = signedFileUrl('/files?path=preview.png', SESSION_AUTH_MARKER)

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(options.headers)
    expect(options.credentials).toBe('include')
    expect(headers.has('Authorization')).toBe(false)
    expect(url).toContain('token=real-file-ticket')
    expect(url).not.toContain(SESSION_AUTH_MARKER)
  })

  it('still accepts an explicit file ticket override', () => {
    const url = signedFileUrl('/files?path=preview.png', 'explicit-file-ticket')

    expect(url).toContain('token=explicit-file-ticket')
  })
})
