import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AdminPanel } from '../../components/AdminPanel'

describe('AdminPanel compatibility export', () => {
  it('renders the compact admin console shell', () => {
    const html = renderToStaticMarkup(createElement(AdminPanel, { token: 'cookie-session' }))
    expect(html).toContain('data-admin-density="compact"')
    expect(html).toContain('admin.tabs.overview')
  })
})
