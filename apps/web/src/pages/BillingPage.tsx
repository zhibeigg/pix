import { useI18n } from '../i18n'
import { CreditPanel } from '../components/CreditPanel'
import { PageHeader } from '../components/PageHeader'
import type { CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, PaymentCheckout, PaymentOrder } from '../types'

interface BillingPageProps { balance: CreditBalance | null; transactions: CreditTransaction[]; packages: CreditPackage[]; customRechargeOptions: CustomRechargeOptions | null; orders: PaymentOrder[]; checkout: PaymentCheckout | null; isAdmin: boolean; onRefresh: () => void; onCreateOrder: (packageKey: string) => Promise<void>; onCheckout: (packageKey: string, provider: string) => Promise<void>; onCreateCustomOrder: (customCredits: number) => Promise<void>; onCustomCheckout: (customCredits: number, provider: string) => Promise<void>; onMockPayOrder: (orderId: number) => Promise<void> }

export function BillingPage(props: BillingPageProps) {
  const { text } = useI18n()
  return <div className="grid gap-6"><PageHeader eyebrow={text('点数', 'Credits')} title={text('点数中心', 'Billing center')} description={text('充值、订单、流水。', 'Top-ups, orders, and credit history.')} /><CreditPanel {...props} /></div>
}
