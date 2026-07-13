import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartDataset,
  type ChartOptions,
  type Plugin,
} from 'chart.js'
import { Chart } from 'react-chartjs-2'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { useI18n } from '../../i18n'
import type {
  AdminDashboard,
  AdminDashboardGranularity,
  AdminDashboardPeriodSummary,
  AdminDashboardSeriesPoint,
  AdminDashboardTopic,
} from '../../types'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Switch } from '../../components/ui/switch'
import {
  expandDashboardRange,
  isGranularityAvailable,
  validateCustomRange,
  type DashboardQueryState,
} from './dashboardQuery'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, LineController, BarController, Tooltip, Legend)

type DashboardOverviewProps = {
  dashboard: AdminDashboard
  query: DashboardQueryState
  refreshing: boolean
  error: string
  onQueryChange: (next: DashboardQueryState) => void
  onRetry: () => void
}

type TrendMetric = 'jobs' | 'success_rate' | 'credits_recharged' | 'credits_consumed' | 'orders_created' | 'orders_paid' | 'active_users' | 'new_users'
type DashboardDataset = ChartDataset<'line', number[]> & { dashboardMetric: TrendMetric; dashboardPrevious: boolean }

type ChangeResult = { kind: 'none' | 'new' | 'percent' | 'points'; value: number }

export const DASHBOARD_TOPIC_METRICS: Record<AdminDashboardTopic, TrendMetric[]> = {
  quality: ['jobs', 'success_rate'],
  credits: ['credits_recharged', 'credits_consumed'],
  orders: ['orders_created', 'orders_paid'],
  users: ['active_users', 'new_users'],
}

const RANGE_VALUES = ['24h', '7d', '14d', '30d', '90d'] as const
const GRANULARITIES: AdminDashboardGranularity[] = ['auto', 'hour', 'day', 'week']
const TOPICS: AdminDashboardTopic[] = ['quality', 'credits', 'orders', 'users']
const SERIES_COLORS = ['--dashboard-series-1', '--dashboard-series-2'] as const

const crosshairPlugin: Plugin<'line'> = {
  id: 'dashboard-crosshair',
  afterDatasetsDraw(chart) {
    const active = chart.getActiveElements()
    const selected = (chart as ChartJS<'line'> & { dashboardSelectedIndex?: number }).dashboardSelectedIndex
    const index = active[0]?.index ?? selected
    if (index === undefined || index < 0) return
    const x = chart.scales.x.getPixelForValue(index)
    const { top, bottom } = chart.chartArea
    const context = chart.ctx
    context.save()
    context.beginPath()
    context.moveTo(x, top)
    context.lineTo(x, bottom)
    context.lineWidth = 1
    context.setLineDash([3, 4])
    context.strokeStyle = cssColor('--dashboard-crosshair', 'rgba(99,102,241,.55)')
    context.stroke()
    context.restore()
  },
}

export function DashboardOverview({ dashboard, query, refreshing, error, onQueryChange, onRetry }: DashboardOverviewProps) {
  const { language, t } = useI18n()
  const locale = language === 'en' ? 'en-US' : 'zh-CN'
  const normalized = useMemo(() => normalizeDashboard(dashboard), [dashboard])
  const chartRef = useRef<ChartJS<'line'> | null>(null)
  const [hiddenDatasets, setHiddenDatasets] = useState<Set<string>>(() => new Set())
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [customOpen, setCustomOpen] = useState(query.range === 'custom')
  const siteToday = useMemo(() => normalized.window.generated_at.slice(0, 10), [normalized.window.generated_at])
  const [customFrom, setCustomFrom] = useState(query.from ?? shiftDate(siteToday, -13))
  const [customTo, setCustomTo] = useState(query.to ?? siteToday)
  const reducedMotion = useReducedMotion()
  const themeRevision = useThemeRevision()
  const number = useMemo(() => new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }), [locale])
  const timeZone = useMemo(() => safeTimeZone(normalized.window.timezone), [normalized.window.timezone])
  const dateTime = useMemo(() => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: normalized.window.granularity === 'hour' ? 'short' : undefined, ...(timeZone ? { timeZone } : {}) }), [locale, normalized.window.granularity, timeZone])
  const updatedAt = useMemo(() => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', ...(timeZone ? { timeZone } : {}) }), [locale, timeZone])
  const shortDate = useMemo(() => new Intl.DateTimeFormat(locale, { ...(normalized.window.granularity === 'hour' ? { month: 'short' as const, day: 'numeric' as const, hour: '2-digit' as const } : { month: 'short' as const, day: 'numeric' as const }), ...(timeZone ? { timeZone } : {}) }), [locale, normalized.window.granularity, timeZone])
  const customError = validateCustomRange(customFrom, customTo, siteToday)

  useEffect(() => {
    if (query.range !== 'custom') return
    setCustomFrom(query.from ?? shiftDate(siteToday, -13))
    setCustomTo(query.to ?? siteToday)
  }, [query.from, query.range, query.to, siteToday])

  const datasets = useMemo(
    () => buildTrendDatasets(query.topic, normalized.series, normalized.previousSeries, normalized.previous?.has_data === true, (metric) => t(`admin.overview.series.${metric}`), t('admin.overview.comparison.previous'), themeRevision),
    [normalized.previous?.has_data, normalized.previousSeries, normalized.series, query.topic, t, themeRevision],
  )
  const chartData = useMemo(() => ({ labels: normalized.series.map((point) => shortDate.format(new Date(point.start_at))), datasets }), [datasets, normalized.series, shortDate])
  const chartOptions = useMemo<ChartOptions<'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    normalized: true,
    animation: reducedMotion ? false : { duration: 180 },
    interaction: { mode: 'index', intersect: false },
    onClick: (_event, elements) => {
      const index = elements[0]?.index
      if (index !== undefined) selectBucket(index, true)
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        enabled: true,
        displayColors: true,
        callbacks: {
          title: (items) => {
            const index = items[0]?.dataIndex ?? 0
            return `${t('admin.overview.chart.currentTime')}: ${formatExactRange(normalized.series[index], dateTime)}`
          },
          afterTitle: (items) => {
            const index = items[0]?.dataIndex ?? 0
            const point = normalized.previousSeries[index]
            return normalized.previous?.has_data && point ? `${t('admin.overview.chart.previousTime')}: ${formatExactRange(point, dateTime)}` : ''
          },
          label: (context) => {
            const dataset = context.dataset as DashboardDataset
            const period = dataset.dashboardPrevious ? t('admin.overview.comparison.previous') : t('admin.overview.comparison.current')
            const rawValue = context.parsed.y ?? 0
            const value = dataset.dashboardMetric === 'success_rate' ? `${Number(rawValue).toFixed(2)}%` : number.format(rawValue)
            return `${period} · ${dataset.label}: ${value}`
          },
        },
      },
    },
    scales: {
      x: { grid: { color: cssColor('--dashboard-grid', 'rgba(100,116,139,.12)') }, ticks: { color: cssColor('--dashboard-axis', '#64748b'), maxRotation: 0, autoSkip: true, maxTicksLimit: 9 } },
      y: { beginAtZero: true, grid: { color: cssColor('--dashboard-grid', 'rgba(100,116,139,.12)') }, ticks: { color: cssColor('--dashboard-axis', '#64748b'), precision: 0 } },
      yRate: { display: query.topic === 'quality', position: 'right', beginAtZero: true, min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { color: cssColor('--dashboard-axis', '#64748b'), callback: (value) => `${value}%` } },
    },
  }), [dateTime, normalized.previousSeries, normalized.series, number, query.topic, reducedMotion, t, themeRevision])

  useEffect(() => {
    if (selectedIndex === null || selectedIndex >= normalized.series.length) return
    syncChartSelection(chartRef.current, selectedIndex)
  }, [datasets, normalized.series.length, selectedIndex])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    datasets.forEach((dataset, index) => chart.setDatasetVisibility(index, !hiddenDatasets.has(datasetId(dataset))))
    chart.update('none')
  }, [datasets, hiddenDatasets])

  const metrics = [
    { key: 'jobs', current: normalized.current.jobs, previous: normalized.previous?.jobs, kind: 'number' as const },
    { key: 'successRate', current: normalized.current.success_rate, previous: normalized.previous?.success_rate, kind: 'rate' as const },
    { key: 'creditsConsumed', current: normalized.current.credits_consumed, previous: normalized.previous?.credits_consumed, kind: 'number' as const },
    { key: 'creditsRecharged', current: normalized.current.credits_recharged, previous: normalized.previous?.credits_recharged, kind: 'number' as const },
    { key: 'paidOrders', current: normalized.current.orders_paid, previous: normalized.previous?.orders_paid, kind: 'number' as const },
    { key: 'activeUsers', current: normalized.current.active_users, previous: normalized.previous?.active_users, kind: 'number' as const },
  ]
  const expanded = expandDashboardRange(query, siteToday)

  function selectBucket(index: number, openDetails: boolean) {
    setSelectedIndex(index)
    if (openDetails) setDetailsOpen(true)
    syncChartSelection(chartRef.current, index)
    if (openDetails) window.setTimeout(() => document.querySelector(`[data-dashboard-bucket="${index}"]`)?.scrollIntoView({ block: 'nearest', behavior: reducedMotion ? 'auto' : 'smooth' }), 0)
  }

  function updateQuery(patch: Partial<DashboardQueryState>) {
    const next = { ...query, ...patch }
    if (!isGranularityAvailable(next.granularity, next)) next.granularity = 'auto'
    onQueryChange(next)
  }

  function chooseRange(range: typeof RANGE_VALUES[number]) {
    setCustomOpen(false)
    updateQuery({ range, from: undefined, to: undefined })
  }

  function applyCustomRange() {
    if (customError) return
    onQueryChange({ ...query, range: 'custom', from: customFrom, to: customTo, granularity: query.granularity === 'hour' && !isGranularityAvailable('hour', { range: 'custom', from: customFrom, to: customTo }) ? 'auto' : query.granularity })
    setCustomOpen(false)
  }

  return (
    <div className={`dashboard-overview ${refreshing ? 'is-refreshing' : ''}`} aria-busy={refreshing}>
      <section className="dashboard-control-band" aria-label={t('admin.overview.controls.label')}>
        <div className="dashboard-range-group" role="group" aria-label={t('admin.overview.controls.range')}>
          {RANGE_VALUES.map((range) => <button key={range} type="button" aria-pressed={query.range === range} className="dashboard-segment" onClick={() => chooseRange(range)}>{t(`admin.overview.ranges.${range}`)}</button>)}
          <button type="button" aria-expanded={customOpen} aria-pressed={query.range === 'custom'} className="dashboard-segment" onClick={() => setCustomOpen((value) => !value)}>{t('admin.overview.ranges.custom')}</button>
        </div>
        <label className="dashboard-control-field">
          <span>{t('admin.overview.controls.granularity')}</span>
          <Select value={query.granularity} onValueChange={(value) => updateQuery({ granularity: value as AdminDashboardGranularity })}>
            <SelectTrigger className="h-8 min-h-8 w-[132px]"><SelectValue /></SelectTrigger>
            <SelectContent>{GRANULARITIES.map((value) => <SelectItem key={value} value={value} disabled={!isGranularityAvailable(value, query)}>{t(`admin.overview.granularity.${value}`)}</SelectItem>)}</SelectContent>
          </Select>
        </label>
        <label className="dashboard-compare-switch"><Switch checked={query.compare} onCheckedChange={(checked) => updateQuery({ compare: checked })} /><span>{t('admin.overview.controls.compare')}</span></label>
        <div className="dashboard-control-meta">
          <span>{t('admin.overview.controls.timezone')}: <b>{normalized.window.timezone}</b></span>
          <span>{t('admin.overview.controls.updatedAt', { time: updatedAt.format(new Date(normalized.window.generated_at)) })}</span>
          {refreshing && <span className="dashboard-refreshing"><RefreshCw />{t('admin.overview.states.refreshing')}</span>}
        </div>
      </section>

      {customOpen && <section className="dashboard-custom-range" aria-label={t('admin.overview.custom.title')}>
        <label><span>{t('admin.overview.custom.from')}</span><Input type="date" value={customFrom} max={siteToday} onChange={(event) => setCustomFrom(event.target.value)} /></label>
        <label><span>{t('admin.overview.custom.to')}</span><Input type="date" value={customTo} max={siteToday} onChange={(event) => setCustomTo(event.target.value)} /></label>
        <div className="dashboard-custom-actions"><Button type="button" size="sm" disabled={Boolean(customError)} onClick={applyCustomRange}>{t('admin.overview.custom.apply')}</Button><Button type="button" size="sm" variant="outline" onClick={() => setCustomOpen(false)}>{t('admin.overview.custom.cancel')}</Button></div>
        <p className={customError ? 'text-destructive' : 'text-muted-foreground'}>{customError ? t(`admin.overview.custom.errors.${customError}`) : t('admin.overview.custom.hint', { date: siteToday })}</p>
      </section>}

      {error && <Alert variant="destructive"><div className="flex flex-wrap items-center justify-between gap-2"><span>{t('admin.overview.states.staleError', { error })}</span><Button type="button" size="sm" variant="outline" onClick={onRetry}>{t('admin.overview.states.retry')}</Button></div></Alert>}

      <section className="dashboard-kpi-band" aria-label={t('admin.overview.kpis.label')}>
        {metrics.map((metric) => {
          const change = calculateDashboardChange(metric.current, metric.previous, metric.kind, normalized.previous?.has_data === true)
          return <div className="dashboard-kpi" key={metric.key}><span>{t(`admin.overview.kpis.${metric.key}`)}</span><strong>{metric.kind === 'rate' ? `${(metric.current * 100).toFixed(1)}%` : number.format(metric.current)}</strong><small>{t('admin.overview.comparison.previous')}: {metric.previous === undefined || normalized.previous?.has_data !== true ? '—' : metric.kind === 'rate' ? `${(metric.previous * 100).toFixed(1)}%` : number.format(metric.previous)}</small><ChangeBadge change={change} /></div>
        })}
      </section>

      {!normalized.current.has_data ? <section className="dashboard-empty"><h2>{t('admin.overview.states.emptyTitle')}</h2><p>{t('admin.overview.states.emptyDescription')}</p>{expanded && <Button type="button" variant="outline" onClick={() => onQueryChange(expanded)}>{t('admin.overview.states.expandRange', { range: t(`admin.overview.ranges.${expanded.range}`) })}</Button>}</section> : <section className="dashboard-workspace">
        <div className="dashboard-trend-panel">
          <div className="dashboard-section-heading"><div><h2>{t('admin.overview.chart.title')}</h2><p>{t('admin.overview.chart.description')}</p></div><div className="dashboard-topic-tabs" role="tablist" aria-label={t('admin.overview.chart.topicsLabel')}>{TOPICS.map((topic) => <button key={topic} type="button" role="tab" aria-selected={query.topic === topic} onClick={() => updateQuery({ topic })}>{t(`admin.overview.topics.${topic}`)}</button>)}</div></div>
          <div className="dashboard-chart-legend" aria-label={t('admin.overview.chart.legendLabel')}>{datasets.map((dataset) => { const id = datasetId(dataset); const visible = !hiddenDatasets.has(id); return <button key={id} type="button" aria-pressed={visible} onClick={() => { const next = new Set(hiddenDatasets); if (visible) next.add(id); else next.delete(id); setHiddenDatasets(next) }}><span style={{ borderTopColor: String(dataset.borderColor), borderTopStyle: dataset.borderDash?.length ? 'dashed' : 'solid' }} />{dataset.label}</button> })}</div>
          <div className="dashboard-chart-wrap">
            <Chart ref={chartRef} type="line" data={chartData} options={chartOptions} plugins={[crosshairPlugin]} updateMode="none" role="img" aria-label={t('admin.overview.chart.ariaLabel', { topic: t(`admin.overview.topics.${query.topic}`), range: t(`admin.overview.ranges.${query.range}`) })} />
            {refreshing && <div className="dashboard-loading-overlay"><RefreshCw />{t('admin.overview.states.refreshing')}</div>}
          </div>
        </div>
        <Diagnostics dashboard={dashboard} current={normalized.current} number={number} />
      </section>}

      <RealtimeStatus dashboard={dashboard} number={number} />
      <Ledger dashboard={dashboard} number={number} />

      {normalized.current.has_data && <section className="dashboard-details">
        <button type="button" className="dashboard-details-toggle" aria-expanded={detailsOpen} onClick={() => setDetailsOpen((value) => !value)}><span><b>{t('admin.overview.details.title')}</b><small>{t('admin.overview.details.description')}</small></span><ChevronDown className={detailsOpen ? 'rotate-180' : ''} /></button>
        {detailsOpen && <div className="dashboard-details-content">
          <div className="dashboard-details-table" role="table" aria-label={t('admin.overview.details.title')}>
            <div className="dashboard-details-head" role="row"><span>{t('admin.overview.details.columns.time')}</span><span>{t('admin.overview.details.columns.jobs')}</span><span>{t('admin.overview.details.columns.credits')}</span><span>{t('admin.overview.details.columns.orders')}</span><span>{t('admin.overview.details.columns.users')}</span></div>
            {normalized.series.map((point, index) => <BucketRow key={point.start_at} point={point} index={index} selected={selectedIndex === index} dateTime={dateTime} number={number} onSelect={() => selectBucket(index, false)} />)}
          </div>
          <div className="dashboard-details-mobile">{normalized.series.map((point, index) => <BucketMobile key={point.start_at} point={point} index={index} selected={selectedIndex === index} dateTime={dateTime} number={number} onSelect={() => selectBucket(index, false)} />)}</div>
        </div>}
      </section>}
    </div>
  )

  function ChangeBadge({ change }: { change: ChangeResult }) {
    if (change.kind === 'none') return <em className="is-neutral">{t('admin.overview.comparison.unavailable')}</em>
    if (change.kind === 'new') return <em className="is-positive">{t('admin.overview.comparison.new')}</em>
    const positive = change.value > 0
    const label = change.kind === 'points' ? t('admin.overview.comparison.points', { value: `${positive ? '+' : ''}${change.value.toFixed(1)}` }) : `${positive ? '+' : ''}${change.value.toFixed(1)}%`
    return <em className={positive ? 'is-positive' : change.value < 0 ? 'is-negative' : 'is-neutral'}>{label}</em>
  }
}

export function calculateDashboardChange(current: number, previous: number | undefined, kind: 'number' | 'rate', comparable: boolean): ChangeResult {
  if (!comparable || previous === undefined) return { kind: 'none', value: 0 }
  if (kind === 'rate') return { kind: 'points', value: (current - previous) * 100 }
  if (previous === 0 && current > 0) return { kind: 'new', value: current }
  if (previous === 0) return { kind: 'percent', value: 0 }
  return { kind: 'percent', value: ((current - previous) / previous) * 100 }
}

export function buildTrendDatasets(topic: AdminDashboardTopic, current: AdminDashboardSeriesPoint[], previous: AdminDashboardSeriesPoint[], includePrevious: boolean, label: (metric: TrendMetric) => string, previousLabel = 'previous', _themeRevision = 0): DashboardDataset[] {
  const metrics = DASHBOARD_TOPIC_METRICS[topic]
  const datasets: DashboardDataset[] = []
  metrics.forEach((metric, index) => {
    const color = cssColor(SERIES_COLORS[index], index === 0 ? '#6d5ce7' : '#178f87')
    datasets.push({
      label: label(metric),
      data: current.map((point) => metricValue(point, metric)),
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      pointRadius: 2,
      pointHoverRadius: 5,
      tension: 0.24,
      yAxisID: metric === 'success_rate' ? 'yRate' : 'y',
      dashboardMetric: metric,
      dashboardPrevious: false,
    })
    if (includePrevious && previous.length > 0) datasets.push({
      label: `${label(metric)} · ${previousLabel}`,
      data: current.map((_, pointIndex) => metricValue(previous[pointIndex], metric)),
      borderColor: color,
      backgroundColor: color,
      borderWidth: 1.5,
      borderDash: [6, 5],
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.24,
      yAxisID: metric === 'success_rate' ? 'yRate' : 'y',
      dashboardMetric: metric,
      dashboardPrevious: true,
    })
  })
  return datasets
}

function Diagnostics({ dashboard, current, number }: { dashboard: AdminDashboard; current: AdminDashboardPeriodSummary; number: Intl.NumberFormat }) {
  const { t } = useI18n()
  const closed = current.succeeded + current.failed
  const values = [
    [t('admin.overview.diagnostics.outcome'), `${number.format(current.succeeded)} / ${number.format(current.failed)}`, closed > 0 ? `${(current.success_rate * 100).toFixed(1)}%` : '—'],
    [t('admin.overview.diagnostics.netCredits'), signed(number, current.net_credits), `${number.format(current.credits_recharged)} − ${number.format(current.credits_consumed)}`],
    [t('admin.overview.diagnostics.paymentRate'), `${(current.payment_rate * 100).toFixed(1)}%`, `${number.format(current.orders_converted)} / ${number.format(current.orders_created)}`],
    [t('admin.overview.diagnostics.payingRate'), `${(current.active_to_paying_rate * 100).toFixed(1)}%`, `${number.format(current.paying_users)} / ${number.format(current.active_users)}`],
  ]
  return <aside className="dashboard-diagnostics" aria-label={t('admin.overview.diagnostics.title')}><div><h2>{t('admin.overview.diagnostics.title')}</h2><p>{t('admin.overview.diagnostics.description')}</p></div>{values.map(([label, value, meta]) => <div className="dashboard-diagnostic-row" key={label}><span>{label}<small>{meta}</small></span><strong>{value}</strong></div>)}<div className={`dashboard-diagnostic-note ${dashboard.failure_rate > .1 ? 'is-danger' : ''}`}>{t('admin.overview.diagnostics.todayFailureRate', { value: `${(dashboard.failure_rate * 100).toFixed(1)}%` })}</div></aside>
}

function RealtimeStatus({ dashboard, number }: { dashboard: AdminDashboard; number: Intl.NumberFormat }) {
  const { t } = useI18n()
  const alerts = dashboard.running_over_30m_jobs + dashboard.policy_blocked_today + dashboard.upstream_errors_today + dashboard.timeout_jobs_today + dashboard.pipeline_errors_today
  return <section className={`dashboard-realtime ${alerts > 0 ? 'has-alerts' : ''}`} aria-label={t('admin.overview.realtime.title')}><div><b>{t('admin.overview.realtime.title')}</b><span>{t('admin.overview.realtime.description')}</span></div><dl><div><dt>{t('admin.overview.realtime.pending')}</dt><dd>{number.format(dashboard.pending_jobs)}</dd></div><div><dt>{t('admin.overview.realtime.running')}</dt><dd>{number.format(dashboard.running_jobs)}</dd></div><div><dt>{t('admin.overview.realtime.over30m')}</dt><dd>{number.format(dashboard.running_over_30m_jobs)}</dd></div><div><dt>{t('admin.overview.realtime.failures')}</dt><dd>{number.format(dashboard.failed_today)}</dd></div><div><dt>{t('admin.overview.realtime.alerts')}</dt><dd>{number.format(alerts + dashboard.candidate_failures_today + dashboard.pipeline_warnings_today)}</dd></div></dl></section>
}

function Ledger({ dashboard, number }: { dashboard: AdminDashboard; number: Intl.NumberFormat }) {
  const { t } = useI18n()
  const items = [
    ['users', dashboard.total_users], ['jobs', dashboard.total_jobs], ['succeeded', dashboard.total_succeeded], ['failed', dashboard.total_failed], ['recharged', dashboard.total_credits_recharged], ['consumed', dashboard.total_credits_consumed], ['orders', dashboard.total_orders_created], ['paidOrders', dashboard.total_orders_paid], ['uploads', dashboard.total_uploads],
  ] as const
  return <section className="dashboard-ledger" aria-label={t('admin.overview.ledger.title')}><div><b>{t('admin.overview.ledger.title')}</b><span>{t('admin.overview.ledger.description')}</span></div><dl>{items.map(([key, value]) => <div key={key}><dt>{t(`admin.overview.ledger.${key}`)}</dt><dd>{number.format(value)}</dd></div>)}</dl></section>
}

function BucketRow({ point, index, selected, dateTime, number, onSelect }: BucketProps) {
  return <button type="button" role="row" data-dashboard-bucket={index} aria-selected={selected} className="dashboard-bucket-row" onClick={onSelect}><span>{formatExactRange(point, dateTime)}</span><span>{number.format(point.jobs)} · {(point.success_rate * 100).toFixed(1)}%</span><span>+{number.format(point.credits_recharged)} / −{number.format(point.credits_consumed)}</span><span>{number.format(point.orders_created)} / {number.format(point.orders_paid)}</span><span>{number.format(point.active_users)} / {number.format(point.new_users)}</span></button>
}

function BucketMobile({ point, index, selected, dateTime, number, onSelect }: BucketProps) {
  const { t } = useI18n()
  return <button type="button" data-dashboard-bucket={index} aria-pressed={selected} className="dashboard-bucket-mobile" onClick={onSelect}><time>{formatExactRange(point, dateTime)}</time><dl><div><dt>{t('admin.overview.details.columns.jobs')}</dt><dd>{number.format(point.jobs)} · {(point.success_rate * 100).toFixed(1)}%</dd></div><div><dt>{t('admin.overview.details.columns.credits')}</dt><dd>+{number.format(point.credits_recharged)} / −{number.format(point.credits_consumed)}</dd></div><div><dt>{t('admin.overview.details.columns.orders')}</dt><dd>{number.format(point.orders_created)} / {number.format(point.orders_paid)}</dd></div><div><dt>{t('admin.overview.details.columns.users')}</dt><dd>{number.format(point.active_users)} / {number.format(point.new_users)}</dd></div></dl></button>
}

type BucketProps = { point: AdminDashboardSeriesPoint; index: number; selected: boolean; dateTime: Intl.DateTimeFormat; number: Intl.NumberFormat; onSelect: () => void }

function normalizeDashboard(dashboard: AdminDashboard) {
  const fallbackSeries = (dashboard.history ?? []).map<AdminDashboardSeriesPoint>((point) => {
    const closed = point.succeeded + point.failed
    return {
      start_at: `${point.date}T00:00:00Z`, end_at: `${shiftDate(point.date, 1)}T00:00:00Z`, jobs: point.jobs, succeeded: point.succeeded, failed: point.failed,
      credits_consumed: point.credits_consumed, credits_recharged: point.credits_recharged, net_credits: point.credits_recharged - point.credits_consumed,
      orders_created: point.orders_created, orders_paid: point.orders_paid, orders_converted: point.orders_paid, uploads: point.uploads, new_users: point.new_users,
      active_users: point.new_users, paying_users: point.orders_paid, success_rate: closed ? point.succeeded / closed : 0,
      payment_rate: point.orders_created ? point.orders_paid / point.orders_created : 0, active_to_paying_rate: point.new_users ? point.orders_paid / point.new_users : 0,
      has_data: point.jobs + point.credits_recharged + point.orders_created + point.uploads + point.new_users > 0,
    }
  })
  const series = dashboard.series ?? fallbackSeries
  const current = dashboard.current_period ?? summarizeSeries(series)
  const first = series[0]?.start_at ?? new Date().toISOString()
  const end = series[series.length - 1]?.end_at ?? new Date().toISOString()
  return {
    series,
    previousSeries: dashboard.previous_series ?? [],
    current,
    previous: dashboard.previous_period ?? null,
    window: dashboard.window ?? { range: '14d' as const, granularity: 'day' as const, timezone: 'site', start_at: first, end_at: end, generated_at: end, data_cutoff_at: end, compare_enabled: false, comparison_start_at: null, comparison_end_at: null },
  }
}

function summarizeSeries(series: AdminDashboardSeriesPoint[]): AdminDashboardPeriodSummary {
  const sum = (key: keyof AdminDashboardSeriesPoint) => series.reduce((total, point) => total + Number(point[key] ?? 0), 0)
  const succeeded = sum('succeeded')
  const failed = sum('failed')
  const ordersCreated = sum('orders_created')
  const activeUsers = sum('active_users')
  const payingUsers = sum('paying_users')
  const recharged = sum('credits_recharged')
  const consumed = sum('credits_consumed')
  return { jobs: sum('jobs'), succeeded, failed, credits_consumed: consumed, credits_recharged: recharged, net_credits: recharged - consumed, orders_created: ordersCreated, orders_paid: sum('orders_paid'), orders_converted: sum('orders_converted'), uploads: sum('uploads'), new_users: sum('new_users'), active_users: activeUsers, paying_users: payingUsers, success_rate: succeeded + failed ? succeeded / (succeeded + failed) : 0, payment_rate: ordersCreated ? sum('orders_converted') / ordersCreated : 0, active_to_paying_rate: activeUsers ? payingUsers / activeUsers : 0, has_data: series.some((point) => point.has_data) }
}

function metricValue(point: AdminDashboardSeriesPoint | undefined, metric: TrendMetric) {
  if (!point) return 0
  return metric === 'success_rate' ? point.success_rate * 100 : point[metric]
}

function syncChartSelection(chart: ChartJS<'line'> | null, index: number) {
  if (!chart || index < 0) return
  const active = chart.data.datasets.flatMap((_, datasetIndex) => chart.isDatasetVisible(datasetIndex) ? [{ datasetIndex, index }] : [])
  ;(chart as ChartJS<'line'> & { dashboardSelectedIndex?: number }).dashboardSelectedIndex = index
  chart.setActiveElements(active)
  const x = chart.scales.x?.getPixelForValue(index) ?? 0
  chart.tooltip?.setActiveElements(active, { x, y: chart.chartArea.top })
  chart.update('none')
}

function datasetId(dataset: DashboardDataset) { return `${dataset.dashboardMetric}:${dataset.dashboardPrevious ? 'previous' : 'current'}` }
function signed(number: Intl.NumberFormat, value: number) { return `${value > 0 ? '+' : ''}${number.format(value)}` }
function formatExactRange(point: AdminDashboardSeriesPoint | undefined, formatter: Intl.DateTimeFormat) { return point ? `${formatter.format(new Date(point.start_at))} – ${formatter.format(new Date(point.end_at))}` : '—' }
function safeTimeZone(timeZone: string) {
  const candidates = [timeZone]
  const offset = /^UTC([+-])(\d{2}):(\d{2})$/.exec(timeZone)
  if (offset) {
    candidates.push(`${offset[1]}${offset[2]}:${offset[3]}`)
    if (offset[3] === '00') candidates.push(`Etc/GMT${offset[1] === '+' ? '-' : '+'}${Number(offset[2])}`)
  }
  return candidates.find((candidate) => {
    try { new Intl.DateTimeFormat('en-US', { timeZone: candidate }).format(); return true } catch { return false }
  })
}
function shiftDate(date: string, days: number) { const value = new Date(`${date}T00:00:00Z`); value.setUTCDate(value.getUTCDate() + days); return value.toISOString().slice(0, 10) }
function cssColor(name: string, fallback: string) {
  if (typeof document === 'undefined') return fallback
  const target = document.querySelector<HTMLElement>('.dashboard-overview') ?? document.documentElement
  return getComputedStyle(target).getPropertyValue(name).trim() || fallback
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => { const media = window.matchMedia('(prefers-reduced-motion: reduce)'); const sync = () => setReduced(media.matches); sync(); media.addEventListener('change', sync); return () => media.removeEventListener('change', sync) }, [])
  return reduced
}

function useThemeRevision() {
  const [revision, setRevision] = useState(0)
  useEffect(() => { const observer = new MutationObserver(() => setRevision((value) => value + 1)); observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); return () => observer.disconnect() }, [])
  return revision
}
