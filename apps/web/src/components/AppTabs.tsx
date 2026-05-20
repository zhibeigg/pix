import { Box, Stack, Typography } from '@mui/material'
import type { User } from '../types'
import { notionTokens } from '../theme'

export type AppPage = 'workspace' | 'raw-image' | 'gallery' | 'packs' | 'billing' | 'admin'

const tabs: Array<{ page: AppPage; label: string; description: string; adminOnly?: boolean; tint: string }> = [
  { page: 'workspace', label: '生产工作台', description: '单图与批量创建', tint: notionTokens.tintYellowBold },
  { page: 'raw-image', label: '原始生图', description: '仅生成原图', tint: notionTokens.tintCream },
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
      sx={{
        width: '100%',
        gap: { xs: .75, sm: 1 },
        overflowX: 'auto',
        overflowY: 'hidden',
        px: .25,
        py: .25,
        scrollbarWidth: 'thin',
        scrollbarColor: `${notionTokens.hairlineStrong} transparent`,
        scrollSnapType: { xs: 'x proximity', lg: 'none' },
        overscrollBehaviorX: 'contain',
        WebkitOverflowScrolling: 'touch',
        '&::-webkit-scrollbar': { height: 5 },
        '&::-webkit-scrollbar-track': { background: 'transparent' },
        '&::-webkit-scrollbar-thumb': { backgroundColor: notionTokens.hairlineStrong, borderRadius: 999 },
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
              borderColor: active ? notionTokens.brandNavyDeep : notionTokens.hairline,
              borderRadius: '8px',
              bgcolor: active ? notionTokens.brandNavyDeep : notionTokens.canvas,
              color: active ? notionTokens.onDark : notionTokens.ink,
              boxShadow: active ? notionTokens.cardShadow : 'none',
              px: { xs: 1.45, sm: 1.65, lg: 1.35, xl: 1.6 },
              py: { xs: .85, lg: .78 },
              minHeight: { xs: 44, lg: 40 },
              minWidth: { xs: 136, sm: 132, lg: 112, xl: 132 },
              maxWidth: { lg: 160 },
              scrollSnapAlign: 'start',
              cursor: 'pointer',
              textAlign: 'left',
              font: 'inherit',
              whiteSpace: 'nowrap',
              flex: '0 0 auto',
              transition: 'background-color .16s ease, border-color .16s ease, transform .14s ease, box-shadow .16s ease',
              '@media (min-width: 1321px) and (max-width: 1500px)': {
                minWidth: 'auto',
                maxWidth: 132,
                px: 1.25,
              },
              '@media (hover: hover)': {
                '&:hover': { transform: 'translateY(-1px)', bgcolor: active ? notionTokens.brandNavyDeep : notionTokens.surface },
              },
              '@media (prefers-reduced-motion: reduce)': {
                '&, &:hover': { transform: 'none' },
              },
            }}
          >
            <Typography component="span" variant="body2" noWrap sx={{ display: 'block', fontWeight: 600 }}>{tab.label}</Typography>
            <Typography
              component="span"
              variant="caption"
              noWrap
              sx={{
                display: 'block',
                color: active ? notionTokens.onDarkMuted : notionTokens.steel,
                '@media (min-width: 1321px) and (max-width: 1500px)': { display: 'none' },
              }}
            >
              {tab.description}
            </Typography>
          </Box>
        )
      })}
    </Stack>
  )
}
