import { AdminPanel } from '../components/AdminPanel'
import { PageHeader } from '../components/PageHeader'
import type { AdminDashboard, CreditPackage, PricingRule, SystemSetting, User } from '../types'

interface AdminPageProps { dashboard: AdminDashboard | null; users: User[]; pricing: PricingRule[]; packages: CreditPackage[]; settings: SystemSetting[]; onRefresh: () => void; onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>; onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>; onCreatePackage: (payload: CreditPackage) => Promise<void>; onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>; onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>; onTestEmail: (email: string) => Promise<void> }

export function AdminPage(props: AdminPageProps) {
  return <div className="grid gap-6"><PageHeader eyebrow="Admin" title="管理后台" description="运营、点数、价格配置。" /><AdminPanel {...props} /></div>
}
