import { CreditPanel } from '../components/CreditPanel'
import type { CreditBalance, CreditPackage, CreditTransaction, PaymentCheckout, PaymentOrder } from '../types'

interface BillingPageProps {
  balance: CreditBalance | null
  transactions: CreditTransaction[]
  packages: CreditPackage[]
  orders: PaymentOrder[]
  checkout: PaymentCheckout | null
  isAdmin: boolean
  onRefresh: () => void
  onCreateOrder: (packageKey: string) => Promise<void>
  onCheckout: (packageKey: string, provider: string) => Promise<void>
  onMockPayOrder: (orderId: number) => Promise<void>
}

export function BillingPage(props: BillingPageProps) {
  return (
    <section className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">Credits</p>
        <h2>点数中心</h2>
        <p>充值 Credits、查看订单和流水。生成失败会自动退回冻结点数。</p>
      </header>
      <CreditPanel {...props} />
    </section>
  )
}
