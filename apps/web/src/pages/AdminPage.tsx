import { Stack } from '@mui/material'
import { AdminPanel } from '../components/AdminPanel'
import { PageHeader } from '../components/PageHeader'
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
    <Stack spacing={3}>
      <PageHeader eyebrow="Admin" title="管理后台" description="运营、点数、价格配置。" tint="cream" />
      <AdminPanel {...props} />
    </Stack>
  )
}
