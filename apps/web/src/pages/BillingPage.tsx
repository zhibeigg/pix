import { CreditPanel } from '../components/CreditPanel'
import { PageHeader } from '../components/PageHeader'
import type { CreditBalance, CreditPackage, CreditTransaction, PaymentCheckout, PaymentOrder } from '../types'

interface BillingPageProps { balance: CreditBalance | null; transactions: CreditTransaction[]; packages: CreditPackage[]; orders: PaymentOrder[]; checkout: PaymentCheckout | null; isAdmin: boolean; onRefresh: () => void; onCreateOrder: (packageKey: string) => Promise<void>; onCheckout: (packageKey: string, provider: string) => Promise<void>; onMockPayOrder: (orderId: number) => Promise<void> }

export function BillingPage(props: BillingPageProps) {
  return <div className="grid gap-6"><PageHeader eyebrow="点数" title="点数中心" description="充值、订单、流水。" /><CreditPanel {...props} /></div>
}
