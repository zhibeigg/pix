import { FormEvent, useState } from 'react'
import type { PricingRule, User } from '../types'

type AdminPanelProps = {
  users: User[]
  pricing: PricingRule[]
  onRefresh: () => void
  onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>
  onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>
}

export function AdminPanel({ users, pricing, onRefresh, onAdjustCredits, onUpdatePricing }: AdminPanelProps) {
  const [selectedUser, setSelectedUser] = useState<number>(0)
  const [amount, setAmount] = useState(100)
  const [note, setNote] = useState('seed credits')

  async function submitAdjust(event: FormEvent) {
    event.preventDefault()
    if (!selectedUser) return
    await onAdjustCredits(selectedUser, amount, note)
  }

  return (
    <section className="panel admin-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>运营控制台</h2>
        </div>
        <button className="ghost" onClick={onRefresh}>刷新</button>
      </div>
      <div className="admin-grid">
        <form className="stack" onSubmit={submitAdjust}>
          <h3>手动加点</h3>
          <label>
            用户
            <select value={selectedUser} onChange={(event) => setSelectedUser(Number(event.target.value))}>
              <option value={0}>选择用户</option>
              {users.map((user) => (
                <option value={user.id} key={user.id}>{user.email} · {user.role}</option>
              ))}
            </select>
          </label>
          <label>
            点数变化
            <input type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
          </label>
          <label>
            备注
            <input value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button>调整点数</button>
        </form>
        <div>
          <h3>价格规则</h3>
          <div className="pricing-list">
            {pricing.map((rule) => (
              <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function PricingRow({ rule, onUpdate }: { rule: PricingRule; onUpdate: (key: string, priceCredits: number, enabled: boolean) => Promise<void> }) {
  const [price, setPrice] = useState(rule.price_credits)
  const [enabled, setEnabled] = useState(rule.enabled)

  return (
    <div className="pricing-row">
      <div>
        <strong>{rule.key}</strong>
        <p>{rule.enabled ? '启用' : '停用'}</p>
      </div>
      <input type="number" min={0} value={price} onChange={(event) => setPrice(Number(event.target.value))} />
      <label className="mini-check">
        <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
        启用
      </label>
      <button className="ghost" onClick={() => onUpdate(rule.key, price, enabled)}>保存</button>
    </div>
  )
}
