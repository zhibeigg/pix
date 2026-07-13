import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'
import { I18nProvider, i18n } from '../i18n'
import type { CreditBalance, User } from '../types'
import { AccountMenu } from './AccountMenu'

const user: User = {
  id: 1,
  email: 'user@example.com',
  display_name: 'Pix User',
  role: 'user',
  status: 'active',
  created_at: '2026-07-14T00:00:00Z',
}

const balance: CreditBalance = {
  available_credits: 96,
  reserved_credits: 0,
  total_recharged: 128,
  total_consumed: 32,
  available_total: 128,
}

function renderAccountMenu(language: 'zh-CN' | 'en') {
  const menu = createElement(AccountMenu, {
    user,
    balance,
    activeJobs: 0,
    completedJobs: 3,
    failedJobs: 0,
    isAdmin: false,
    onNavigate: vi.fn(),
    onRefresh: vi.fn(),
    onLogout: vi.fn(),
  })
  return renderToStaticMarkup(createElement(I18nProvider, { language, children: menu }))
}

describe('AccountMenu', () => {
  test('renders the top-up shortcut beside the credit balance in both languages', async () => {
    await i18n.changeLanguage('zh-CN')
    const chinese = renderAccountMenu('zh-CN')
    expect(chinese).toContain('点数 128')
    expect(chinese).toContain('href="#/billing"')
    expect(chinese).toContain('aria-label="充值点数"')
    expect(chinese.indexOf('点数 128')).toBeLessThan(chinese.indexOf('充值'))

    await i18n.changeLanguage('en')
    const english = renderAccountMenu('en')
    expect(english).toContain('Credits 128')
    expect(english).toContain('aria-label="Top up credits"')

    await i18n.changeLanguage('zh-CN')
  })
})
