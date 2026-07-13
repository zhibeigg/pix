import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { I18nProvider } from '../../i18n'
import type { AdminDashboard, AdminDashboardSeriesPoint } from '../../types'
import { DEFAULT_DASHBOARD_QUERY } from './dashboardQuery'
import { buildTrendDatasets, calculateDashboardChange, DashboardOverview } from './DashboardOverview'

const point: AdminDashboardSeriesPoint = {
  start_at: '2026-07-01T00:00:00+08:00', end_at: '2026-07-02T00:00:00+08:00', jobs: 20, succeeded: 18, failed: 2,
  credits_consumed: 140, credits_recharged: 500, net_credits: 360, orders_created: 5, orders_paid: 3, orders_converted: 3,
  uploads: 7, new_users: 4, active_users: 12, paying_users: 3, success_rate: .9, payment_rate: .6, active_to_paying_rate: .25, has_data: true,
}

const dashboard: AdminDashboard = {
  total_users: 808, total_jobs: 1522, total_succeeded: 1413, total_failed: 104, total_credits_consumed: 13156, total_credits_recharged: 21327,
  total_orders_created: 116, total_orders_paid: 77, total_uploads: 1040, history_days: 14, history: [], new_users_today: 1, active_users_today: 5,
  paying_users_today: 1, jobs_today: 9, succeeded_today: 4, failed_today: 1, policy_blocked_today: 0, upstream_errors_today: 0, timeout_jobs_today: 0,
  pipeline_errors_today: 0, pending_jobs: 2, running_jobs: 5, running_over_30m_jobs: 1, candidate_failures_today: 0, pipeline_warnings_today: 1,
  average_generation_seconds_today: 318, p95_generation_seconds_today: 481, credits_consumed_today: 4, credits_recharged_today: 0, orders_created_today: 1,
  orders_paid_today: 0, uploads_today: 0, failure_rate: .1,
  window: { range: '14d', granularity: 'day', timezone: 'Asia/Shanghai', start_at: point.start_at, end_at: point.end_at, generated_at: point.end_at, data_cutoff_at: point.end_at, compare_enabled: true, comparison_start_at: '2026-06-17T00:00:00+08:00', comparison_end_at: point.start_at },
  current_period: point,
  previous_period: { ...point, jobs: 0, credits_consumed: 100, success_rate: .8, has_data: true },
  series: [point], previous_series: [{ ...point, start_at: '2026-06-17T00:00:00+08:00', end_at: '2026-06-18T00:00:00+08:00' }],
}

describe('DashboardOverview', () => {
  it('calculates relative, percentage-point, new, and unavailable changes', () => {
    expect(calculateDashboardChange(15, 10, 'number', true)).toEqual({ kind: 'percent', value: 50 })
    expect(calculateDashboardChange(.9, .8, 'rate', true).kind).toBe('points')
    expect(calculateDashboardChange(2, 0, 'number', true).kind).toBe('new')
    expect(calculateDashboardChange(2, undefined, 'number', false).kind).toBe('none')
  })

  it('maps each topic to two current and two dashed previous datasets', () => {
    const datasets = buildTrendDatasets('quality', [point], [point], true, (metric) => metric, 'previous')
    expect(datasets).toHaveLength(4)
    expect(datasets.filter((item) => item.dashboardPrevious)).toHaveLength(2)
    expect(datasets.filter((item) => item.borderDash?.length)).toHaveLength(2)
    expect(datasets.find((item) => item.dashboardMetric === 'success_rate')?.yAxisID).toBe('yRate')
  })

  it('renders six KPIs, controls, diagnostics, ledger, and bucket details in Chinese', () => {
    const html = renderToStaticMarkup(createElement(I18nProvider, { language: 'zh-CN', children: createElement(DashboardOverview, { dashboard, query: DEFAULT_DASHBOARD_QUERY, refreshing: false, error: '', onQueryChange: () => undefined, onRetry: () => undefined }) }))
    expect(html).toContain('周期核心指标')
    expect(html).toContain('成功率')
    expect(html).toContain('新增')
    expect(html).toContain('周期诊断')
    expect(html).toContain('实时运行状态')
    expect(html).toContain('累计数据账本')
    expect(html).toContain('逐桶明细')
    expect(html).toContain('Asia/Shanghai')
  })

  it('keeps live status and the lifetime ledger visible for an empty selected period', () => {
    const emptyDashboard: AdminDashboard = { ...dashboard, current_period: { ...dashboard.current_period!, jobs: 0, has_data: false }, series: [{ ...point, jobs: 0, has_data: false }] }
    const html = renderToStaticMarkup(createElement(I18nProvider, { language: 'zh-CN', children: createElement(DashboardOverview, { dashboard: emptyDashboard, query: DEFAULT_DASHBOARD_QUERY, refreshing: false, error: '', onQueryChange: () => undefined, onRetry: () => undefined }) }))
    expect(html).toContain('这个周期还没有运营数据')
    expect(html).toContain('实时运行状态')
    expect(html).toContain('累计数据账本')
    expect(html).not.toContain('逐桶明细')
  })
})
