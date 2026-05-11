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

const featureCards = [
  { label: '单图生成', body: '从一句描述快速生成可微调的像素图标，适合验证角色、道具和 UI 元素方向。' },
  { label: '批量生产', body: '一次上传多张参考图或多条需求，统一入队、计费、追踪和归档。' },
  { label: 'AI 微调', body: '在作品库中选择结果，继续做本地像素化或图生图微调，保留创作上下文。' },
]

export function AppHero({ user, balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: AppHeroProps) {
  const compact = Boolean(user)
  const stats = [
    { value: activeJobs, label: '队列中', tone: notionTokens.tintSky },
    { value: completedJobs, label: '已完成', tone: notionTokens.tintMint },
    { value: balance?.available_credits ?? '—', label: '可用点数', tone: notionTokens.tintLavender },
  ]

  return (
    <Box
      component="section"
      sx={{
        position: 'relative',
        overflow: 'hidden',
        scrollSnapAlign: compact ? 'none' : 'start',
        minHeight: compact ? 'auto' : { md: 'calc(100vh - 80px)' },
        display: 'flex',
        alignItems: 'center',
        bgcolor: notionTokens.brandNavyDeep,
        color: notionTokens.onDark,
        borderRadius: compact ? 1.5 : 0,
        mx: compact ? 0 : { xs: -2, md: -4 },
        px: compact ? { xs: 3, md: 5 } : { xs: 2, md: 4 },
        py: compact ? { xs: 4, md: 5 } : { xs: 7, md: 9 },
      }}
    >
      <HeroGlow />
      <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1152, mx: 'auto' }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1.08fr .92fr' }, gap: { xs: 5, lg: 7 }, alignItems: 'center' }}>
          <Stack spacing={3.2}>
            <Chip
              label={user ? 'Pix Forge 控制平面' : '面向独立开发者的像素素材生产力基座'}
              sx={{ alignSelf: 'flex-start', bgcolor: 'rgba(255,255,255,.10)', color: notionTokens.onDark, border: '1px solid rgba(255,255,255,.24)', borderRadius: 999 }}
            />
            <Box>
              <Typography variant="h1" sx={{ maxWidth: 760, fontSize: compact ? { xs: 38, md: 56 } : { xs: 42, sm: 58, md: 76 }, color: notionTokens.onDark }}>
                一句 Prompt 批量生成像素素材包
              </Typography>
              <Typography sx={{ mt: 2.5, maxWidth: 640, fontSize: { xs: 16, md: 18 }, lineHeight: 1.65, color: notionTokens.onDarkMuted }}>
                把单图试验、批量生产、作品库微调和点数成本控制收束到一个工作区，让游戏素材从想法到打包下载更稳定。
              </Typography>
            </Box>

            <PipelineCard />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href={user ? '#/workspace' : '#auth-panel'}>开始生产</Button>
              <Button variant="outlined" href={user ? '#/gallery' : '#workflow'} sx={{ color: notionTokens.onDark, borderColor: 'rgba(255,255,255,.45)' }}>查看流程</Button>
            </Stack>

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(3, max-content)' }, gap: 1.5 }}>
              {stats.map((stat) => (
                <Box key={stat.label} sx={{ minWidth: 128, border: '1px dashed rgba(255,255,255,.20)', borderRadius: 2, bgcolor: 'rgba(255,255,255,.06)', px: 2, py: 1.5 }}>
                  <Typography variant="h4" sx={{ color: stat.tone }}>{stat.value}</Typography>
                  <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>{stat.label}</Typography>
                </Box>
              ))}
            </Box>
          </Stack>

          <CapabilityPanel user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={batchCount} />
        </Box>
      </Box>
    </Box>
  )
}

function PipelineCard() {
  return (
    <Card sx={{ maxWidth: 640, bgcolor: 'rgba(255,255,255,.08)', borderColor: 'rgba(255,255,255,.16)', color: notionTokens.onDark, backdropFilter: 'blur(18px)' }}>
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted, letterSpacing: '.08em', textTransform: 'uppercase' }}>输入生产需求即可入队</Typography>
        <Box sx={{ mt: 1.5, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr auto' }, gap: 1.2, alignItems: 'center' }}>
          <Box sx={{ border: '1px solid rgba(255,255,255,.18)', borderRadius: 2, bgcolor: 'rgba(255,255,255,.10)', px: 2, py: 1.4 }}>
            <Typography sx={{ color: notionTokens.onDark }}>RPG 魔法药水图标，一套 12 个，透明背景</Typography>
          </Box>
          <Chip label="批量入队" sx={{ bgcolor: notionTokens.tintYellowBold, color: notionTokens.ink, borderRadius: 999 }} />
        </Box>
      </CardContent>
    </Card>
  )
}

function CapabilityPanel(props: AppHeroProps) {
  return (
    <Box sx={{ position: 'relative' }}>
      <Box sx={{ position: 'absolute', inset: -18, borderRadius: 5, opacity: .5, filter: 'blur(40px)', background: `linear-gradient(135deg, ${notionTokens.primary}, ${notionTokens.brandTeal})` }} />
      <Card sx={{ position: 'relative', borderRadius: 3.5, bgcolor: 'rgba(255,255,255,.10)', borderColor: 'rgba(255,255,255,.18)', color: notionTokens.onDark, backdropFilter: 'blur(20px)', boxShadow: 'rgba(0,0,0,.30) 0 28px 70px -24px' }}>
        <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
          <Stack spacing={2.2}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2, alignItems: 'flex-start' }}>
              <Box>
                <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>Pix Board</Typography>
                <Typography variant="h5" sx={{ color: notionTokens.onDark }}>{props.user ? `${props.user.display_name || props.user.email} 的素材控制台` : '像素素材生产线'}</Typography>
              </Box>
              <Chip label={props.user?.role ?? 'guest'} sx={{ bgcolor: notionTokens.tintCream, borderRadius: 1, color: notionTokens.ink }} />
            </Stack>

            {featureCards.map((item, index) => (
              <Box key={item.label} sx={{ border: '1px solid rgba(255,255,255,.16)', borderRadius: 2.5, bgcolor: 'rgba(255,255,255,.08)', p: 2, transition: 'transform .2s ease, background .2s ease', '&:hover': { transform: 'translateY(-3px)', bgcolor: 'rgba(255,255,255,.12)' } }}>
                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'flex-start' }}>
                  <Box sx={{ width: 36, height: 36, borderRadius: 1.5, display: 'grid', placeItems: 'center', bgcolor: index === 0 ? notionTokens.tintYellowBold : index === 1 ? notionTokens.tintMint : notionTokens.tintLavender, color: notionTokens.ink, fontWeight: 700 }}>0{index + 1}</Box>
                  <Box>
                    <Typography sx={{ fontWeight: 600, color: notionTokens.onDark }}>{item.label}</Typography>
                    <Typography variant="body2" sx={{ mt: .4, color: notionTokens.onDarkMuted }}>{item.body}</Typography>
                  </Box>
                </Stack>
              </Box>
            ))}

            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
              <MiniMetric label="素材包" value={props.batchCount ?? 0} />
              <MiniMetric label="失败" value={props.failedJobs} />
              <MiniMetric label="点数" value={props.balance?.available_credits ?? '—'} />
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}

function MiniMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <Box sx={{ borderRadius: 2, p: 1.4, bgcolor: 'rgba(255,255,255,.08)', border: '1px solid rgba(255,255,255,.14)' }}>
      <Typography sx={{ color: notionTokens.onDark, fontWeight: 600 }}>{value}</Typography>
      <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>{label}</Typography>
    </Box>
  )
}

function HeroGlow() {
  return (
    <>
      <Box sx={{ position: 'absolute', width: 440, height: 440, borderRadius: '50%', top: -180, left: -160, background: 'rgba(108,71,255,.28)', filter: 'blur(70px)' }} />
      <Box sx={{ position: 'absolute', width: 380, height: 380, borderRadius: '50%', right: -120, bottom: -120, background: 'rgba(24,169,153,.24)', filter: 'blur(70px)' }} />
      <Box sx={{ position: 'absolute', inset: 0, opacity: .12, backgroundImage: 'linear-gradient(rgba(255,255,255,.16) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.16) 1px, transparent 1px)', backgroundSize: '44px 44px' }} />
    </>
  )
}
