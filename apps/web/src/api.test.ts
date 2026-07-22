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

  it('creates an admin-managed standard user with the exact request contract', async () => {
    const createdUser = { id: 42, email: 'new-user@example.com', display_name: 'New User', role: 'user', status: 'active', created_at: '2026-07-22T00:00:00Z' }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(createdUser), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.createAdminUser(SESSION_AUTH_MARKER, {
      email: 'new-user@example.com',
      display_name: 'New User',
      password: 'Temporary9',
    })

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(options.headers)
    expect(url).toContain('/admin/users')
    expect(url).not.toContain('/admin/users?')
    expect(options.method).toBe('POST')
    expect(options.credentials).toBe('include')
    expect(headers.has('Authorization')).toBe(false)
    expect(JSON.parse(String(options.body))).toEqual({ email: 'new-user@example.com', display_name: 'New User', password: 'Temporary9' })
    expect(result).toEqual(createdUser)
  })

  it('sends the exact signed update apply contract', async () => {
    const operation = { id: 'op-1', kind: 'apply', status: 'queued', target_version: '1.2.3', started_at: null, updated_at: null, finished_at: null, error: null, steps: [] }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(operation), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await api.applyAdminUpdate(SESSION_AUTH_MARKER, { target_version: '1.2.3', expected_manifest_sha256: 'abc123', idempotency_key: 'update-1' })

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/admin/updates/apply')
    expect(options.method).toBe('POST')
    expect(JSON.parse(String(options.body))).toEqual({ target_version: '1.2.3', expected_manifest_sha256: 'abc123', idempotency_key: 'update-1' })
  })

  it('serializes dashboard data query fields without a presentation topic', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await api.adminDashboard(SESSION_AUTH_MARKER, { range: 'custom', granularity: 'day', compare: false, from: '2026-06-01', to: '2026-06-20' })

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/admin/dashboard?range=custom&granularity=day&compare=false&from=2026-06-01&to=2026-06-20')
    expect(url).not.toContain('topic')
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
