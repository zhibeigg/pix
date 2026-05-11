import { Box, Stack, Typography } from '@mui/material'
import type { User } from '../types'
import { notionTokens } from '../theme'

export type AppPage = 'workspace' | 'gallery' | 'packs' | 'billing' | 'admin'

const tabs: Array<{ page: AppPage; label: string; description: string; adminOnly?: boolean; tint: string }> = [
  { page: 'workspace', label: '生产工作台', description: '单图与批量创建', tint: notionTokens.tintYellowBold },
  { page: 'gallery', label: '作品库', description: '查看结果与微调', tint: notionTokens.tintSky },
  { page: 'packs', label: '素材包', description: '管理批量生产', tint: notionTokens.tintMint },
  { page: 'billing', label: '点数中心', description: '充值与流水', tint: notionTokens.tintLavender },
  { page: 'admin', label: '管理后台', description: '运营与配置', adminOnly: true, tint: notionTokens.tintPeach },
]

interface AppTabsProps {
  page: AppPage
  user: User | null
  onChange: (page: AppPage) => void
}

export function AppTabs({ page, user, onChange }: AppTabsProps) {
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.role === 'admin')
  return (
    <Stack
      direction="row"
      spacing={1}
      sx={{
        overflowX: 'auto',
        overflowY: 'hidden',
        pb: 0,
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
        scrollSnapType: { xs: 'x proximity', lg: 'none' },
        '&::-webkit-scrollbar': { display: 'none' },
      }}
      aria-label="主导航"
      role="navigation"
    >
      {visibleTabs.map((tab) => {
        const active = page === tab.page
        return (
          <Box
            component="button"
            type="button"
            key={tab.page}
            aria-current={active ? 'page' : undefined}
            onClick={() => onChange(tab.page)}
            sx={{
              border: 1,
              borderColor: active ? notionTokens.inkDeep : notionTokens.hairline,
              borderRadius: 999,
              bgcolor: active ? notionTokens.inkDeep : notionTokens.canvas,
              color: active ? notionTokens.onDark : notionTokens.ink,
              px: { xs: 1.75, lg: 2 },
              py: .9,
              minHeight: { xs: 44, md: 40 },
              minWidth: { xs: 148, lg: 136, xl: 150 },
              scrollSnapAlign: 'start',
              cursor: 'pointer',
              textAlign: 'left',
              font: 'inherit',
              flex: '0 0 auto',
            }}
          >
            <Typography component="span" variant="body2" sx={{ display: 'block', fontWeight: 600 }}>{tab.label}</Typography>
            <Typography component="span" variant="caption" sx={{ display: 'block', color: active ? notionTokens.onDarkMuted : notionTokens.steel }}>{tab.description}</Typography>
          </Box>
        )
      })}
    </Stack>
  )
}
