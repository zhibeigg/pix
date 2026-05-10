import type { CreditBalance, CreditPackage, CreditTransaction, PaymentOrder } from '../types'

type CreditPanelProps = {
  balance: CreditBalance | null
  transactions: CreditTransaction[]
  packages: CreditPackage[]
  orders: PaymentOrder[]
  isAdmin: boolean
  onRefresh: () => void
  onCreateOrder: (packageKey: string) => Promise<void>
  onMockPayOrder: (orderId: number) => Promise<void>
}

export function CreditPanel({ balance, transactions, packages, orders, isAdmin, onRefresh, onCreateOrder, onMockPayOrder }: CreditPanelProps) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Credits</p>
          <h2>点数账户</h2>
        </div>
        <button className="ghost" onClick={onRefresh}>刷新</button>
      </div>
      <div className="metric-grid">
        <Metric label="可用" value={balance?.available_credits ?? '—'} />
        <Metric label="冻结" value={balance?.reserved_credits ?? '—'} />
        <Metric label="累计充值" value={balance?.total_recharged ?? '—'} />
        <Metric label="累计消费" value={balance?.total_consumed ?? '—'} />
      </div>
      <div className="package-list">
        {packages.map((item) => (
          <div className="transaction" key={item.key}>
            <span className="dot positive" />
            <div>
              <strong>{item.name}</strong>
              <p>{item.credits} credits · {(item.amount_cents / 100).toFixed(2)} {item.currency.toUpperCase()}</p>
            </div>
            <button className="ghost" onClick={() => onCreateOrder(item.key)}>创建订单</button>
          </div>
        ))}
      </div>
      <div className="transaction-list">
        {orders.length > 0 && orders.map((order) => (
          <div className="transaction" key={order.id}>
            <span className={`dot ${order.status === 'paid' ? 'positive' : 'negative'}`} />
            <div>
              <strong>订单 #{order.id} · {order.status}</strong>
              <p>{order.credits} credits · {(order.amount_cents / 100).toFixed(2)} {order.currency.toUpperCase()}</p>
            </div>
            {isAdmin && order.status !== 'paid' && <button className="ghost" onClick={() => onMockPayOrder(order.id)}>模拟支付</button>}
          </div>
        ))}
      </div>
      <div className="transaction-list">
        {transactions.length === 0 ? (
          <p className="muted">暂无流水。管理员可先给账户加点。</p>
        ) : (
          transactions.map((tx) => (
            <div className="transaction" key={tx.id}>
              <span className={`dot ${tx.amount >= 0 ? 'positive' : 'negative'}`} />
              <div>
                <strong>{tx.type}</strong>
                <p>{tx.note || '—'}</p>
              </div>
              <b>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</b>
            </div>
          ))
        )}
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
