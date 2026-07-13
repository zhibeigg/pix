import type { AdminDashboardGranularity, AdminDashboardQueryParams, AdminDashboardRange, AdminDashboardTopic } from '../../types'

export type DashboardQueryState = AdminDashboardQueryParams & {
  topic: AdminDashboardTopic
}

export const DEFAULT_DASHBOARD_QUERY: DashboardQueryState = {
  range: '14d',
  granularity: 'auto',
  compare: true,
  topic: 'quality',
}

const DASHBOARD_KEYS = ['range', 'granularity', 'compare', 'from', 'to', 'topic'] as const
const RANGES = new Set<AdminDashboardRange>(['24h', '7d', '14d', '30d', '90d', 'custom'])
const GRANULARITIES = new Set<AdminDashboardGranularity>(['auto', 'hour', 'day', 'week'])
const TOPICS = new Set<AdminDashboardTopic>(['quality', 'credits', 'orders', 'users'])
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

export function parseDashboardQuery(params: URLSearchParams): DashboardQueryState {
  const rawRange = params.get('range')
  const rawGranularity = params.get('granularity')
  const rawTopic = params.get('topic')
  const rawCompare = params.get('compare')
  const range = rawRange && RANGES.has(rawRange as AdminDashboardRange) ? rawRange as AdminDashboardRange : DEFAULT_DASHBOARD_QUERY.range
  const granularity = rawGranularity && GRANULARITIES.has(rawGranularity as AdminDashboardGranularity) ? rawGranularity as AdminDashboardGranularity : DEFAULT_DASHBOARD_QUERY.granularity
  const topic = rawTopic && TOPICS.has(rawTopic as AdminDashboardTopic) ? rawTopic as AdminDashboardTopic : DEFAULT_DASHBOARD_QUERY.topic
  const compare = rawCompare === 'false' ? false : rawCompare === 'true' || rawCompare === null ? true : DEFAULT_DASHBOARD_QUERY.compare
  const from = validDate(params.get('from'))
  const to = validDate(params.get('to'))
  const customDays = range === 'custom' ? customRangeDays(from, to) : null
  if (range === 'custom' && (!from || !to || customDays === null || customDays > 365)) {
    return { ...DEFAULT_DASHBOARD_QUERY, compare, topic }
  }
  return {
    range,
    granularity,
    compare,
    topic,
    ...(range === 'custom' && from ? { from } : {}),
    ...(range === 'custom' && to ? { to } : {}),
  }
}

export function writeDashboardQuery(current: URLSearchParams, query: DashboardQueryState): URLSearchParams {
  const next = new URLSearchParams(current)
  DASHBOARD_KEYS.forEach((key) => next.delete(key))
  if (query.range !== DEFAULT_DASHBOARD_QUERY.range) next.set('range', query.range)
  if (query.granularity !== DEFAULT_DASHBOARD_QUERY.granularity) next.set('granularity', query.granularity)
  if (query.compare !== DEFAULT_DASHBOARD_QUERY.compare) next.set('compare', String(query.compare))
  if (query.range === 'custom' && validDate(query.from)) next.set('from', query.from as string)
  if (query.range === 'custom' && validDate(query.to)) next.set('to', query.to as string)
  if (query.topic !== DEFAULT_DASHBOARD_QUERY.topic) next.set('topic', query.topic)
  return next
}

export function dashboardRequestParams(query: DashboardQueryState): AdminDashboardQueryParams {
  return {
    range: query.range,
    granularity: query.granularity,
    compare: query.compare,
    ...(query.range === 'custom' && query.from ? { from: query.from } : {}),
    ...(query.range === 'custom' && query.to ? { to: query.to } : {}),
  }
}

export function dashboardRequestKey(query: DashboardQueryState): string {
  const params = dashboardRequestParams(query)
  return [params.range, params.granularity, params.compare ? 'compare' : 'current', params.from ?? '', params.to ?? ''].join('|')
}

export function customRangeDays(from?: string, to?: string): number | null {
  if (!validDate(from) || !validDate(to)) return null
  const start = Date.parse(`${from}T00:00:00Z`)
  const end = Date.parse(`${to}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null
  return Math.floor((end - start) / 86400000) + 1
}

export function validateCustomRange(from: string, to: string, siteToday: string): 'incomplete' | 'reversed' | 'future' | 'tooLong' | null {
  if (!validDate(from) || !validDate(to)) return 'incomplete'
  const days = customRangeDays(from, to)
  if (days === null) return 'reversed'
  if (to > siteToday) return 'future'
  if (days > 365) return 'tooLong'
  return null
}

export function isGranularityAvailable(granularity: AdminDashboardGranularity, query: Pick<DashboardQueryState, 'range' | 'from' | 'to'>): boolean {
  if (granularity === 'auto') return true
  if (granularity !== 'hour') return true
  if (query.range === '24h' || query.range === '7d') return true
  if (query.range !== 'custom') return false
  const days = customRangeDays(query.from, query.to)
  return days !== null && days <= 7
}

export function expandDashboardRange(query: DashboardQueryState, siteToday?: string): DashboardQueryState | null {
  const nextRange: Partial<Record<AdminDashboardRange, AdminDashboardRange>> = {
    '24h': '7d',
    '7d': '14d',
    '14d': '30d',
    '30d': '90d',
  }
  if (query.range === '90d' && validDate(siteToday)) {
    return { ...query, range: 'custom', granularity: 'auto', from: shiftDate(siteToday as string, -364), to: siteToday }
  }
  let range = nextRange[query.range]
  if (query.range === 'custom') {
    const days = customRangeDays(query.from, query.to) ?? 0
    range = days < 7 ? '7d' : days < 14 ? '14d' : days < 30 ? '30d' : days < 90 ? '90d' : undefined
  }
  if (!range) return null
  return { ...query, range, granularity: query.granularity === 'hour' && range !== '7d' ? 'auto' : query.granularity, from: undefined, to: undefined }
}

function validDate(value: string | null | undefined): string | undefined {
  if (!value || !DATE_PATTERN.test(value)) return undefined
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value ? undefined : value
}

function shiftDate(value: string, days: number): string {
  const parsed = new Date(`${value}T00:00:00Z`)
  parsed.setUTCDate(parsed.getUTCDate() + days)
  return parsed.toISOString().slice(0, 10)
}
