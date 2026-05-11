import { Box, Tab, Tabs, Typography } from '@mui/material'
import type { User } from '../types'

export type AppPage = 'workspace' | 'gallery' | 'packs' | 'billing' | 'admin'

const tabs: Array<{ page: AppPage; label: string; description: string; adminOnly?: boolean }> = [
  { page: 'workspace', label: '生产工作台', description: '单图与批量创建' },
  { page: 'gallery', label: '作品库', description: '查看结果与微调' },
  { page: 'packs', label: '素材包', description: '管理批量生产' },
  { page: 'billing', label: '点数中心', description: '充值与流水' },
  { page: 'admin', label: '管理后台', description: '运营与配置', adminOnly: true },
]

interface AppTabsProps {
  page: AppPage
  user: User | null
  onChange: (page: AppPage) => void
}

export function AppTabs({ page, user, onChange }: AppTabsProps) {
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.role === 'admin')
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
      <Tabs value={page} variant="scrollable" scrollButtons="auto" aria-label="主导航" onChange={(_, value: AppPage) => onChange(value)}>
        {visibleTabs.map((tab) => (
          <Tab
            key={tab.page}
            value={tab.page}
            aria-current={page === tab.page ? 'page' : undefined}
            label={(
              <Box sx={{ textAlign: 'left' }}>
                <Typography component="span" variant="button" sx={{ display: 'block', fontWeight: 900 }}>{tab.label}</Typography>
                <Typography component="span" variant="caption" color="text.secondary">{tab.description}</Typography>
              </Box>
            )}
          />
        ))}
      </Tabs>
    </Box>
  )
}
