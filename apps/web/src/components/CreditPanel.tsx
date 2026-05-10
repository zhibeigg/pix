import type { CreditBalance, CreditTransaction } from '../types'

type CreditPanelProps = {
  balance: CreditBalance | null
  transactions: CreditTransaction[]
  onRefresh: () => void
}

export function CreditPanel({ balance, transactions, onRefresh }: CreditPanelProps) {
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
