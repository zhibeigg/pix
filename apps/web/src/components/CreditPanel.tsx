import { useMemo, useState } from 'react'
import type { CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, PaymentCheckout, PaymentOrder } from '../types'
import { formatDateTime } from '../lib/utils'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixMetric } from './pix/PixMetric'
import { PixPanel } from './pix/PixPanel'

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
  const [customCredits, setCustomCredits] = useState(100)
  const safeCustomCredits = Number.isFinite(customCredits) ? customCredits : 0
  const customAmountCents = useMemo(() => {
    if (!customRechargeOptions) return 0
    return Math.ceil(customRechargeOptions.base_package_amount_cents * safeCustomCredits / customRechargeOptions.base_package_credits)
  }, [safeCustomCredits, customRechargeOptions])
  const customValid = Boolean(customRechargeOptions && safeCustomCredits >= customRechargeOptions.min_credits && safeCustomCredits <= customRechargeOptions.max_credits && Number.isInteger(safeCustomCredits))
  const customCurrency = customRechargeOptions?.currency ?? 'cny'

  return (
    <PixPanel eyebrow="点数中心" title="点数账户" description="选择固定套餐，或输入你需要的自定义点数；实际金额以提交时后端计算为准。" action={<Button variant="outline" onClick={onRefresh}>刷新</Button>}>
      <div className="grid gap-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><PixMetric label="可用" value={balance?.available_credits ?? '—'} /><PixMetric label="冻结" value={balance?.reserved_credits ?? '—'} /><PixMetric label="累计充值" value={balance?.total_recharged ?? '—'} tone="success" /><PixMetric label="累计消费" value={balance?.total_consumed ?? '—'} tone="warning" /></div>

        <section className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-lg font-black">固定套餐</h3><p className="text-sm text-muted-foreground">大额套餐可配置优惠，自定义点数按基准单价计算。</p></div><Badge variant="outline">套餐价优先</Badge></div>
          <div className="grid gap-3 md:grid-cols-3">{packages.map((item, index) => <article key={item.key} className={`rounded-2xl border p-4 ${index === 0 ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}><div className="grid gap-4"><div><div className="flex items-center gap-2"><h4 className="font-black">{item.name}</h4>{index === 0 && <Badge>推荐</Badge>}</div><p className="mt-2 text-3xl font-black">{item.credits}<span className="ml-1 text-sm text-muted-foreground">点</span></p><p className="text-sm text-muted-foreground">{money(item.amount_cents, item.currency)}</p></div><div className="flex flex-wrap gap-2"><Button onClick={() => onCheckout(item.key, 'alipay')}>支付宝支付</Button>{isAdmin && <Button variant="ghost" onClick={() => onCreateOrder(item.key)}>创建模拟订单</Button>}</div></div></article>)}</div>
        </section>

        <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
            <div>
              <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-black">自定义充值数量</h3><Badge variant="secondary">后端计价</Badge></div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">输入想购买的点数，系统按当前基准套餐单价计算金额。支付创建订单时会重新计算，前端金额仅用于预览。</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)] sm:items-center">
                <Input type="number" min={customRechargeOptions?.min_credits ?? 10} max={customRechargeOptions?.max_credits ?? 100000} step={1} value={customCredits} onChange={(event) => setCustomCredits(Number(event.target.value))} />
                <div className="flex flex-wrap gap-2">{(customRechargeOptions?.suggested_credits ?? [50, 100, 200, 500]).map((credits) => <Button key={credits} type="button" variant="outline" size="sm" onClick={() => setCustomCredits(credits)}>{credits} 点</Button>)}</div>
              </div>
              {customRechargeOptions && <p className="mt-3 text-xs text-muted-foreground">允许范围：{customRechargeOptions.min_credits}—{customRechargeOptions.max_credits} 点；基准：{customRechargeOptions.base_package_credits} 点 / {money(customRechargeOptions.base_package_amount_cents, customCurrency)}</p>}
              {!customValid && <p className="mt-3 text-sm text-destructive">请输入允许范围内的整数点数。</p>}
            </div>
            <div className="rounded-2xl border border-border bg-muted/35 p-4">
              <p className="text-xs font-black uppercase tracking-[.12em] text-muted-foreground">预计支付</p>
              <p className="mt-2 text-4xl font-black text-primary">{money(customAmountCents, customCurrency)}</p>
              <p className="mt-1 text-sm text-muted-foreground">{safeCustomCredits} 点</p>
              <div className="mt-4 flex flex-wrap gap-2"><Button disabled={!customValid} onClick={() => onCustomCheckout(safeCustomCredits, 'alipay')}>支付宝支付</Button>{isAdmin && <Button variant="ghost" disabled={!customValid} onClick={() => onCreateCustomOrder(safeCustomCredits)}>创建模拟订单</Button>}</div>
            </div>
          </div>
        </section>

        {checkout?.payment_url && <Alert variant="info">支付宝支付页已打开。支付完成后请回到 Pix 刷新订单状态。</Alert>}
        <section className="grid gap-3"><h3 className="text-lg font-black">充值订单</h3>{orders.length === 0 ? <p className="text-sm text-muted-foreground">暂无充值订单。</p> : orders.map((order) => <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4"><div><p className="font-bold">订单 #{order.id}</p><p className="text-sm text-muted-foreground">{order.credits} 点 · {money(order.amount_cents, order.currency)} · {formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><Badge variant={order.status === 'paid' ? 'success' : 'warning'}>{order.status}</Badge>{isAdmin && order.status !== 'paid' && <Button size="sm" onClick={() => onMockPayOrder(order.id)}>模拟支付</Button>}</div></div>)}</section>
        <section className="grid gap-3"><h3 className="text-lg font-black">点数流水</h3>{transactions.length === 0 ? <p className="text-sm text-muted-foreground">暂无流水。</p> : transactions.map((tx) => <div key={tx.id} className="flex justify-between gap-3 border-b border-border py-3"><div><p className="font-bold">{tx.type}</p><p className="text-sm text-muted-foreground">{tx.note || '—'} · {formatDateTime(tx.created_at)}</p></div><p className={tx.amount >= 0 ? 'font-black text-emerald-600' : 'font-black text-destructive'}>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</p></div>)}</section>
      </div>
    </PixPanel>
  )
}
