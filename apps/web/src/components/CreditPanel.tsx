import { useMemo, useState } from 'react'
import { Download, RotateCcw, Search } from 'lucide-react'
import { useI18n } from '../i18n'
import type { CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, PaymentCheckout, PaymentOrder } from '../types'
import { formatDateTime } from '../lib/utils'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
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
  const { text } = useI18n()
  const [customCredits, setCustomCredits] = useState(100)
  const safeCustomCredits = Number.isFinite(customCredits) ? customCredits : 0
  const customAmountCents = useMemo(() => {
    if (!customRechargeOptions) return 0
    return Math.ceil(customRechargeOptions.base_package_amount_cents * safeCustomCredits / customRechargeOptions.base_package_credits)
  }, [safeCustomCredits, customRechargeOptions])
  const customValid = Boolean(customRechargeOptions && safeCustomCredits >= customRechargeOptions.min_credits && safeCustomCredits <= customRechargeOptions.max_credits && Number.isInteger(safeCustomCredits))
  const customCurrency = customRechargeOptions?.currency ?? 'cny'

  return (
    <PixPanel eyebrow={text('点数中心', 'Billing center')} title={text('点数账户', 'Credit account')} description={text('选择固定套餐，或输入你需要的自定义点数；实际金额以提交时后端计算为准。', 'Choose a package or enter custom credits; the backend calculates the final amount when submitted.')} action={<Button variant="outline" onClick={onRefresh}>{text('刷新', 'Refresh')}</Button>}>
      <div className="grid gap-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><PixMetric label={text('可用', 'Available')} value={balance?.available_credits ?? '—'} /><PixMetric label={text('冻结', 'Reserved')} value={balance?.reserved_credits ?? '—'} /><PixMetric label={text('累计充值', 'Total topped up')} value={balance?.total_recharged ?? '—'} tone="success" /><PixMetric label={text('累计消费', 'Total spent')} value={balance?.total_consumed ?? '—'} tone="warning" /></div>

        <section className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-lg font-semibold">{text('固定套餐', 'Fixed packages')}</h3><p className="text-sm text-muted-foreground">{text('大额套餐可配置优惠，自定义点数按基准单价计算。', 'Large packages can include discounts; custom credits use the base unit price.')}</p></div><Badge variant="outline">{text('套餐价优先', 'Package price first')}</Badge></div>
          <div className="grid gap-3 md:grid-cols-3">{packages.map((item, index) => <article key={item.key} className={`rounded-lg border p-4 ${index === 0 ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}><div className="grid gap-4"><div><div className="flex items-center gap-2"><h4 className="font-semibold">{item.name}</h4>{index === 0 && <Badge>{text('推荐', 'Recommended')}</Badge>}</div><p className="mt-2 text-3xl font-semibold">{item.credits}<span className="ml-1 text-sm text-muted-foreground">{text('点', 'credits')}</span></p><p className="text-sm text-muted-foreground">{money(item.amount_cents, item.currency)}</p></div><div className="flex flex-wrap gap-2"><Button onClick={() => onCheckout(item.key, 'alipay')}>{text('支付宝支付', 'Pay with Alipay')}</Button>{isAdmin && <Button variant="ghost" onClick={() => onCreateOrder(item.key)}>{text('创建模拟订单', 'Create mock order')}</Button>}</div></div></article>)}</div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
            <div>
              <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-semibold">{text('自定义充值数量', 'Custom top-up amount')}</h3><Badge variant="secondary">{text('后端计价', 'Backend priced')}</Badge></div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{text('输入想购买的点数，系统按当前基准套餐单价计算金额。支付创建订单时会重新计算，前端金额仅用于预览。', 'Enter the credits you want. The system estimates from the current base package price; checkout recalculates on the backend.')}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)] sm:items-center">
                <Input type="number" min={customRechargeOptions?.min_credits ?? 10} max={customRechargeOptions?.max_credits ?? 100000} step={1} value={customCredits} onChange={(event) => setCustomCredits(Number(event.target.value))} />
                <div className="flex flex-wrap gap-2">{(customRechargeOptions?.suggested_credits ?? [50, 100, 200, 500]).map((credits) => <Button key={credits} type="button" variant="outline" size="sm" onClick={() => setCustomCredits(credits)}>{text(`${credits} 点`, `${credits} credits`)}</Button>)}</div>
              </div>
              {customRechargeOptions && <p className="mt-3 text-xs text-muted-foreground">{text(`允许范围：${customRechargeOptions.min_credits}—${customRechargeOptions.max_credits} 点；基准：${customRechargeOptions.base_package_credits} 点 / ${money(customRechargeOptions.base_package_amount_cents, customCurrency)}`, `Allowed range: ${customRechargeOptions.min_credits}—${customRechargeOptions.max_credits} credits; base: ${customRechargeOptions.base_package_credits} credits / ${money(customRechargeOptions.base_package_amount_cents, customCurrency)}`)}</p>}
              {!customValid && <p className="mt-3 text-sm text-destructive">{text('请输入允许范围内的整数点数。', 'Enter an integer credit amount within the allowed range.')}</p>}
            </div>
            <div className="rounded-lg border border-border bg-muted/35 p-4">
              <p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('预计支付', 'Estimated payment')}</p>
              <p className="mt-2 text-4xl font-semibold text-primary">{money(customAmountCents, customCurrency)}</p>
              <p className="mt-1 text-sm text-muted-foreground">{text(`${safeCustomCredits} 点`, `${safeCustomCredits} credits`)}</p>
              <div className="mt-4 flex flex-wrap gap-2"><Button disabled={!customValid} onClick={() => onCustomCheckout(safeCustomCredits, 'alipay')}>{text('支付宝支付', 'Pay with Alipay')}</Button>{isAdmin && <Button variant="ghost" disabled={!customValid} onClick={() => onCreateCustomOrder(safeCustomCredits)}>{text('创建模拟订单', 'Create mock order')}</Button>}</div>
            </div>
          </div>
        </section>

        {checkout?.payment_url && <Alert variant="info">{text('支付宝支付页已打开。支付完成后请回到 Pix 刷新订单状态。', 'The Alipay page opened. Return to Pix and refresh order status after payment.')}</Alert>}
        <TopUpOrders orders={orders} isAdmin={isAdmin} onMockPayOrder={onMockPayOrder} />
        <CreditLedgerTable balance={balance} transactions={transactions} onRefresh={onRefresh} />
      </div>
    </PixPanel>
  )
}

function TopUpOrders({ orders, isAdmin, onMockPayOrder }: { orders: PaymentOrder[]; isAdmin: boolean; onMockPayOrder: (orderId: number) => Promise<void> }) {
  const { text } = useI18n()
  return <section className="grid gap-3"><h3 className="text-lg font-semibold">{text('充值订单', 'Top-up orders')}</h3>{orders.length === 0 ? <p className="text-sm text-muted-foreground">{text('暂无充值订单。', 'No top-up orders yet.')}</p> : orders.map((order) => <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-4"><div><p className="font-bold">{text(`订单 #${order.id}`, `Order #${order.id}`)}</p><p className="text-sm text-muted-foreground">{text(`${order.credits} 点`, `${order.credits} credits`)} · {money(order.amount_cents, order.currency)} · {formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><Badge variant={order.status === 'paid' ? 'success' : 'warning'}>{order.status}</Badge>{isAdmin && order.status !== 'paid' && <Button size="sm" onClick={() => onMockPayOrder(order.id)}>{text('模拟支付', 'Mock pay')}</Button>}</div></div>)}</section>
}

function CreditLedgerTable({ balance, transactions, onRefresh }: { balance: CreditBalance | null; transactions: CreditTransaction[]; onRefresh: () => void }) {
  const { text } = useI18n()
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

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card text-foreground shadow-[0_12px_36px_-24px_rgba(15,23,42,.35)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-navy-deep))] dark:text-white dark:shadow-[0_24px_80px_-44px_rgba(0,0,0,.9)]">
      <div className="border-b border-border bg-[hsl(var(--pix-paper-soft))] p-4 dark:border-white/10 dark:bg-transparent">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold tracking-[.14em] text-primary dark:text-[hsl(var(--pix-brand-purple-300))]">{text('点数流水', 'Credit ledger')}</p>
            <h3 className="mt-1 text-xl font-semibold">{text('流水明细', 'Ledger details')}</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <LedgerPill label={text('可用点数', 'Available')} value={balance?.available_credits ?? 0} tone="blue" />
            <LedgerPill label={text('冻结点数', 'Reserved')} value={balance?.reserved_credits ?? 0} tone="slate" />
            <LedgerPill label={text('本页收入', 'Page income')} value={`+${income}`} tone="green" />
            <LedgerPill label={text('本页支出', 'Page spent')} value={`-${spent}`} tone="rose" />
            <LedgerPill label={text('流水', 'Rows')} value={filtered.length} tone="slate" />
          </div>
        </div>

        <div className="mt-4 grid gap-2 lg:grid-cols-[150px_150px_160px_minmax(180px,1fr)_auto]">
          <Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} className="h-9 border-input bg-background text-foreground [color-scheme:light] placeholder:text-muted-foreground dark:border-white/10 dark:bg-white/10 dark:text-white dark:[color-scheme:dark] dark:placeholder:text-white/45" />
          <Input type="date" value={to} onChange={(event) => setTo(event.target.value)} className="h-9 border-input bg-background text-foreground [color-scheme:light] placeholder:text-muted-foreground dark:border-white/10 dark:bg-white/10 dark:text-white dark:[color-scheme:dark] dark:placeholder:text-white/45" />
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as TxFilter)} className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring dark:border-white/10 dark:bg-white/10 dark:text-white dark:focus:ring-[hsl(var(--pix-brand-purple-300))]">
            {TX_TYPES.map((type) => <option key={type} value={type} className="bg-card text-foreground dark:bg-[hsl(var(--pix-navy-deep))] dark:text-white">{txTypeFilterLabel(type, text)}</option>)}
          </select>
          <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground dark:text-white/45" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={text('备注、类型或任务 ID', 'Note, type, or job ID')} className="h-9 border-input bg-background pl-9 text-foreground placeholder:text-muted-foreground dark:border-white/10 dark:bg-white/10 dark:text-white dark:placeholder:text-white/45" /></div>
          <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" onClick={onRefresh}><RotateCcw />{text('查询', 'Search')}</Button><Button type="button" size="sm" variant="ghost" onClick={reset}>{text('重置', 'Reset')}</Button><Button type="button" size="sm" className="bg-sky-600 text-white hover:bg-sky-500 dark:bg-sky-500 dark:hover:bg-sky-400" onClick={() => exportLedgerCsv(filtered, text)}><Download />{text('导出 CSV', 'Export CSV')}</Button></div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-collapse text-sm">
          <thead className="text-left text-xs text-muted-foreground dark:text-white/48">
            <tr className="border-b border-border dark:border-white/10">
              <th className="px-4 py-3 font-semibold">{text('时间', 'Time')}</th>
              <th className="px-4 py-3 font-semibold">{text('类型', 'Type')}</th>
              <th className="px-4 py-3 font-semibold">{text('说明', 'Note')}</th>
              <th className="px-4 py-3 font-semibold">{text('任务', 'Job')}</th>
              <th className="px-4 py-3 text-right font-semibold">{text('变动', 'Amount')}</th>
              <th className="px-4 py-3 text-right font-semibold">{text('余额', 'Balance')}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground dark:text-white/50">{text('没有符合条件的流水。', 'No matching transactions.')}</td></tr> : filtered.map((tx) => <LedgerRow key={tx.id} tx={tx} />)}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function LedgerRow({ tx }: { tx: CreditTransaction }) {
  const { text } = useI18n()
  const group = txTypeGroup(tx.type)
  return (
    <tr className="border-b border-border bg-card transition hover:bg-muted/45 last:border-b-0 dark:border-white/7 dark:bg-white/[.025] dark:hover:bg-white/[.055]">
      <td className="whitespace-nowrap px-4 py-3 text-foreground dark:text-white/82">{formatDateTime(tx.created_at)}</td>
      <td className="px-4 py-3"><TxBadge type={group} raw={tx.type} /></td>
      <td className="max-w-[420px] truncate px-4 py-3 text-muted-foreground dark:text-white/72">{tx.note || text('—', '—')}</td>
      <td className="whitespace-nowrap px-4 py-3 text-muted-foreground dark:text-white/68">{tx.job_id ? `#${tx.job_id}` : '—'}</td>
      <td className={`whitespace-nowrap px-4 py-3 text-right font-semibold ${tx.amount >= 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-600 dark:text-rose-300'}`}>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</td>
      <td className="whitespace-nowrap px-4 py-3 text-right text-foreground dark:text-white/82">{tx.balance_after}</td>
    </tr>
  )
}

function LedgerPill({ label, value, tone }: { label: string; value: string | number; tone: 'blue' | 'green' | 'rose' | 'slate' }) {
  const toneClass = tone === 'blue' ? 'bg-sky-50 text-sky-800 ring-sky-200 dark:bg-sky-400/12 dark:text-sky-100 dark:ring-sky-300/20' : tone === 'green' ? 'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-400/12 dark:text-emerald-100 dark:ring-emerald-300/20' : tone === 'rose' ? 'bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-400/12 dark:text-rose-100 dark:ring-rose-300/20' : 'bg-muted text-muted-foreground ring-border dark:bg-white/10 dark:text-white/80 dark:ring-white/10'
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${toneClass}`}><span className="opacity-65">{label}</span>{value}</span>
}

function TxBadge({ type, raw }: { type: TxFilter; raw: string }) {
  const { text } = useI18n()
  const tone = type === 'recharge' || type === 'refund' ? 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-400/14 dark:text-emerald-100 dark:ring-emerald-300/25' : type === 'consume' ? 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-400/14 dark:text-rose-100 dark:ring-rose-300/25' : type === 'reserve' ? 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-400/14 dark:text-amber-100 dark:ring-amber-300/25' : type === 'adjust' ? 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-400/14 dark:text-sky-100 dark:ring-sky-300/25' : 'bg-muted text-muted-foreground ring-border dark:bg-white/10 dark:text-white/75 dark:ring-white/10'
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${tone}`}>{txTypeLabel(type, raw, text)}</span>
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

function txTypeFilterLabel(type: TxFilter, text: (zh: string, en: string) => string) {
  if (type === 'all') return text('全部类型', 'All types')
  return txTypeLabel(type, type, text)
}

function txTypeLabel(type: TxFilter, raw: string, text: (zh: string, en: string) => string) {
  const labels: Record<TxFilter, string> = {
    all: text('全部', 'All'),
    recharge: text('充值', 'Top-up'),
    reserve: text('冻结', 'Reserve'),
    consume: text('消费', 'Spend'),
    refund: text('退款', 'Refund'),
    adjust: text('调整', 'Adjust'),
    other: raw,
  }
  return labels[type]
}

function exportLedgerCsv(rows: CreditTransaction[], text: (zh: string, en: string) => string) {
  const headers = [text('时间', 'Time'), text('类型', 'Type'), text('说明', 'Note'), text('任务 ID', 'Job ID'), text('变动', 'Amount'), text('余额', 'Balance')]
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
