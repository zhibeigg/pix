import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AdminPanel } from '../../components/AdminPanel'
import { i18n, I18nProvider } from '../../i18n'
import type { AdminDashboard } from '../../types'
import { refreshAdminOverview } from './AdminConsole'
import { AdminUserCreateForm } from './LegacyPanels'
import { DashboardOverview } from './DashboardOverview'
import { DEFAULT_DASHBOARD_QUERY } from './dashboardQuery'

const dashboardFixture: AdminDashboard = {
  total_users: 808,
  total_jobs: 1522,
  total_succeeded: 1413,
  total_failed: 104,
  total_credits_consumed: 13156,
  total_credits_recharged: 21327,
  total_orders_created: 116,
  total_orders_paid: 77,
  total_uploads: 1040,
  history_days: 14,
  history: [{ date: '2026-07-13', jobs: 82, succeeded: 82, failed: 0, credits_consumed: 169, credits_recharged: 500, orders_created: 3, orders_paid: 2, uploads: 4, new_users: 6 }],
  new_users_today: 1,
  active_users_today: 5,
  paying_users_today: 0,
  jobs_today: 9,
  succeeded_today: 4,
  failed_today: 0,
  policy_blocked_today: 0,
  upstream_errors_today: 0,
  timeout_jobs_today: 0,
  pipeline_errors_today: 0,
  pending_jobs: 0,
  running_jobs: 5,
  running_over_30m_jobs: 0,
  candidate_failures_today: 0,
  pipeline_warnings_today: 0,
  average_generation_seconds_today: 318.694,
  p95_generation_seconds_today: 481.089,
  credits_consumed_today: 4,
  credits_recharged_today: 0,
  orders_created_today: 1,
  orders_paid_today: 0,
  uploads_today: 0,
  failure_rate: 0,
}

describe('AdminPanel compatibility export', () => {
  it('renders the compact admin console shell', () => {
    const html = renderToStaticMarkup(createElement(AdminPanel, { token: 'cookie-session' }))
    expect(html).toContain('data-admin-density="compact"')
    expect(html).toContain('admin.tabs.overview')
  })

  it('renders historical totals and daily overview data', () => {
    const html = renderToStaticMarkup(
      createElement(I18nProvider, {
        language: 'zh-CN',
        children: createElement(DashboardOverview, { dashboard: dashboardFixture, query: DEFAULT_DASHBOARD_QUERY, refreshing: false, error: '', onQueryChange: () => undefined, onRetry: () => undefined }),
      }),
    )

    expect(html).toContain('周期核心指标')
    expect(html).toContain('累计数据账本')
    expect(html).toContain('逐桶明细')
    expect(html).toContain('1,522')
    expect(html).toContain('21,327')
  })

  it('renders the Chinese admin user creation fields and safety rules', async () => {
    await i18n.changeLanguage('zh-CN')
    const html = renderToStaticMarkup(
      createElement(I18nProvider, {
        language: 'zh-CN',
        children: createElement(AdminUserCreateForm, { onCreate: async () => undefined }),
      }),
    )

    expect(html).toContain('创建普通用户')
    expect(html).toContain('临时密码')
    expect(html).toContain('type="password"')
    expect(html).toContain('账户创建后立即激活')
    expect(html).toContain('无需发送或填写邮箱验证码')
    expect(html).toContain('只能创建普通用户')
    expect(html).toContain('当前注册赠送规则')
  })

  it('renders the English admin user creation fields and safety rules', async () => {
    await i18n.changeLanguage('en')
    const html = renderToStaticMarkup(
      createElement(I18nProvider, {
        language: 'en',
        children: createElement(AdminUserCreateForm, { onCreate: async () => undefined }),
      }),
    )

    expect(html).toContain('Create standard user')
    expect(html).toContain('Temporary password')
    expect(html).toContain('type="password"')
    expect(html).toContain('activated immediately')
    expect(html).toContain('No email verification code is required')
    expect(html).toContain('Only a standard user can be created')
    expect(html).toContain('current registration bonus rules')
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
