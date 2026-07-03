import { useMemo, useState, type CSSProperties } from 'react'
import { Copy, Download, ExternalLink, RotateCcw, Search, Users } from 'lucide-react'
import { useI18n } from '../i18n'
import type { CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, MembershipPlan, PaymentCheckout, PaymentOrder } from '../types'
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

const TX_TYPES = ['all', 'recharge', 'reserve', 'quota', 'consume', 'refund', 'adjust', 'other'] as const
type TxFilter = typeof TX_TYPES[number]

type Props = {
  balance: CreditBalance | null
  transactions: CreditTransaction[]
  packages: CreditPackage[]
  membershipPlans: MembershipPlan[]
  customRechargeOptions: CustomRechargeOptions | null
  orders: PaymentOrder[]
  checkout: PaymentCheckout | null
  isAdmin: boolean
  onRefresh: () => void
  onCreateOrder: (packageKey: string) => Promise<void>
  onCheckout: (packageKey: string, provider: string) => Promise<void>
  onCreateCustomOrder: (customCredits: number) => Promise<void>
  onCustomCheckout: (customCredits: number, provider: string) => Promise<void>
  onCreateMembershipOrder: (planKey: string) => Promise<void>
  onMembershipCheckout: (planKey: string, provider: string) => Promise<void>
  onMockPayOrder: (orderId: number) => Promise<void>
}

function money(cents: number, currency = 'cny') {
  const prefix = currency.toLowerCase() === 'cny' ? '¥' : `${currency.toUpperCase()} `
  return `${prefix}${(cents / 100).toFixed(2)}`
}

function membershipNominalValueCents(plan: MembershipPlan) {
  // 永久点数定价：10 点 = ¥1，即 1 点 = 10 分。
  return Math.max(0, plan.daily_quota * Math.max(1, plan.duration_days || 30) * 10)
}

function membershipBreakEvenDays(plan: MembershipPlan) {
  const dailyPermanentValueCents = Math.max(1, plan.daily_quota * 10)
  return Math.max(1, Math.ceil(plan.amount_cents / dailyPermanentValueCents))
}

type MembershipMetal = {
  key: string
  labelClass: string
  frameClass: string
  buttonClass: string
  style: CSSProperties
  glowClass: string
}

function membershipMetal(key: string): MembershipMetal {
  const normalized = key.toLowerCase()
  if (normalized.includes('silver')) {
    return {
      key: 'silver',
      labelClass: 'text-slate-950',
      frameClass: 'border-slate-200/80 text-slate-950',
      buttonClass: 'bg-slate-950 text-white hover:bg-slate-800',
      glowClass: 'bg-white/55',
      style: {
        background: 'radial-gradient(circle at 18% 10%, rgba(255,255,255,.95), transparent 24%), radial-gradient(circle at 78% 2%, rgba(255,255,255,.72), transparent 18%), linear-gradient(135deg, #f8fafc 0%, #cbd5e1 19%, #ffffff 33%, #94a3b8 50%, #e2e8f0 65%, #64748b 82%, #f8fafc 100%)',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,.9), inset 0 -24px 56px rgba(15,23,42,.18), 0 22px 60px -38px rgba(15,23,42,.68)',
      },
    }
  }
  if (normalized.includes('gold')) {
    return {
      key: 'gold',
      labelClass: 'text-amber-950',
      frameClass: 'border-amber-300/80 text-amber-950',
      buttonClass: 'bg-amber-950 text-amber-50 hover:bg-amber-900',
      glowClass: 'bg-yellow-100/45',
      style: {
        background: 'radial-gradient(circle at 20% 8%, rgba(255,255,255,.88), transparent 22%), radial-gradient(circle at 76% 0%, rgba(255,245,157,.85), transparent 20%), linear-gradient(135deg, #fff7cc 0%, #f6c453 16%, #fff0a3 28%, #c18417 45%, #ffdb67 59%, #8b5a0a 79%, #ffe9a6 100%)',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,.8), inset 0 -26px 58px rgba(92,52,3,.24), 0 24px 70px -36px rgba(180,83,9,.72)',
      },
    }
  }
  return {
    key: 'bronze',
    labelClass: 'text-orange-950',
    frameClass: 'border-orange-300/80 text-orange-950',
    buttonClass: 'bg-orange-950 text-orange-50 hover:bg-orange-900',
    glowClass: 'bg-orange-100/40',
    style: {
      background: 'radial-gradient(circle at 18% 8%, rgba(255,238,213,.85), transparent 24%), radial-gradient(circle at 82% 6%, rgba(255,255,255,.48), transparent 17%), linear-gradient(135deg, #f7c28b 0%, #b96d36 17%, #ffd0a3 31%, #8c4a24 48%, #d98a4d 64%, #623015 82%, #f2b879 100%)',
      boxShadow: 'inset 0 1px 0 rgba(255,247,237,.78), inset 0 -26px 58px rgba(67,20,7,.24), 0 24px 70px -38px rgba(154,52,18,.70)',
    },
  }
}

export function CreditPanel({ balance, transactions, packages, membershipPlans, customRechargeOptions, orders, checkout, isAdmin, onRefresh, onCreateOrder, onCheckout, onCreateCustomOrder, onCustomCheckout, onCreateMembershipOrder, onMembershipCheckout, onMockPayOrder }: Props) {
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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6"><PixMetric label={t('billing.account.availableTotal')} value={balance?.available_total ?? balance?.available_credits ?? '—'} /><PixMetric label={t('billing.account.dailyQuota')} value={balance ? `${balance.daily_quota_balance ?? 0}/${balance.daily_quota_limit ?? 0}` : '—'} tone="success" /><PixMetric label={t('billing.account.available')} value={balance?.available_credits ?? '—'} /><PixMetric label={t('billing.account.reserved')} value={balance ? `${balance.reserved_credits}${(balance.reserved_quota ?? 0) > 0 ? ` + ${balance.reserved_quota}临` : ''}` : '—'} /><PixMetric label={t('billing.account.totalRecharged')} value={balance?.total_recharged ?? '—'} tone="success" /><PixMetric label={t('billing.account.totalSpent')} value={balance?.total_consumed ?? '—'} tone="warning" /></div>

        <CommunityCard />

        <section className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-lg font-semibold">{t('membership.title')}</h3><p className="text-sm text-muted-foreground">{t('membership.description')}</p></div><Badge variant="outline">{t('membership.priority')}</Badge></div>
          <div className="grid gap-4 md:grid-cols-3">{membershipPlans.map((plan) => <MembershipCard key={plan.key} plan={plan} active={balance?.membership_plan_key === plan.key} expiresAt={balance?.membership_expires_at ?? null} isAdmin={isAdmin} onCheckout={onMembershipCheckout} onCreateOrder={onCreateMembershipOrder} />)}</div>
        </section>

        <section className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-lg font-semibold">{t('billing.packages.title')}</h3><p className="text-sm text-muted-foreground">{t('billing.packages.description')}</p></div><Badge variant="outline">{t('billing.packages.priority')}</Badge></div>
          <div className="grid gap-3 md:grid-cols-3">{packages.map((item) => { const recommended = item.key === 'pro'; return <article key={item.key} className={`rounded-lg border p-4 ${recommended ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}><div className="grid gap-4"><div><div className="flex items-center gap-2"><h4 className="font-semibold">{item.name}</h4>{recommended && <Badge>{t('common.recommended')}</Badge>}</div><p className="mt-2 text-2xl font-semibold sm:text-3xl">{item.credits}<span className="ml-1 text-sm text-muted-foreground">{t('common.creditUnit')}</span></p><p className="text-sm text-muted-foreground">{money(item.amount_cents, item.currency)}</p></div><div className="flex flex-wrap gap-2"><Button onClick={() => onCheckout(item.key, 'alipay')}>{t('billing.packages.payAlipay')}</Button>{isAdmin && <Button variant="ghost" onClick={() => onCreateOrder(item.key)}>{t('billing.packages.createMockOrder')}</Button>}</div></div></article> })}</div>
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
              <p className="mt-2 text-3xl font-semibold text-primary sm:text-4xl">{money(customAmountCents, customCurrency)}</p>
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

function MembershipCard({ plan, active, expiresAt, isAdmin, onCheckout, onCreateOrder }: { plan: MembershipPlan; active: boolean; expiresAt: string | null; isAdmin: boolean; onCheckout: (planKey: string, provider: string) => Promise<void>; onCreateOrder: (planKey: string) => Promise<void> }) {
  const { t } = useI18n()
  const metal = membershipMetal(plan.key)
  const nominalValue = membershipNominalValueCents(plan)
  const breakEvenDays = membershipBreakEvenDays(plan)
  const profitDays = Math.max(0, plan.duration_days - breakEvenDays)
  const multiplier = Math.max(1, nominalValue / Math.max(1, plan.amount_cents))
  return (
    <article
      className={`group relative isolate overflow-hidden rounded-2xl border p-[1px] transition duration-200 hover:-translate-y-1 hover:shadow-[0_28px_70px_-42px_rgba(15,15,15,.75)] ${metal.frameClass} ${active ? 'ring-2 ring-primary/55' : ''}`}
      style={metal.style}
    >
      <div className="pointer-events-none absolute inset-0 opacity-45 [background-image:repeating-linear-gradient(100deg,rgba(255,255,255,.22)_0px,rgba(255,255,255,.22)_1px,transparent_1px,transparent_7px)]" />
      <div className="pointer-events-none absolute -right-16 -top-20 h-44 w-44 rounded-full bg-white/45 blur-2xl transition duration-300 group-hover:scale-125" />
      <div className="pointer-events-none absolute inset-y-0 left-[-35%] w-1/2 -skew-x-12 bg-white/22 opacity-0 transition duration-500 group-hover:left-[120%] group-hover:opacity-100" />
      <div className="relative grid min-h-[270px] gap-4 rounded-[15px] bg-[linear-gradient(180deg,rgba(255,255,255,.34),rgba(255,255,255,.12))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,.5)] backdrop-saturate-150">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[.18em] opacity-70">{t('membership.metalPass')}</p>
            <div className="mt-1 flex items-center gap-2"><h4 className={`text-xl font-black tracking-tight ${metal.labelClass}`}>{plan.name}</h4>{active && <Badge className="bg-black/70 text-white hover:bg-black/70">{t('membership.active')}</Badge>}</div>
          </div>
          <div className={`rounded-full px-3 py-1 text-xs font-black shadow-[inset_0_1px_0_rgba(255,255,255,.45)] ${metal.glowClass}`}>{t('membership.valueMultiplier', { multiplier: multiplier.toFixed(1) })}</div>
        </div>
        <div>
          <p className="text-[3.2rem] font-black leading-none tracking-[-.08em] drop-shadow-[0_1px_0_rgba(255,255,255,.45)]">{plan.daily_quota}</p>
          <p className="mt-1 text-sm font-bold opacity-75">{t('membership.dailyUnit')}</p>
        </div>
        <div className="grid gap-2 rounded-xl bg-black/10 p-3 text-sm font-bold shadow-[inset_0_1px_8px_rgba(0,0,0,.10)]">
          <div className="flex items-center justify-between gap-2"><span>{t('membership.breakEven')}</span><strong>{t('membership.breakEvenDays', { count: breakEvenDays })}</strong></div>
          <div className="flex items-center justify-between gap-2"><span>{t('membership.monthlyValue')}</span><strong>{money(nominalValue, plan.currency)}</strong></div>
          <div className="rounded-lg bg-white/30 px-3 py-2 text-center text-xs font-black tracking-wide">{t('membership.profitHint', { count: profitDays })}</div>
        </div>
        <div className="mt-auto grid gap-3">
          <p className="text-sm font-bold">{money(plan.amount_cents, plan.currency)} · {t('membership.durationDays', { count: plan.duration_days })}</p>
          {active && expiresAt && <p className="text-xs font-semibold opacity-75">{t('membership.expiresAt', { date: formatDateTime(expiresAt) })}</p>}
          <div className="flex flex-wrap gap-2"><Button className={`shadow-[0_12px_26px_-18px_rgba(0,0,0,.9)] ${metal.buttonClass}`} onClick={() => onCheckout(plan.key, 'alipay')}>{t('membership.buyAlipay')}</Button>{isAdmin && <Button variant="ghost" className="bg-white/25 hover:bg-white/38" onClick={() => onCreateOrder(plan.key)}>{t('billing.packages.createMockOrder')}</Button>}</div>
        </div>
      </div>
    </article>
  )
}

function TopUpOrders({ orders, isAdmin, onMockPayOrder }: { orders: PaymentOrder[]; isAdmin: boolean; onMockPayOrder: (orderId: number) => Promise<void> }) {
  const { t } = useI18n()
  return <section className="grid gap-3"><h3 className="text-lg font-semibold">{t('billing.orders.title')}</h3>{orders.length === 0 ? <p className="text-sm text-muted-foreground">{t('billing.orders.empty')}</p> : orders.map((order) => { const label = order.order_kind === 'membership' ? t('membership.orderLabel', { plan: order.membership_plan_key ?? '' }) : t('common.points', { count: order.credits }); return <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-4"><div><p className="font-bold">{t('billing.orders.order', { id: order.id })}</p><p className="text-sm text-muted-foreground">{label} · {money(order.amount_cents, order.currency)} · {formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><Badge variant={order.status === 'paid' ? 'success' : 'warning'}>{order.status}</Badge>{isAdmin && order.status !== 'paid' && <Button size="sm" onClick={() => onMockPayOrder(order.id)}>{t('billing.orders.mockPay')}</Button>}</div></div> })}</section>
}

function CommunityCard() {
  const { t } = useI18n()
  const qq = t('billing.community.qqNumber')
  const joinUrl = `mqqapi://card/show_pslcard?src_type=internal&version=1&uin=${encodeURIComponent(qq)}&card_type=group&source=external`
  const [copied, setCopied] = useState(false)
  const handleJoin = () => {
    window.location.href = joinUrl
  }
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
          <div className="flex flex-wrap items-baseline gap-2"><h3 className="text-base font-semibold leading-tight">{t('billing.community.title')}</h3><span className="text-xs text-muted-foreground">{t('billing.community.qqLabel')}</span><button type="button" className="font-mono text-lg font-semibold tracking-wide text-primary underline-offset-4 hover:underline" onClick={handleJoin}>{qq}</button></div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{t('billing.community.description')}</p>
        </div>
        <div className="flex flex-wrap gap-2"><Button type="button" size="sm" onClick={handleJoin}><ExternalLink className="h-3.5 w-3.5" />{t('billing.community.join')}</Button><Button type="button" size="sm" variant={copied ? 'secondary' : 'outline'} onClick={handleCopy} aria-live="polite"><Copy className="h-3.5 w-3.5" />{copied ? t('billing.community.copied') : t('billing.community.copy')}</Button></div>
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
      filters={<FilterBar><Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} className={dataInputClass} /><Input type="date" value={to} onChange={(event) => setTo(event.target.value)} className={dataInputClass} /><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as TxFilter)} className={dataSelectClass}>{TX_TYPES.map((type) => <option key={type} value={type} className={dataOptionClass}>{txTypeFilterLabel(type, t)}</option>)}</select><div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--data-text-faint))]" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('billing.ledger.keywordPlaceholder')} className={`${dataInputClass} pl-9`} /></div><div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" onClick={onRefresh}><RotateCcw />{t('common.search')}</Button><Button type="button" size="sm" variant="ghost" onClick={reset}>{t('common.reset')}</Button><Button type="button" size="sm" className="bg-[hsl(var(--pix-link-blue))] text-white hover:bg-[hsl(var(--pix-link-blue-pressed))]" onClick={() => exportLedgerCsv(filtered, t)}><Download />{t('billing.ledger.exportCsv')}</Button></div></FilterBar>}
      columns={columns}
      rows={rows}
      empty={t('billing.ledger.empty')}
    />
  )
}

function txTypeTone(type: TxFilter): DataTone {
  if (type === 'recharge' || type === 'refund') return 'green'
  if (type === 'consume') return 'rose'
  if (type === 'reserve' || type === 'quota') return 'amber'
  if (type === 'adjust') return 'blue'
  return 'slate'
}

function txTypeGroup(type: string): TxFilter {
  const value = type.toLowerCase()
  if (value.includes('recharge') || value.includes('top') || value.includes('membership')) return 'recharge'
  if (value.includes('quota')) return 'quota'
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
