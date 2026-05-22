import { useI18n } from '../i18n'
import { AdminPanel } from '../components/AdminPanel'
import { PageHeader } from '../components/PageHeader'
import type { AdminDashboard, CreditPackage, PricingRule, SystemSetting, User } from '../types'

interface AdminPageProps { dashboard: AdminDashboard | null; users: User[]; pricing: PricingRule[]; packages: CreditPackage[]; settings: SystemSetting[]; onRefresh: () => void; onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>; onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>; onCreatePackage: (payload: CreditPackage) => Promise<void>; onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>; onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>; onTestEmail: (email: string) => Promise<void> }

export function AdminPage(props: AdminPageProps) {
  const { text } = useI18n()
  return <div className="grid gap-6"><PageHeader eyebrow={text('后台', 'Admin')} title={text('管理后台', 'Admin console')} description={text('运营、点数、价格配置。', 'Operations, credits, and pricing configuration.')} /><AdminPanel {...props} /></div>
}
