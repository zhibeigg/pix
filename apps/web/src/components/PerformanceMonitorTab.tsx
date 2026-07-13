import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  BarController,
  LineController,
  Tooltip,
  Filler,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import { Chart } from 'react-chartjs-2'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { PerformanceMetrics } from '../types'
import { Alert } from './ui/alert'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, BarController, LineController, Tooltip, Filler)

const RANGES = ['1h', '24h', '7d'] as const
const POLL_MS = 8000

type PerformanceRange = (typeof RANGES)[number]
type AsyncPhase = 'idle' | 'loading' | 'refreshing' | 'ready' | 'error'

function hhmm(iso: string): string {
  const date = new Date(iso)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function currentTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function PerformanceMonitorTab({ token }: { token: string }) {
  const { t } = useI18n()
  const [range, setRange] = useState<PerformanceRange>('24h')
  const [data, setData] = useState<PerformanceMetrics | null>(null)
  const [phase, setPhase] = useState<AsyncPhase>('idle')
  const [error, setError] = useState('')
  const [theme, setTheme] = useState<'light' | 'dark'>(() => currentTheme())

  const load = useCallback(async () => {
    setPhase((current) => current === 'ready' || data ? 'refreshing' : 'loading')
    try {
      const result = await api.performanceMetrics(token, range)
      setData(result)
      setError('')
      setPhase('ready')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
      setPhase('error')
    }
  }, [data, range, token])

  useEffect(() => {
    void load()
  }, [range, token]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let timer = 0
    const schedule = () => {
      window.clearTimeout(timer)
      if (document.visibilityState === 'visible') timer = window.setTimeout(async () => { await load(); schedule() }, POLL_MS)
    }
    const onVisibility = () => schedule()
    document.addEventListener('visibilitychange', onVisibility)
    schedule()
    return () => { document.removeEventListener('visibilitychange', onVisibility); window.clearTimeout(timer) }
  }, [load])

  useEffect(() => {
    const root = document.documentElement
    const observer = new MutationObserver(() => setTheme(currentTheme()))
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  const tickColor = theme === 'dark' ? 'rgba(255,255,255,0.68)' : 'rgba(0,0,0,0.58)'
  const gridColor = theme === 'dark' ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.07)'
  const series = data?.series ?? []
  const labels = series.map((point) => hhmm(point.t))
  const succeeded = series.map((point) => point.succeeded)
  const failed = series.map((point) => point.failed)
  const totals = series.map((point) => point.total)
  const rates = series.map((point) => {
    const closed = point.succeeded + point.failed
    return closed ? Math.round((point.succeeded / closed) * 100) : 0
  })
  const kpi = data?.kpi

  const mainData = useMemo<ChartData<'bar' | 'line', number[], string>>(() => ({
    labels,
    datasets: [
      { type: 'bar', label: t('admin.performance.succeeded'), data: succeeded, backgroundColor: '#1D9E75', stack: 's', yAxisID: 'y' },
      { type: 'bar', label: t('admin.performance.failed'), data: failed, backgroundColor: '#E24B4A', stack: 's', yAxisID: 'y' },
      { type: 'line', label: t('admin.performance.successRate'), data: rates, borderColor: '#378ADD', backgroundColor: 'rgba(55,138,221,0.10)', yAxisID: 'y1', tension: 0.35, pointRadius: 0, borderWidth: 2, fill: true },
    ],
  }), [failed, labels, rates, succeeded, t])

  const mainOptions = useMemo<ChartOptions<'bar' | 'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: { stacked: true, beginAtZero: true, grid: { color: gridColor }, ticks: { color: tickColor, precision: 0 } },
      y1: { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { color: tickColor, callback: (value) => `${value}%` } },
      x: { grid: { display: false }, ticks: { color: tickColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
    },
    plugins: { legend: { display: false } },
  }), [gridColor, tickColor])

  const throughputData = useMemo<ChartData<'line', number[], string>>(() => ({ labels, datasets: [{ data: totals, borderColor: '#7F77DD', backgroundColor: 'rgba(127,119,221,0.15)', tension: 0.35, pointRadius: 0, borderWidth: 2, fill: true }] }), [labels, totals])
  const throughputOptions = useMemo<ChartOptions<'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: tickColor, precision: 0, maxTicksLimit: 4 } },
      x: { grid: { display: false }, ticks: { color: tickColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 4 } },
    },
    plugins: { legend: { display: false } },
  }), [gridColor, tickColor])

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">{RANGES.map((item) => <button type="button" key={item} onClick={() => setRange(item)} className={`rounded-md border px-3 py-1 text-sm ${range === item ? 'border-transparent bg-foreground text-background' : 'border-border text-muted-foreground hover:bg-muted'}`}>{t(`admin.performance.range.${item}`)}</button>)}</div>
        <span className="text-xs text-muted-foreground">{phase === 'refreshing' ? t('admin.performance.refreshing') : data ? t('admin.performance.updatedAt', { time: new Date(data.generated_at).toLocaleTimeString() }) : '—'}</span>
      </div>

      {error && <Alert variant="destructive">{t('admin.performance.loadFailed', { error })}</Alert>}
      {phase === 'loading' && !data && <Alert variant="info">{t('admin.common.loading')}</Alert>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label={t('admin.performance.successRate')} value={kpi ? `${Math.round(kpi.success_rate * 100)}%` : '—'} />
        <Metric label={t('admin.performance.running')} value={kpi ? String(kpi.running) : '—'} sub={t('admin.performance.inFlight')} />
        <Metric label={t('admin.performance.totalTasks')} value={kpi ? kpi.total.toLocaleString() : '—'} sub={kpi ? t('admin.performance.failedCount', { count: kpi.failed }) : ''} />
        <Metric label={t('admin.performance.averageTime')} value={kpi ? `${kpi.avg_seconds}s` : '—'} sub={kpi ? `p95 ${kpi.p95_seconds}s` : ''} />
      </div>

      <section><p className="mb-2 text-sm text-muted-foreground">{t('admin.performance.volume')}</p><div className="relative h-[260px]"><Chart type="bar" data={mainData} options={mainOptions} /></div></section>
      <div className="grid gap-5 md:grid-cols-2">
        <section><p className="mb-2 text-sm text-muted-foreground">{t('admin.performance.throughput')}</p><div className="relative h-40"><Chart type="line" data={throughputData} options={throughputOptions} /></div></section>
        <section><p className="mb-2 text-sm text-muted-foreground">{t('admin.performance.providers')}</p><div className="grid gap-2">{(data?.providers ?? []).map((provider) => <ProviderBar key={provider.provider || 'unknown'} name={provider.display_name || provider.provider || t('admin.performance.unknown')} id={provider.provider} enabled={provider.enabled} rate={Math.round(provider.success_rate * 100)} total={provider.total} />)}{(!data || data.providers.length === 0) && <p className="text-xs text-muted-foreground">{t('admin.performance.noData')}</p>}</div></section>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <section><p className="mb-2 text-sm text-muted-foreground">{t('admin.performance.failures')}</p><div className="grid gap-1.5">{(data?.failures ?? []).map((failure) => <div key={failure.code} className="flex justify-between text-sm"><span className="font-mono text-xs">{failure.code}</span><span className="text-muted-foreground">{failure.count}</span></div>)}{(!data || data.failures.length === 0) && <p className="text-xs text-muted-foreground">{t('admin.performance.noFailures')}</p>}</div></section>
        <section><p className="mb-2 text-sm text-muted-foreground">{t('admin.performance.recent')}</p><div className="grid gap-1.5">{(data?.recent ?? []).map((job) => <div key={job.id} className="flex items-center gap-2 text-xs"><span className="font-mono text-muted-foreground">#{job.id}</span><span className="rounded bg-muted px-1.5 py-0.5">{t(`admin.status.job.${job.status}`, { defaultValue: job.status })}</span><span>{job.job_type}</span>{job.provider && <span className="text-muted-foreground">{job.provider_display_name || job.provider}</span>}{job.failure_code && <span className="text-destructive">{job.failure_code}</span>}<span className="ml-auto text-muted-foreground">{job.seconds}s</span></div>)}{(!data || data.recent.length === 0) && <p className="text-xs text-muted-foreground">{t('admin.performance.noTasks')}</p>}</div></section>
      </div>
    </div>
  )
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return <div className="rounded-md bg-muted/50 p-3"><p className="mb-1 text-xs text-muted-foreground">{label}</p><p className="text-2xl font-medium">{value}</p>{sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}</div>
}

function ProviderBar({ name, id, enabled, rate, total }: { name: string; id: string; enabled: boolean; rate: number; total: number }) {
  const { t } = useI18n()
  return <div><div className="mb-1 flex justify-between gap-3 text-xs"><span className="min-w-0 truncate">{name}{id && id !== name && <span className="ml-1 text-muted-foreground">{id}</span>}{!enabled && <span className="ml-1 text-muted-foreground">{t('admin.performance.disabled')}</span>}</span><span className="shrink-0 text-muted-foreground">{rate}% · {total}</span></div><div className="flex h-1.5 overflow-hidden rounded bg-muted"><div style={{ width: `${rate}%`, background: '#1D9E75' }} /><div style={{ width: `${100 - rate}%`, background: '#E24B4A', opacity: .5 }} /></div></div>
}
