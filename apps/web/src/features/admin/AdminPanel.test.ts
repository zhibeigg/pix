import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AdminPanel } from '../../components/AdminPanel'
import { refreshAdminOverview } from './AdminConsole'

describe('AdminPanel compatibility export', () => {
  it('renders the compact admin console shell', () => {
    const html = renderToStaticMarkup(createElement(AdminPanel, { token: 'cookie-session' }))
    expect(html).toContain('data-admin-density="compact"')
    expect(html).toContain('admin.tabs.overview')
  })

  it('refreshes dashboard metrics and update summary together', async () => {
    const calls: string[] = []

    await refreshAdminOverview(
      async () => { calls.push('dashboard') },
      async () => { calls.push('updates') },
    )

    expect(calls).toEqual(['dashboard', 'updates'])
  })
})
