import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, SESSION_AUTH_MARKER } from './api'

describe('Cookie session API requests', () => {
  beforeEach(() => {
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uses credentialed fetch without exposing a bearer token for the SPA session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 1, email: 'user@example.com', role: 'user' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.me(SESSION_AUTH_MARKER)

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(options.headers)
    expect(options.credentials).toBe('include')
    expect(headers.has('Authorization')).toBe(false)
  })

  it('keeps explicit bearer authentication compatible for non-browser clients', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 1, email: 'user@example.com', role: 'user' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.me('legacy-bearer-token')

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(options.headers)
    expect(options.credentials).toBe('include')
    expect(headers.get('Authorization')).toBe('Bearer legacy-bearer-token')
  })

  it('uses the session login endpoint and never returns a token contract to the SPA', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 1, email: 'user@example.com', role: 'user' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = await api.login('user@example.com', 'password')

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/auth/session/login')
    expect(options.credentials).toBe('include')
    expect(user).not.toHaveProperty('access_token')
  })
})
