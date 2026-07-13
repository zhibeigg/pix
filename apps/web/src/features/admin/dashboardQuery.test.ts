import { describe, expect, it } from 'vitest'
import {
  DEFAULT_DASHBOARD_QUERY,
  dashboardRequestKey,
  dashboardRequestParams,
  expandDashboardRange,
  isGranularityAvailable,
  parseDashboardQuery,
  validateCustomRange,
  writeDashboardQuery,
} from './dashboardQuery'

describe('dashboard query state', () => {
  it('uses compact defaults and restores valid deep links', () => {
    expect(parseDashboardQuery(new URLSearchParams())).toEqual(DEFAULT_DASHBOARD_QUERY)
    expect(parseDashboardQuery(new URLSearchParams('range=custom&granularity=day&compare=false&from=2026-06-01&to=2026-06-20&topic=orders'))).toEqual({ range: 'custom', granularity: 'day', compare: false, from: '2026-06-01', to: '2026-06-20', topic: 'orders' })
  })

  it('falls back from illegal values and serializes non-default values in stable order', () => {
    expect(parseDashboardQuery(new URLSearchParams('range=forever&granularity=minute&compare=maybe&topic=rainbow'))).toEqual(DEFAULT_DASHBOARD_QUERY)
    expect(parseDashboardQuery(new URLSearchParams('range=custom&compare=false&topic=orders'))).toEqual({ ...DEFAULT_DASHBOARD_QUERY, compare: false, topic: 'orders' })
    const params = writeDashboardQuery(new URLSearchParams('tab=overview&unrelated=kept'), { range: 'custom', granularity: 'week', compare: false, from: '2026-01-01', to: '2026-04-01', topic: 'users' })
    expect(params.toString()).toBe('tab=overview&unrelated=kept&range=custom&granularity=week&compare=false&from=2026-01-01&to=2026-04-01&topic=users')
    expect(writeDashboardQuery(new URLSearchParams('tab=overview&range=30d&topic=orders'), DEFAULT_DASHBOARD_QUERY).toString()).toBe('tab=overview')
  })

  it('keeps topic out of the request key and API params', () => {
    const quality = { ...DEFAULT_DASHBOARD_QUERY, range: '30d' as const }
    const users = { ...quality, topic: 'users' as const }
    expect(dashboardRequestKey(quality)).toBe(dashboardRequestKey(users))
    expect(dashboardRequestParams(users)).toEqual({ range: '30d', granularity: 'auto', compare: true })
  })

  it('validates custom dates, granularity limits, and empty-range expansion', () => {
    expect(validateCustomRange('2026-01-10', '2026-01-01', '2026-06-01')).toBe('reversed')
    expect(validateCustomRange('2025-01-01', '2026-01-02', '2026-06-01')).toBe('tooLong')
    expect(validateCustomRange('2026-01-01', '2026-06-02', '2026-06-01')).toBe('future')
    expect(validateCustomRange('2026-01-01', '2026-01-07', '2026-06-01')).toBeNull()
    expect(isGranularityAvailable('hour', { range: '30d' })).toBe(false)
    expect(isGranularityAvailable('hour', { range: 'custom', from: '2026-01-01', to: '2026-01-07' })).toBe(true)
    expect(expandDashboardRange({ ...DEFAULT_DASHBOARD_QUERY, range: '14d' })?.range).toBe('30d')
    expect(expandDashboardRange({ ...DEFAULT_DASHBOARD_QUERY, range: '90d' }, '2026-06-17')).toMatchObject({ range: 'custom', from: '2025-06-18', to: '2026-06-17', granularity: 'auto' })
  })
})
