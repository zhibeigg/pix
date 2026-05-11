import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import type { CreditBalance, User } from '../types'
import { notionTokens } from '../theme'

type AppHeroProps = {
  user: User | null
  balance: CreditBalance | null
  activeJobs: number
  completedJobs: number
  failedJobs: number
}

export function AppHero({ user, balance, activeJobs, completedJobs, failedJobs }: AppHeroProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 1.5,
        bgcolor: notionTokens.brandNavy,
        color: notionTokens.onDark,
        px: { xs: 3, md: 8 },
        py: { xs: 5, md: 8 },
        boxShadow: 'rgba(15, 15, 15, 0.20) 0px 24px 48px -8px',
      }}
    >
      <DecorativeDots />
      <Stack spacing={3} sx={{ position: 'relative', alignItems: 'center', textAlign: 'center' }}>
        <Chip label="Pix Forge" sx={{ bgcolor: 'rgba(255,255,255,.12)', color: notionTokens.onDark, borderColor: 'rgba(255,255,255,.24)', borderRadius: 1 }} variant="outlined" />
        <Box sx={{ maxWidth: 840 }}>
          <Typography variant="h1" sx={{ fontSize: { xs: 38, sm: 52, md: 72, xl: 80 }, color: notionTokens.onDark }}>
            像素素材夜班工坊
          </Typography>
          <Typography sx={{ mt: 2, fontSize: { xs: 16, md: 18 }, lineHeight: 1.55, color: notionTokens.onDarkMuted }}>
            单图试想法，批量生产素材包；像 Notion 工作区一样组织任务、点数、素材包和微调流程。
          </Typography>
        </Box>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ justifyContent: 'center' }}>
          <Button variant="contained" color="primary" href={user ? '#/workspace' : undefined}>开始生产</Button>
          <Button variant="outlined" href="#/gallery" sx={{ color: notionTokens.onDark, borderColor: 'rgba(255,255,255,.45)' }}>查看作品库</Button>
        </Stack>
        <WorkspaceMockup user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} />
      </Stack>
    </Box>
  )
}

function DecorativeDots() {
  const dots = [
    { x: '10%', y: '18%', c: notionTokens.tintYellowBold, r: 8, rotate: '-12deg' },
    { x: '17%', y: '68%', c: notionTokens.tintMint, r: 10, rotate: '8deg' },
    { x: '82%', y: '20%', c: notionTokens.tintRose, r: 9, rotate: '14deg' },
    { x: '90%', y: '58%', c: notionTokens.tintSky, r: 12, rotate: '-10deg' },
    { x: '72%', y: '78%', c: notionTokens.tintLavender, r: 8, rotate: '18deg' },
  ]
  return (
    <>
      {dots.map((dot, index) => (
        <Box key={index} sx={{ position: 'absolute', left: dot.x, top: dot.y, width: dot.r * 2, height: dot.r * 2, borderRadius: .75, bgcolor: dot.c, transform: `rotate(${dot.rotate})`, opacity: .95 }} />
      ))}
      <Box sx={{ position: 'absolute', inset: 'auto 8% 8% auto', width: 220, height: 120, border: '1px solid rgba(255,255,255,.18)', borderRadius: '50%', transform: 'rotate(-14deg)' }} />
      <Box sx={{ position: 'absolute', inset: '10% auto auto 5%', width: 180, height: 100, border: '1px solid rgba(255,255,255,.14)', borderRadius: '50%', transform: 'rotate(18deg)' }} />
    </>
  )
}

function WorkspaceMockup({ user, balance, activeJobs, completedJobs, failedJobs }: AppHeroProps) {
  const rows = [
    { label: '可用点数', value: balance?.available_credits ?? '—', tint: notionTokens.tintLavender },
    { label: '队列中', value: activeJobs, tint: notionTokens.tintSky },
    { label: '已完成', value: completedJobs, tint: notionTokens.tintMint },
    { label: '失败', value: failedJobs, tint: notionTokens.tintRose },
  ]
  return (
    <Card sx={{ width: 'min(920px, 100%)', mt: 1, borderRadius: 1.5, boxShadow: 'rgba(15, 15, 15, 0.20) 0px 24px 48px -8px', textAlign: 'left' }}>
      <CardContent sx={{ p: { xs: 2, md: 3 } }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', gap: 1 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Ramp HQ / Pix Board</Typography>
              <Typography variant="h5">{user ? `${user.display_name || user.email} 的工作区` : '登录后开启你的素材看板'}</Typography>
            </Box>
            <Chip label={user?.role ?? 'guest'} sx={{ alignSelf: { xs: 'flex-start', sm: 'center' }, bgcolor: notionTokens.tintCream, borderRadius: 1 }} />
          </Stack>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5 }}>
            {rows.map((row) => (
              <Box key={row.label} sx={{ bgcolor: row.tint, borderRadius: 1.5, p: 2, border: `1px solid ${notionTokens.hairline}` }}>
                <Typography variant="caption" color="text.secondary">{row.label}</Typography>
                <Typography variant="h4">{row.value}</Typography>
              </Box>
            ))}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}
