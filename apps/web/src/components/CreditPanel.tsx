import { useMemo, useState } from 'react'
import { Copy, Download, RotateCcw, Search, Users } from 'lucide-react'
import { useI18n } from '../i18n'
import type { CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, PaymentCheckout, PaymentOrder } from '../types'
import { formatDateTime } from '../lib/utils'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { DataTable, type DataColumn, type DataRow } from './data/DataTable'
import { FilterBar, dataInputClass, dataOptionClass, dataSelectClass } from './data/FilterBar'
import { MetricPill, type DataTone } from './data/MetricPill'
import { StatusPill } from './data/StatusPill'
import { PixMetric } from './pix/PixMetric'
import { PixPanel } from './pix/PixPanel'

const TX_TYPES = ['all', 'recharge', 'reserve', 'consume', 'refund', 'adjust', 'other'] as const
type TxFilter = typeof TX_TYPES[number]

type Props = {
  balance: CreditBalance | null
  transactions: CreditTransaction[]
  packages: CreditPackage[]
  customRechargeOptions: CustomRechargeOptions | null
  orders: PaymentOrder[]
  checkout: PaymentCheckout | null
  isAdmin: boolean
  onRefresh: () => void
  onCreateOrder: (packageKey: string) => Promise<void>
  onCheckout: (packageKey: string, provider: string) => Promise<void>
  onCreateCustomOrder: (customCredits: number) => Promise<void>
  onCustomCheckout: (customCredits: number, provider: string) => Promise<void>
  onMockPayOrder: (orderId: number) => Promise<void>
}

function money(cents: number, currency = 'cny') {
  const prefix = currency.toLowerCase() === 'cny' ? '¥' : `${currency.toUpperCase()} `
  return `${prefix}${(cents / 100).toFixed(2)}`
}

export function CreditPanel({ balance, transactions, packages, customRechargeOptions, orders, checkout, isAdmin, onRefresh, onCreateOrder, onCheckout, onCreateCustomOrder, onCustomCheckout, onMockPayOrder }: Props) {
  const { t } = useI18n()
  const [customCredits, setCustomCredits] = useState(100)
  const safeCustomCredits = Number.isFinite(customCredits) ? customCredits : 0
  const customAmountCents = useMemo(() => {
    if (!customRechargeOptions) return 0
    return Math.ceil(customRechargeOptions.base_package_amount_cents * safeCustomCredits / customRechargeOptions.base_package_credits)
  }, [safeCustomCredits, customRechargeOptions])
  const customValid = Boolean(customRechargeOptions && safeCustomCredits >= customRechargeOptions.min_credits && safeCustomCredits <= customRechargeOptions.max_credits && Number.isInteger(safeCustomCredits))
  const customCurrency = customRechargeOptions?.currency ?? 'cny'

  return (
    <PixPanel eyebrow={t('billing.account.eyebrow')} title={t('billing.account.title')} description={t('billing.account.description')} action={<Button variant="outline" onClick={onRefresh}>{t('common.refresh')}</Button>}>
      <div className="grid gap-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><PixMetric label={t('billing.account.available')} value={balance?.available_credits ?? '—'} /><PixMetric label={t('billing.account.reserved')} value={balance?.reserved_credits ?? '—'} /><PixMetric label={t('billing.account.totalRecharged')} value={balance?.total_recharged ?? '—'} tone="success" /><PixMetric label={t('billing.account.totalSpent')} value={balance?.total_consumed ?? '—'} tone="warning" /></div>

        <CommunityCard />

        <section className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-lg font-semibold">{t('billing.packages.title')}</h3><p className="text-sm text-muted-foreground">{t('billing.packages.description')}</p></div><Badge variant="outline">{t('billing.packages.priority')}</Badge></div>
          <div className="grid gap-3 md:grid-cols-3">{packages.map((item) => { const recommended = item.key === 'pro'; return <article key={item.key} className={`rounded-lg border p-4 ${recommended ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}><div className="grid gap-4"><div><div className="flex items-center gap-2"><h4 className="font-semibold">{item.name}</h4>{recommended && <Badge>{t('common.recommended')}</Badge>}</div><p className="mt-2 text-3xl font-semibold">{item.credits}<span className="ml-1 text-sm text-muted-foreground">{t('common.creditUnit')}</span></p><p className="text-sm text-muted-foreground">{money(item.amount_cents, item.currency)}</p></div><div className="flex flex-wrap gap-2"><Button onClick={() => onCheckout(item.key, 'alipay')}>{t('billing.packages.payAlipay')}</Button>{isAdmin && <Button variant="ghost" onClick={() => onCreateOrder(item.key)}>{t('billing.packages.createMockOrder')}</Button>}</div></div></article> })}</div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
            <div>
              <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-semibold">{t('billing.custom.title')}</h3><Badge variant="secondary">{t('billing.custom.pricedByBackend')}</Badge></div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{t('billing.custom.description')}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)] sm:items-center">
                <Input type="number" min={customRechargeOptions?.min_credits ?? 10} max={customRechargeOptions?.max_credits ?? 100000} step={1} value={customCredits} onChange={(event) => setCustomCredits(Number(event.target.value))} />
                <div className="flex flex-wrap gap-2">{(customRechargeOptions?.suggested_credits ?? [50, 100, 200, 500]).map((credits) => <Button key={credits} type="button" variant="outline" size="sm" onClick={() => setCustomCredits(credits)}>{t('common.points', { count: credits })}</Button>)}</div>
              </div>
              {customRechargeOptions && <p className="mt-3 text-xs text-muted-foreground">{t('billing.custom.allowedRange', { min: customRechargeOptions.min_credits, max: customRechargeOptions.max_credits, baseCredits: customRechargeOptions.base_package_credits, baseAmount: money(customRechargeOptions.base_package_amount_cents, customCurrency) })}</p>}
              {!customValid && <p className="mt-3 text-sm text-destructive">{t('billing.custom.invalid')}</p>}
            </div>
            <div className="rounded-lg border border-border bg-muted/35 p-4">
              <p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{t('billing.custom.estimatedPayment')}</p>
              <p className="mt-2 text-4xl font-semibold text-primary">{money(customAmountCents, customCurrency)}</p>
              <p className="mt-1 text-sm text-muted-foreground">{t('common.points', { count: safeCustomCredits })}</p>
              <div className="mt-4 flex flex-wrap gap-2"><Button disabled={!customValid} onClick={() => onCustomCheckout(safeCustomCredits, 'alipay')}>{t('billing.packages.payAlipay')}</Button>{isAdmin && <Button variant="ghost" disabled={!customValid} onClick={() => onCreateCustomOrder(safeCustomCredits)}>{t('billing.packages.createMockOrder')}</Button>}</div>
            </div>
          </div>
        </section>

        {checkout?.payment_url && <Alert variant="info">{t('billing.checkout.opened')}</Alert>}
        <TopUpOrders orders={orders} isAdmin={isAdmin} onMockPayOrder={onMockPayOrder} />
        <CreditLedgerTable balance={balance} transactions={transactions} onRefresh={onRefresh} />
      </div>
    </PixPanel>
  )
}

function TopUpOrders({ orders, isAdmin, onMockPayOrder }: { orders: PaymentOrder[]; isAdmin: boolean; onMockPayOrder: (orderId: number) => Promise<void> }) {
  const { t } = useI18n()
  return <section className="grid gap-3"><h3 className="text-lg font-semibold">{t('billing.orders.title')}</h3>{orders.length === 0 ? <p className="text-sm text-muted-foreground">{t('billing.orders.empty')}</p> : orders.map((order) => <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-4"><div><p className="font-bold">{t('billing.orders.order', { id: order.id })}</p><p className="text-sm text-muted-foreground">{t('common.points', { count: order.credits })} · {money(order.amount_cents, order.currency)} · {formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><Badge variant={order.status === 'paid' ? 'success' : 'warning'}>{order.status}</Badge>{isAdmin && order.status !== 'paid' && <Button size="sm" onClick={() => onMockPayOrder(order.id)}>{t('billing.orders.mockPay')}</Button>}</div></div>)}</section>
}

function CommunityCard() {
  const { t } = useI18n()
  const qq = t('billing.community.qqNumber')
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(qq)
      } else {
        const el = document.createElement('textarea')
        el.value = qq
        el.setAttribute('readonly', '')
        el.style.position = 'fixed'
        el.style.opacity = '0'
        document.body.appendChild(el)
        el.select()
        document.execCommand('copy')
        document.body.removeChild(el)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 复制失败时静默；用户仍可手动选中数字
    }
  }
  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"><Users className="h-4 w-4" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-2"><h3 className="text-base font-semibold leading-tight">{t('billing.community.title')}</h3><span className="text-xs text-muted-foreground">{t('billing.community.qqLabel')}</span><span className="font-mono text-lg font-semibold tracking-wide text-foreground">{qq}</span></div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{t('billing.community.description')}</p>
        </div>
        <Button type="button" size="sm" variant={copied ? 'secondary' : 'outline'} onClick={handleCopy} aria-live="polite"><Copy className="h-3.5 w-3.5" />{copied ? t('billing.community.copied') : t('billing.community.copy')}</Button>
      </div>
    </section>
  )
}

function CreditLedgerTable({ balance, transactions, onRefresh }: { balance: CreditBalance | null; transactions: CreditTransaction[]; onRefresh: () => void }) {
  const { t } = useI18n()
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<TxFilter>('all')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const filtered = useMemo(() => transactions.filter((tx) => {
    const typeGroup = txTypeGroup(tx.type)
    if (typeFilter !== 'all' && typeGroup !== typeFilter) return false
    const created = new Date(tx.created_at).getTime()
    if (from && created < new Date(`${from}T00:00:00`).getTime()) return false
    if (to && created > new Date(`${to}T23:59:59`).getTime()) return false
    const haystack = `${tx.type} ${tx.note} ${tx.job_id ?? ''}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  }), [from, query, to, transactions, typeFilter])

  const income = filtered.filter((tx) => tx.amount > 0).reduce((sum, tx) => sum + tx.amount, 0)
  const spent = Math.abs(filtered.filter((tx) => tx.amount < 0).reduce((sum, tx) => sum + tx.amount, 0))
  const reset = () => { setQuery(''); setTypeFilter('all'); setFrom(''); setTo('') }
  const columns: DataColumn[] = [
    { key: 'time', header: t('billing.ledger.columns.time') },
    { key: 'type', header: t('billing.ledger.columns.type') },
    { key: 'note', header: t('billing.ledger.columns.note'), className: 'max-w-[420px]' },
    { key: 'job', header: t('billing.ledger.columns.job') },
    { key: 'amount', header: t('billing.ledger.columns.amount'), align: 'right' },
    { key: 'balance', header: t('billing.ledger.columns.balance'), align: 'right' },
  ]
  const rows: DataRow[] = filtered.map((tx) => {
    const group = txTypeGroup(tx.type)
    return {
      key: tx.id,
      cells: [
        <span className="whitespace-nowrap text-[hsl(var(--data-text))]">{formatDateTime(tx.created_at)}</span>,
        <StatusPill tone={txTypeTone(group)}>{txTypeLabel(group, tx.type, t)}</StatusPill>,
        <span className="block truncate text-[hsl(var(--data-text-soft))]">{tx.note || t('common.none')}</span>,
        <span className="whitespace-nowrap text-[hsl(var(--data-text-soft))]">{tx.job_id ? `#${tx.job_id}` : t('common.none')}</span>,
        <span className={`whitespace-nowrap font-semibold ${tx.amount >= 0 ? 'text-[hsl(var(--ledger-pill-green-fg))]' : 'text-[hsl(var(--ledger-pill-rose-fg))]'}`}>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</span>,
        <span className="whitespace-nowrap text-[hsl(var(--data-text))]">{tx.balance_after}</span>,
      ],
    }
  })

  return (
    <DataTable
      eyebrow={t('billing.ledger.eyebrow')}
      title={t('billing.ledger.title')}
      metrics={<><MetricPill label={t('billing.ledger.available')} value={balance?.available_credits ?? 0} tone="blue" /><MetricPill label={t('billing.ledger.reserved')} value={balance?.reserved_credits ?? 0} tone="slate" /><MetricPill label={t('billing.ledger.income')} value={`+${income}`} tone="green" /><MetricPill label={t('billing.ledger.spent')} value={`-${spent}`} tone="rose" /><MetricPill label={t('billing.ledger.rows')} value={filtered.length} tone="slate" /></>}
      filters={<FilterBar><Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} className={dataInputClass} /><Input type="date" value={to} onChange={(event) => setTo(event.target.value)} className={dataInputClass} /><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as TxFilter)} className={dataSelectClass}>{TX_TYPES.map((type) => <option key={type} value={type} className={dataOptionClass}>{txTypeFilterLabel(type, t)}</option>)}</select><div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--data-text-faint))]" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('billing.ledger.keywordPlaceholder')} className={`${dataInputClass} pl-9`} /></div><div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" onClick={onRefresh}><RotateCcw />{t('common.search')}</Button><Button type="button" size="sm" variant="ghost" onClick={reset}>{t('common.reset')}</Button><Button type="button" size="sm" className="bg-sky-600 text-white hover:bg-sky-500" onClick={() => exportLedgerCsv(filtered, t)}><Download />{t('billing.ledger.exportCsv')}</Button></div></FilterBar>}
      columns={columns}
      rows={rows}
      empty={t('billing.ledger.empty')}
    />
  )
}

function txTypeTone(type: TxFilter): DataTone {
  if (type === 'recharge' || type === 'refund') return 'green'
  if (type === 'consume') return 'rose'
  if (type === 'reserve') return 'amber'
  if (type === 'adjust') return 'blue'
  return 'slate'
}

function txTypeGroup(type: string): TxFilter {
  const value = type.toLowerCase()
  if (value.includes('recharge') || value.includes('top')) return 'recharge'
  if (value.includes('reserve')) return 'reserve'
  if (value.includes('consume') || value.includes('spent')) return 'consume'
  if (value.includes('refund')) return 'refund'
  if (value.includes('adjust')) return 'adjust'
  return 'other'
}

function txTypeFilterLabel(type: TxFilter, t: (key: string, options?: Record<string, unknown>) => string) {
  if (type === 'all') return t('billing.ledger.allTypes')
  return txTypeLabel(type, type, t)
}

function txTypeLabel(type: TxFilter, raw: string, t: (key: string, options?: Record<string, unknown>) => string) {
  if (type === 'other') return raw
  return t(`billing.ledger.type.${type}`)
}

function exportLedgerCsv(rows: CreditTransaction[], t: (key: string, options?: Record<string, unknown>) => string) {
  const headers = [t('billing.ledger.columns.time'), t('billing.ledger.columns.type'), t('billing.ledger.columns.note'), t('billing.ledger.columns.jobId'), t('billing.ledger.columns.amount'), t('billing.ledger.columns.balance')]
  const csv = [headers, ...rows.map((tx) => [formatDateTime(tx.created_at), tx.type, tx.note || '', tx.job_id ?? '', tx.amount, tx.balance_after])].map((row) => row.map(csvCell).join(',')).join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `pix-credit-ledger-${timestampForFilename()}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function csvCell(value: unknown) {
  const text = String(value ?? '')
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function timestampForFilename() {
  const date = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`
}
