import { useMemo, useState } from 'react'
import { useI18n } from '../i18n'
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
        <section className="grid gap-3"><h3 className="text-lg font-semibold">{text('充值订单', 'Top-up orders')}</h3>{orders.length === 0 ? <p className="text-sm text-muted-foreground">{text('暂无充值订单。', 'No top-up orders yet.')}</p> : orders.map((order) => <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-4"><div><p className="font-bold">{text(`订单 #${order.id}`, `Order #${order.id}`)}</p><p className="text-sm text-muted-foreground">{text(`${order.credits} 点`, `${order.credits} credits`)} · {money(order.amount_cents, order.currency)} · {formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><Badge variant={order.status === 'paid' ? 'success' : 'warning'}>{order.status}</Badge>{isAdmin && order.status !== 'paid' && <Button size="sm" onClick={() => onMockPayOrder(order.id)}>{text('模拟支付', 'Mock pay')}</Button>}</div></div>)}</section>
        <section className="grid gap-3"><h3 className="text-lg font-semibold">{text('点数流水', 'Credit history')}</h3>{transactions.length === 0 ? <p className="text-sm text-muted-foreground">{text('暂无流水。', 'No transactions yet.')}</p> : transactions.map((tx) => <div key={tx.id} className="flex justify-between gap-3 border-b border-border py-3"><div><p className="font-bold">{tx.type}</p><p className="text-sm text-muted-foreground">{tx.note || '—'} · {formatDateTime(tx.created_at)}</p></div><p className={tx.amount >= 0 ? 'font-semibold text-emerald-600' : 'font-semibold text-destructive'}>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</p></div>)}</section>
      </div>
    </PixPanel>
  )
}
