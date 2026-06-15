import { useCallback, useEffect, useRef, useState } from 'react'
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
} from 'chart.js'
import { Chart } from 'react-chartjs-2'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { PerformanceMetrics } from '../types'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, BarController, LineController, Tooltip, Filler)

const RANGES = ['1h', '24h', '7d'] as const
const POLL_MS = 8000

function hhmm(iso: string): string {
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function PerformanceMonitorTab({ token }: { token: string }) {
  const { text } = useI18n()
  const [range, setRange] = useState<string>('24h')
  const [data, setData] = useState<PerformanceMetrics | null>(null)
  const [error, setError] = useState('')
  const rangeRef = useRef(range)
  rangeRef.current = range

  const load = useCallback(async () => {
    try {
      const result = await api.performanceMetrics(token, rangeRef.current)
      setData(result)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [token])

  useEffect(() => {
    void load()
    const timer = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(timer)
  }, [load, range])

  const isDark = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-color-scheme: dark)').matches
  const tickColor = isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.55)'
  const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)'

  const series = data?.series ?? []
  const labels = series.map((p) => hhmm(p.t))
  const succeeded = series.map((p) => p.succeeded)
  const failed = series.map((p) => p.failed)
  const totals = series.map((p) => p.total)
  const rates = series.map((p) => {
    const closed = p.succeeded + p.failed
    return closed ? Math.round((p.succeeded / closed) * 100) : 0
  })
  const kpi = data?.kpi

  const mainData = {
    labels,
    datasets: [
      { type: 'bar', label: text('成功', 'Succeeded'), data: succeeded, backgroundColor: '#1D9E75', stack: 's', yAxisID: 'y' },
      { type: 'bar', label: text('失败', 'Failed'), data: failed, backgroundColor: '#E24B4A', stack: 's', yAxisID: 'y' },
      { type: 'line', label: text('成功率', 'Success %'), data: rates, borderColor: '#378ADD', backgroundColor: 'rgba(55,138,221,0.10)', yAxisID: 'y1', tension: 0.35, pointRadius: 0, borderWidth: 2, fill: true },
    ],
  } as never
  const mainOptions = {
    responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false },
    scales: {
      y: { stacked: true, beginAtZero: true, grid: { color: gridColor }, ticks: { color: tickColor, precision: 0 } },
      y1: { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { color: tickColor, callback: (v: number) => `${v}%` } },
      x: { grid: { display: false }, ticks: { color: tickColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
    },
    plugins: { legend: { display: false } },
  } as never

  const concData = {
    labels,
    datasets: [{ type: 'line', data: totals, borderColor: '#7F77DD', backgroundColor: 'rgba(127,119,221,0.15)', tension: 0.35, pointRadius: 0, borderWidth: 2, fill: true }],
  } as never
  const concOptions = {
    responsive: true, maintainAspectRatio: false, animation: false,
    scales: {
      y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: tickColor, precision: 0, maxTicksLimit: 4 } },
      x: { grid: { display: false }, ticks: { color: tickColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 4 } },
    },
    plugins: { legend: { display: false } },
  } as never

  return (
    <div className="grid gap-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex gap-2">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 rounded-md text-sm border ${range === r ? 'bg-foreground text-background border-transparent' : 'border-border text-muted-foreground hover:bg-muted'}`}
            >
              {r === '1h' ? text('近 1 小时', 'Last 1h') : r === '24h' ? text('近 24 小时', 'Last 24h') : text('近 7 天', 'Last 7d')}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted-foreground">
          {data ? `${text('更新于 ', 'Updated ')}${new Date(data.generated_at).toLocaleTimeString()}` : '—'}
        </span>
      </div>

      {error && <div className="text-sm text-destructive">{text('加载失败：', 'Load failed: ')}{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label={text('成功率', 'Success rate')} value={kpi ? `${Math.round(kpi.success_rate * 100)}%` : '—'} />
        <Metric label={text('活跃并发', 'Running')} value={kpi ? String(kpi.running) : '—'} sub={text('运行中任务', 'in flight')} />
        <Metric label={text('任务总数', 'Total tasks')} value={kpi ? kpi.total.toLocaleString() : '—'} sub={kpi ? `${kpi.failed} ${text('失败', 'failed')}` : ''} />
        <Metric label={text('平均耗时', 'Avg time')} value={kpi ? `${kpi.avg_seconds}s` : '—'} sub={kpi ? `p95 ${kpi.p95_seconds}s` : ''} />
      </div>

      <div>
        <div className="text-sm text-muted-foreground mb-2">{text('任务量与成功率', 'Task volume & success rate')}</div>
        <div style={{ position: 'relative', height: 260 }}>
          <Chart type="bar" data={mainData} options={mainOptions} />
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <div className="text-sm text-muted-foreground mb-2">{text('任务吞吐（每桶任务数）', 'Throughput (tasks per bucket)')}</div>
          <div style={{ position: 'relative', height: 160 }}>
            <Chart type="line" data={concData} options={concOptions} />
          </div>
        </div>
        <div>
          <div className="text-sm text-muted-foreground mb-2">{text('Provider 成功率', 'Provider success rate')}</div>
          <div className="grid gap-2">
            {(data?.providers ?? []).map((p) => (
              <ProviderBar key={p.provider || 'unknown'} name={p.provider || text('未知', 'unknown')} rate={Math.round(p.success_rate * 100)} total={p.total} />
            ))}
            {(!data || data.providers.length === 0) && <div className="text-xs text-muted-foreground">{text('暂无数据', 'No data yet')}</div>}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <div className="text-sm text-muted-foreground mb-2">{text('失败分类', 'Failure breakdown')}</div>
          <div className="grid gap-1.5">
            {(data?.failures ?? []).map((f) => (
              <div key={f.code} className="flex justify-between text-sm">
                <span className="font-mono text-xs">{f.code}</span>
                <span className="text-muted-foreground">{f.count}</span>
              </div>
            ))}
            {(!data || data.failures.length === 0) && <div className="text-xs text-muted-foreground">{text('无失败', 'No failures')}</div>}
          </div>
        </div>
        <div>
          <div className="text-sm text-muted-foreground mb-2">{text('最近任务', 'Recent tasks')}</div>
          <div className="grid gap-1.5">
            {(data?.recent ?? []).map((job) => (
              <div key={job.id} className="flex items-center gap-2 text-xs">
                <span className="font-mono text-muted-foreground">#{job.id}</span>
                <span className={`px-1.5 py-0.5 rounded ${job.status === 'succeeded' ? 'bg-emerald-500/15 text-emerald-600' : job.status === 'failed' ? 'bg-red-500/15 text-red-600' : 'bg-muted text-muted-foreground'}`}>{job.status}</span>
                <span>{job.job_type}</span>
                {job.provider && <span className="text-muted-foreground">{job.provider}</span>}
                {job.failure_code && <span className="text-red-600">{job.failure_code}</span>}
                <span className="ml-auto text-muted-foreground">{job.seconds}s</span>
              </div>
            ))}
            {(!data || data.recent.length === 0) && <div className="text-xs text-muted-foreground">{text('暂无任务', 'No tasks')}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md bg-muted/50 p-3">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-2xl font-medium">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  )
}

function ProviderBar({ name, rate, total }: { name: string; rate: number; total: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span>{name}</span>
        <span className="text-muted-foreground">{rate}% · {total}</span>
      </div>
      <div className="h-1.5 rounded bg-muted overflow-hidden flex">
        <div style={{ width: `${rate}%`, background: '#1D9E75' }} />
        <div style={{ width: `${100 - rate}%`, background: '#E24B4A', opacity: 0.5 }} />
      </div>
    </div>
  )
}
