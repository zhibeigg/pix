import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import type { CreditBalance, User } from '../types'
import { notionTokens } from '../theme'

type AppHeroProps = {
  user: User | null
  balance: CreditBalance | null
  activeJobs: number
  completedJobs: number
  failedJobs: number
  batchCount?: number
}

const pixelTiles = [
  { name: '血气灵玉', tint: notionTokens.tintRose, status: '完成', src: '/hero-icons/blood-jade.png' },
  { name: '紫髓铁', tint: notionTokens.tintLavender, status: '完成', src: '/hero-icons/violet-iron.png' },
  { name: '幽光菇', tint: notionTokens.tintMint, status: '微调', src: '/hero-icons/ghost-mushroom.png' },
  { name: '古木枝', tint: notionTokens.tintCream, status: '完成', src: '/hero-icons/ancient-branch.png' },
  { name: '冰霜徽章', tint: notionTokens.tintSky, status: '完成', src: '/hero-icons/frost-badge.png' },
  { name: '熔火碎片', tint: notionTokens.tintPeach, status: '完成', src: '/hero-icons/ember-shard.png' },
  { name: '藤蔓药剂', tint: notionTokens.tintMint, status: '完成', src: '/hero-icons/vine-potion.png' },
  { name: '失败项', tint: notionTokens.tintGray, status: '待重试', src: '/hero-icons/retry-cross.png' },
  { name: '月银矿', tint: notionTokens.tintSky, status: '完成', src: '/hero-icons/moon-silver.png' },
  { name: '雷纹符石', tint: notionTokens.tintYellowBold, status: '完成', src: '/hero-icons/thunder-rune.png' },
  { name: '毒囊', tint: notionTokens.tintRose, status: '完成', src: '/hero-icons/poison-sac.png' },
  { name: '空瓶', tint: notionTokens.tintCream, status: '排队', src: '/hero-icons/empty-bottle.png' },
]

const workflowStats = [
  { value: '12', label: 'RPG 道具', tone: notionTokens.tintYellowBold },
  { value: '17/20', label: '可先导出', tone: notionTokens.tintMint },
  { value: '3', label: '失败重试', tone: notionTokens.tintRose },
]

export function AppHero({ user, balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: AppHeroProps) {
  const signedIn = Boolean(user)

  return (
    <Box
      component="section"
      sx={{
        position: 'relative',
        overflow: 'hidden',
        scrollSnapAlign: signedIn ? 'none' : 'start',
        minHeight: signedIn ? 'auto' : { md: 'calc(100vh - 80px)' },
        display: 'flex',
        alignItems: 'center',
        bgcolor: notionTokens.brandNavyDeep,
        color: notionTokens.onDark,
        mx: signedIn ? 0 : { xs: -2, md: -4 },
        px: signedIn ? { xs: 2.5, md: 4 } : { xs: 2, md: 4 },
        py: signedIn ? { xs: 4, md: 5 } : { xs: 7, md: 9 },
        borderRadius: signedIn ? 1.5 : 0,
      }}
    >
      <PixelAtmosphere />
      <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1152, mx: 'auto' }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1.02fr .98fr' }, gap: { xs: 5, lg: 7 }, alignItems: 'center' }}>
          <Stack spacing={3.2}>
            <Chip
              label={signedIn ? '今日工位' : '像素素材工坊'}
              sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.tintYellowBold, color: notionTokens.ink, borderRadius: 1 }}
            />
            <Box>
              <Typography variant="h1" sx={{ maxWidth: 760, fontSize: signedIn ? { xs: 36, md: 52 } : { xs: 42, sm: 58, md: 76 }, color: notionTokens.onDark }}>
                把一批游戏素材生产到可交付状态
              </Typography>
              <Typography sx={{ mt: 2.5, maxWidth: 650, fontSize: { xs: 16, md: 18 }, lineHeight: 1.65, color: notionTokens.onDarkMuted }}>
                批量生成、挑选、微调、重试和下载，都在一个工位里完成。
              </Typography>
            </Box>

            <ProductionBrief />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href={signedIn ? '#/workspace' : '#auth-panel'}>开始生产</Button>
              <Button variant="outlined" href={signedIn ? '#/packs' : '#workflow'} sx={{ color: notionTokens.onDark, borderColor: 'rgba(255,255,255,.45)' }}>查看流程</Button>
            </Stack>

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, max-content)' }, gap: 1.5 }}>
              {(signedIn ? [
                { value: activeJobs, label: '队列中', tone: notionTokens.tintSky },
                { value: failedJobs, label: '失败待处理', tone: notionTokens.tintRose },
                { value: balance?.available_credits ?? '—', label: '可用点数', tone: notionTokens.tintLavender },
              ] : workflowStats).map((stat) => (
                <Box key={stat.label} sx={{ minWidth: 132, border: '1px solid rgba(255,255,255,.22)', borderRadius: 1.5, bgcolor: 'rgba(11,18,48,.72)', px: 2, py: 1.5 }}>
                  <Typography variant="h4" sx={{ color: stat.tone }}>{stat.value}</Typography>
                  <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>{stat.label}</Typography>
                </Box>
              ))}
            </Box>
          </Stack>

          <PixelBatchBoard user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={batchCount} />
        </Box>
      </Box>
    </Box>
  )
}

export function DashboardSummary({ balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: Omit<AppHeroProps, 'user'>) {
  const items = [
    { label: '可用点数', value: balance?.available_credits ?? '—', tint: notionTokens.tintLavender, action: '入队冻结，失败退回。' },
    { label: '队列中', value: activeJobs, tint: notionTokens.tintSky, action: activeJobs ? '生产中。' : '可开始新素材包。' },
    { label: '已完成', value: completedJobs, tint: notionTokens.tintMint, action: '可微调或复制路径。' },
    { label: '素材包', value: batchCount, tint: notionTokens.tintYellow, action: '可重试和下载。' },
  ]

  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2.5} sx={{ alignItems: { xs: 'stretch', md: 'center' }, justifyContent: 'space-between' }}>
          <Box sx={{ maxWidth: 420 }}>
            <Typography variant="overline" color="text.secondary">今日工位</Typography>
            <Typography variant="h4">继续生产和导出</Typography>
            <Typography color="text.secondary" sx={{ mt: .75 }}>先处理失败项，再下载成功素材。</Typography>
          </Box>
          <Box sx={{ flex: 1, display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 1.25 }}>
            {items.map((item) => (
              <Box key={item.label} sx={{ bgcolor: item.tint, borderRadius: 1.5, border: `1px solid ${notionTokens.hairline}`, p: 1.5, minWidth: 0 }}>
                <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                <Typography variant="h5">{item.value}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', xl: 'block' } }}>{item.action}</Typography>
              </Box>
            ))}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}

function ProductionBrief() {
  return (
    <Card sx={{ maxWidth: 660, bgcolor: notionTokens.tintCream, borderColor: 'rgba(255,255,255,.20)', color: notionTokens.ink }}>
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: '.06em', textTransform: 'uppercase' }}>示例</Typography>
        <Box sx={{ mt: 1.5, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr auto' }, gap: 1.2, alignItems: 'center' }}>
          <Box sx={{ border: `1px solid ${notionTokens.hairlineStrong}`, borderRadius: 1.5, bgcolor: notionTokens.canvas, px: 2, py: 1.4 }}>
            <Typography>12 个 RPG 药水图标，透明背景</Typography>
          </Box>
          <Chip label="生成包" sx={{ bgcolor: notionTokens.inkDeep, color: notionTokens.onDark, borderRadius: 1 }} />
        </Box>
      </CardContent>
    </Card>
  )
}

function PixelBatchBoard({ user, balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: AppHeroProps) {
  return (
    <Card sx={{ bgcolor: notionTokens.surfaceSoft, borderRadius: 2.5, boxShadow: 'rgba(0,0,0,.32) 0 28px 70px -28px' }}>
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={2}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">素材包看板</Typography>
              <Typography variant="h5">{user ? `${user.display_name || user.email} 的进度` : 'RPG Starter Pack'}</Typography>
            </Box>
            <Chip label={user?.role ?? 'demo'} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800, borderRadius: 1 }} />
          </Stack>

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(3, 1fr)', sm: 'repeat(4, 1fr)' }, gap: 1.2 }}>
            {pixelTiles.map((tile) => <PixelTile key={tile.name} tile={tile} />)}
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1 }}>
            <BoardMetric label="完成" value={user ? completedJobs : 17} />
            <BoardMetric label="失败" value={user ? failedJobs : 3} />
            <BoardMetric label="素材包" value={batchCount} />
            <BoardMetric label="点数" value={balance?.available_credits ?? '—'} />
          </Box>

          <Box sx={{ border: `1px solid ${notionTokens.hairline}`, bgcolor: notionTokens.canvas, borderRadius: 1.5, p: 1.5 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' } }}>
              <Box>
                <Typography sx={{ fontWeight: 600 }}>成功素材可先导出</Typography>
                <Typography variant="body2" color="text.secondary">失败项单独重试。</Typography>
              </Box>
              <Chip label={activeJobs ? '生产中' : 'ZIP 就绪'} sx={{ bgcolor: activeJobs ? notionTokens.tintSky : notionTokens.tintMint, borderRadius: 1 }} />
            </Stack>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}

function PixelTile({ tile }: { tile: typeof pixelTiles[number] }) {
  return (
    <Box sx={{ bgcolor: tile.tint, borderRadius: 1.4, border: `1px solid ${notionTokens.hairline}`, p: 1, minWidth: 0 }}>
      <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 72, backgroundColor: notionTokens.canvas, backgroundImage: `linear-gradient(45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(-45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%), linear-gradient(-45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%)`, backgroundSize: '16px 16px', backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0', borderRadius: 1 }}>
        <Box component="img" src={tile.src} alt={`${tile.name} 64×64 像素素材`} width={64} height={64} loading="eager" decoding="async" sx={{ width: 64, height: 64, objectFit: 'contain', imageRendering: 'pixelated' }} />
      </Box>
      <Typography variant="caption" sx={{ display: 'block', mt: .8, fontWeight: 600 }} noWrap>{tile.name}</Typography>
      <Typography variant="caption" color="text.secondary">{tile.status}</Typography>
    </Box>
  )
}


function BoardMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <Box sx={{ borderRadius: 1.4, p: 1.2, bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}` }}>
      <Typography sx={{ fontWeight: 600 }}>{value}</Typography>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Box>
  )
}

function PixelAtmosphere() {
  return (
    <>
      <Box sx={{ position: 'absolute', inset: 0, opacity: .16, backgroundImage: 'linear-gradient(rgba(255,255,255,.18) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.18) 1px, transparent 1px)', backgroundSize: '32px 32px' }} />
      <Box sx={{ position: 'absolute', width: 22, height: 22, left: '10%', top: '20%', bgcolor: notionTokens.tintYellowBold, boxShadow: `34px 20px 0 ${notionTokens.tintMint}, 70px -10px 0 ${notionTokens.tintLavender}` }} />
      <Box sx={{ position: 'absolute', width: 18, height: 18, right: '12%', bottom: '16%', bgcolor: notionTokens.tintRose, boxShadow: `-28px -24px 0 ${notionTokens.tintSky}, -74px 8px 0 ${notionTokens.tintPeach}` }} />
    </>
  )
}
