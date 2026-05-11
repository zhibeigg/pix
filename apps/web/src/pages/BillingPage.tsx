import { Stack } from '@mui/material'
import { CreditPanel } from '../components/CreditPanel'
import { PageHeader } from '../components/PageHeader'
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
    <Stack spacing={3}>
      <PageHeader eyebrow="Credits" title="点数中心" description="充值 Credits、查看订单和流水。生成失败会自动退回冻结点数。" />
      <CreditPanel {...props} />
    </Stack>
  )
}
