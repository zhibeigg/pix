import type { CreditBalance, CreditPackage, CreditTransaction, PaymentCheckout, PaymentOrder } from '../types'
import { formatDateTime } from '../lib/utils'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { PixMetric } from './pix/PixMetric'
import { PixPanel } from './pix/PixPanel'

type Props = { balance: CreditBalance | null; transactions: CreditTransaction[]; packages: CreditPackage[]; orders: PaymentOrder[]; checkout: PaymentCheckout | null; isAdmin: boolean; onRefresh: () => void; onCreateOrder: (packageKey: string) => Promise<void>; onCheckout: (packageKey: string, provider: string) => Promise<void>; onMockPayOrder: (orderId: number) => Promise<void> }

export function CreditPanel({ balance, transactions, packages, orders, checkout, isAdmin, onRefresh, onCreateOrder, onCheckout, onMockPayOrder }: Props) {
  return (
    <PixPanel eyebrow="点数中心" title="点数账户" action={<Button variant="outline" onClick={onRefresh}>刷新</Button>}>
      <div className="grid gap-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><PixMetric label="可用" value={balance?.available_credits ?? '—'} /><PixMetric label="冻结" value={balance?.reserved_credits ?? '—'} /><PixMetric label="累计充值" value={balance?.total_recharged ?? '—'} tone="success" /><PixMetric label="累计消费" value={balance?.total_consumed ?? '—'} tone="warning" /></div>
        <div className="grid gap-3">{packages.map((item, index) => <article key={item.key} className={`rounded-2xl border p-4 ${index === 0 ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}><div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><div className="flex items-center gap-2"><h3 className="font-black">{item.name}</h3>{index === 0 && <Badge>推荐</Badge>}</div><p className="text-sm text-muted-foreground">{item.credits} 点 · ¥{(item.amount_cents / 100).toFixed(2)}</p></div><div className="flex flex-wrap gap-2"><Button onClick={() => onCheckout(item.key, 'alipay')}>支付宝</Button>{isAdmin && <Button variant="ghost" onClick={() => onCreateOrder(item.key)}>模拟订单</Button>}</div></div></article>)}</div>
        {checkout?.payment_url && <Alert variant="info">支付宝已打开，支付后刷新。</Alert>}
        <section className="grid gap-3"><h3 className="text-lg font-black">充值订单</h3>{orders.length === 0 ? <p className="text-sm text-muted-foreground">暂无充值订单。</p> : orders.map((order) => <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4"><div><p className="font-bold">订单 #{order.id}</p><p className="text-sm text-muted-foreground">{order.credits} 点 · ¥{(order.amount_cents / 100).toFixed(2)} · {formatDateTime(order.created_at)}</p></div><div className="flex items-center gap-2"><Badge variant={order.status === 'paid' ? 'success' : 'warning'}>{order.status}</Badge>{isAdmin && order.status !== 'paid' && <Button size="sm" onClick={() => onMockPayOrder(order.id)}>模拟支付</Button>}</div></div>)}</section>
        <section className="grid gap-3"><h3 className="text-lg font-black">点数流水</h3>{transactions.length === 0 ? <p className="text-sm text-muted-foreground">暂无流水。</p> : transactions.map((tx) => <div key={tx.id} className="flex justify-between gap-3 border-b border-border py-3"><div><p className="font-bold">{tx.type}</p><p className="text-sm text-muted-foreground">{tx.note || '—'} · {formatDateTime(tx.created_at)}</p></div><p className={tx.amount >= 0 ? 'font-black text-emerald-600' : 'font-black text-destructive'}>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</p></div>)}</section>
      </div>
    </PixPanel>
  )
}
