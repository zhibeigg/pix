import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw, Search } from 'lucide-react'
import { api } from '../api'
import { formatDateTime } from '../lib/utils'
import type { AdminPaymentOrder } from '../types'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { FilterBar, dataInputClass, dataOptionClass, dataSelectClass } from './data/FilterBar'

type AdminOrdersPanelProps = { token: string }

type StatusFilter = 'all' | 'paid' | 'pending' | 'failed'
type KindFilter = 'all' | 'recharge' | 'membership'
type SortKey = 'created_at' | 'amount_cents' | 'credits'
type SortDir = 'asc' | 'desc'

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: '全部状态' },
  { value: 'paid', label: '已支付' },
  { value: 'pending', label: '待支付' },
  { value: 'failed', label: '失败/取消' },
]

const KIND_OPTIONS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: '全部类型' },
  { value: 'recharge', label: '点数充值' },
  { value: 'membership', label: '月卡会员' },
]

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'created_at', label: '按创建时间' },
  { value: 'amount_cents', label: '按金额' },
  { value: 'credits', label: '按点数' },
]

function money(cents: number, currency = 'cny') {
  const prefix = currency.toLowerCase() === 'cny' ? '¥' : `${currency.toUpperCase()} `
  return `${prefix}${(cents / 100).toFixed(2)}`
}

function statusVariant(status: string): 'success' | 'warning' | 'outline' {
  if (status === 'paid') return 'success'
  if (status === 'pending') return 'warning'
  return 'outline'
}

/** 后台订单总览：所有用户的充值 / 月卡订单，支持按状态、类型、关键词筛选与多字段排序。 */
export function AdminOrdersPanel({ token }: AdminOrdersPanelProps) {
  const [orders, setOrders] = useState<AdminPaymentOrder[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [kindFilter, setKindFilter] = useState<KindFilter>('all')
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const result = await api.adminOrders(token)
      setOrders(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载订单失败')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    const rows = orders.filter((order) => {
      if (statusFilter !== 'all' && order.status !== statusFilter) return false
      if (kindFilter !== 'all' && order.order_kind !== kindFilter) return false
      if (keyword) {
        const haystack = `${order.user_email} ${order.user_display_name} ${order.provider_order_id} #${order.id} #${order.user_id}`.toLowerCase()
        if (!haystack.includes(keyword)) return false
      }
      return true
    })
    const dir = sortDir === 'asc' ? 1 : -1
    return rows.sort((a, b) => {
      if (sortKey === 'created_at') return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * dir
      return (a[sortKey] - b[sortKey]) * dir
    })
  }, [orders, statusFilter, kindFilter, query, sortKey, sortDir])

  const totalPaidCents = useMemo(
    () => filtered.filter((o) => o.status === 'paid').reduce((sum, o) => sum + o.amount_cents, 0),
    [filtered],
  )

  function reset() {
    setStatusFilter('all')
    setKindFilter('all')
    setQuery('')
    setSortKey('created_at')
    setSortDir('desc')
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">全部订单</h3>
          <p className="text-sm text-muted-foreground">所有用户的充值 / 月卡订单总览，可按状态、类型、关键词筛选与排序。</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{filtered.length} 笔</Badge>
          <Badge variant="success">已收 {money(totalPaidCents)}</Badge>
        </div>
      </div>

      <FilterBar>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} className={dataSelectClass}>
          {STATUS_OPTIONS.map((item) => <option key={item.value} value={item.value} className={dataOptionClass}>{item.label}</option>)}
        </select>
        <select value={kindFilter} onChange={(event) => setKindFilter(event.target.value as KindFilter)} className={dataSelectClass}>
          {KIND_OPTIONS.map((item) => <option key={item.value} value={item.value} className={dataOptionClass}>{item.label}</option>)}
        </select>
        <select value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)} className={dataSelectClass}>
          {SORT_OPTIONS.map((item) => <option key={item.value} value={item.value} className={dataOptionClass}>{item.label}</option>)}
        </select>
        <button type="button" onClick={() => setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))} className={dataSelectClass} title="切换升/降序">
          {sortDir === 'asc' ? '升序 ↑' : '降序 ↓'}
        </button>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--data-text-faint))]" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索邮箱 / 昵称 / 订单号 / #ID" className={`${dataInputClass} pl-9`} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={() => void load()}><RefreshCw />{loading ? '刷新中…' : '刷新'}</Button>
          <Button type="button" size="sm" variant="ghost" onClick={reset}>重置</Button>
        </div>
      </FilterBar>

      {error && <Alert variant="destructive">{error}</Alert>}

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[860px] text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
              <th className="px-3 py-2 font-medium">订单</th>
              <th className="px-3 py-2 font-medium">用户</th>
              <th className="px-3 py-2 font-medium">类型</th>
              <th className="px-3 py-2 font-medium">金额</th>
              <th className="px-3 py-2 font-medium">点数</th>
              <th className="px-3 py-2 font-medium">状态</th>
              <th className="px-3 py-2 font-medium">创建时间</th>
              <th className="px-3 py-2 font-medium">支付时间</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-muted-foreground">{loading ? '加载中…' : '暂无订单'}</td></tr>
            ) : filtered.map((order) => (
              <tr key={order.id} className="border-b border-border last:border-b-0">
                <td className="px-3 py-2">
                  <span className="block font-medium">#{order.id}</span>
                  <span className="block truncate text-xs text-muted-foreground" title={order.provider_order_id}>{order.provider}·{order.provider_order_id || '—'}</span>
                </td>
                <td className="px-3 py-2">
                  <span className="block truncate font-medium" title={order.user_email}>{order.user_display_name || order.user_email || '—'}</span>
                  <span className="block truncate text-xs text-muted-foreground">#{order.user_id} · {order.user_email}</span>
                </td>
                <td className="px-3 py-2">
                  {order.order_kind === 'membership'
                    ? <Badge variant="secondary">月卡{order.membership_plan_key ? `·${order.membership_plan_key}` : ''}</Badge>
                    : <Badge variant="outline">充值</Badge>}
                </td>
                <td className="px-3 py-2 whitespace-nowrap font-medium">{money(order.amount_cents, order.currency)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{order.order_kind === 'membership' ? '—' : order.credits}</td>
                <td className="px-3 py-2"><Badge variant={statusVariant(order.status)}>{order.status}</Badge></td>
                <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(order.created_at)}</td>
                <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">{order.paid_at ? formatDateTime(order.paid_at) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
