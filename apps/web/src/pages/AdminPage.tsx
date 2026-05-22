import { useI18n } from '../i18n'
import { AdminPanel } from '../components/AdminPanel'
import { PageHeader } from '../components/PageHeader'
import type { AdminDashboard, CreditPackage, PricingRule, SystemSetting, User } from '../types'

interface AdminPageProps { dashboard: AdminDashboard | null; users: User[]; pricing: PricingRule[]; packages: CreditPackage[]; settings: SystemSetting[]; onRefresh: () => void; onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>; onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>; onCreatePackage: (payload: CreditPackage) => Promise<void>; onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>; onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>; onTestEmail: (email: string) => Promise<void> }

export function AdminPage(props: AdminPageProps) {
  const { t } = useI18n()
  return <div className="grid gap-6"><PageHeader eyebrow={t('pages.admin.eyebrow')} title={t('pages.admin.title')} description={t('pages.admin.description')} /><AdminPanel {...props} /></div>
}
