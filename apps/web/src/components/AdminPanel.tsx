import { FormEvent, useState } from 'react'
import type { AdminDashboard, PricingRule, SystemSetting, User } from '../types'

type AdminPanelProps = {
  dashboard: AdminDashboard | null
  users: User[]
  pricing: PricingRule[]
  settings: SystemSetting[]
  onRefresh: () => void
  onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>
  onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>
  onUpdateSetting: (key: string, value: string) => Promise<void>
}

type AdminTab = 'dashboard' | 'users' | 'pricing' | 'settings'

export function AdminPanel({ dashboard, users, pricing, settings, onRefresh, onAdjustCredits, onUpdatePricing, onUpdateSetting }: AdminPanelProps) {
  const [tab, setTab] = useState<AdminTab>('dashboard')
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
      <div className="admin-tabs" role="tablist" aria-label="管理后台栏目">
        <button type="button" role="tab" aria-selected={tab === 'dashboard'} className={tab === 'dashboard' ? 'active' : ''} onClick={() => setTab('dashboard')}>概览</button>
        <button type="button" role="tab" aria-selected={tab === 'users'} className={tab === 'users' ? 'active' : ''} onClick={() => setTab('users')}>用户与点数</button>
        <button type="button" role="tab" aria-selected={tab === 'pricing'} className={tab === 'pricing' ? 'active' : ''} onClick={() => setTab('pricing')}>价格规则</button>
        <button type="button" role="tab" aria-selected={tab === 'settings'} className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>运营保护</button>
      </div>

      {tab === 'dashboard' && dashboard && (
        <div className="metric-grid">
          <Metric label="今日任务" value={dashboard.jobs_today} />
          <Metric label="成功 / 失败" value={`${dashboard.succeeded_today} / ${dashboard.failed_today}`} />
          <Metric label="排队 / 运行" value={`${dashboard.pending_jobs} / ${dashboard.running_jobs}`} />
          <Metric label="今日充值" value={dashboard.credits_recharged_today} />
          <Metric label="今日消费" value={dashboard.credits_consumed_today} />
          <Metric label="今日上传" value={dashboard.uploads_today} />
          <Metric label="总用户" value={dashboard.total_users} />
          <Metric label="失败率" value={`${Math.round(dashboard.failure_rate * 100)}%`} />
        </div>
      )}

      {tab === 'users' && (
        <form className="stack admin-section" onSubmit={submitAdjust}>
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
      )}

      {tab === 'pricing' && (
        <div className="admin-section">
          <h3>价格规则</h3>
          <div className="pricing-list">
            {pricing.map((rule) => (
              <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />
            ))}
          </div>
        </div>
      )}

      {tab === 'settings' && (
        <div className="admin-section">
          <h3>运营保护</h3>
          <div className="pricing-list">
            {settings.map((setting) => (
              <SettingRow setting={setting} onUpdate={onUpdateSetting} key={setting.key} />
            ))}
          </div>
        </div>
      )}
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

function SettingRow({ setting, onUpdate }: { setting: SystemSetting; onUpdate: (key: string, value: string) => Promise<void> }) {
  const [value, setValue] = useState(setting.value)
  const isBoolean = setting.key === 'generation_enabled'
  const isTextArea = setting.key === 'blocked_prompt_terms'

  return (
    <div className="pricing-row">
      <div>
        <strong>{settingLabel(setting.key)}</strong>
        <p>{setting.key}</p>
      </div>
      {isBoolean ? (
        <label className="mini-check">
          <input type="checkbox" checked={value === 'true'} onChange={(event) => setValue(event.target.checked ? 'true' : 'false')} />
          启用
        </label>
      ) : isTextArea ? (
        <textarea rows={3} value={value} onChange={(event) => setValue(event.target.value)} placeholder="每行或逗号分隔一个禁词" />
      ) : (
        <input type="number" min={0} value={value} onChange={(event) => setValue(event.target.value)} />
      )}
      <button className="ghost" onClick={() => onUpdate(setting.key, value)}>保存</button>
    </div>
  )
}

function settingLabel(key: string) {
  const labels: Record<string, string> = {
    generation_enabled: '生成总开关',
    max_pending_jobs_per_user: '每用户排队/运行上限',
    daily_job_limit_per_user: '每用户每日任务上限',
    blocked_prompt_terms: 'Prompt 禁词',
    max_uploads_per_user_per_day: '每用户每日上传上限',
  }
  return labels[key] ?? key
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
