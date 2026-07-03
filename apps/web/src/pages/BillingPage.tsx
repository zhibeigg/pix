import { useI18n } from '../i18n'
import { CreditPanel } from '../components/CreditPanel'
import { PageHeader } from '../components/PageHeader'
import type { CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, MembershipPlan, PaymentCheckout, PaymentOrder } from '../types'

interface BillingPageProps { balance: CreditBalance | null; transactions: CreditTransaction[]; packages: CreditPackage[]; membershipPlans: MembershipPlan[]; customRechargeOptions: CustomRechargeOptions | null; orders: PaymentOrder[]; checkout: PaymentCheckout | null; isAdmin: boolean; onRefresh: () => void; onCreateOrder: (packageKey: string) => Promise<void>; onCheckout: (packageKey: string, provider: string) => Promise<void>; onCreateCustomOrder: (customCredits: number) => Promise<void>; onCustomCheckout: (customCredits: number, provider: string) => Promise<void>; onCreateMembershipOrder: (planKey: string) => Promise<void>; onMembershipCheckout: (planKey: string, provider: string) => Promise<void>; onMockPayOrder: (orderId: number) => Promise<void> }

export function BillingPage(props: BillingPageProps) {
  const { t } = useI18n()
  return <div className="grid gap-6"><PageHeader eyebrow={t('pages.billing.eyebrow')} title={t('pages.billing.title')} description={t('pages.billing.description')} /><CreditPanel {...props} /></div>
}
