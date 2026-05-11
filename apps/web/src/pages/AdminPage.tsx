import { AdminPanel } from '../components/AdminPanel'
import type { AdminDashboard, PricingRule, SystemSetting, User } from '../types'

interface AdminPageProps {
  dashboard: AdminDashboard | null
  users: User[]
  pricing: PricingRule[]
  settings: SystemSetting[]
  onRefresh: () => void
  onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>
  onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>
  onUpdateSetting: (key: string, value: string) => Promise<void>
}

export function AdminPage(props: AdminPageProps) {
  return (
    <section className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">Admin</p>
        <h2>管理后台</h2>
        <p>查看运营概览、调整用户点数、配置价格和上线保护策略。</p>
      </header>
      <AdminPanel {...props} />
    </section>
  )
}
