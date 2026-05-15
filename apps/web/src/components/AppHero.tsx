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

type ShowcaseItem = {
  name: string
  tint: string
  status: string
  src: string
  prompt: string
  brief: string
  variants: Array<{ label: string; src: string }>
}

const showcaseItems: ShowcaseItem[] = [
  { name: '月蚀铃', tint: notionTokens.tintSky, status: '全流程', src: '/hero-icons/pipeline/mooneclipse-bell.png', prompt: '月蚀铃，银蓝小铃铛，中间嵌一枚弯月，适合背包材料图标，透明背景，16×16 像素风，深色描边', brief: '暗夜祭司掉落物，轮廓用月弧和铃身区分。', variants: [{ label: '源图', src: '/hero-icons/pipeline/mooneclipse-bell-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/mooneclipse-bell-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/mooneclipse-bell-preview.png' }] },
  { name: '苍火鳞', tint: notionTokens.tintMint, status: '全流程', src: '/hero-icons/pipeline/blueflame-scale.png', prompt: '苍火鳞，青蓝火焰鳞片，边缘有冷焰高光，RPG 怪物素材，透明背景，清晰像素块', brief: '用斜切鳞片和冷色火线突出“苍火”。', variants: [{ label: '源图', src: '/hero-icons/pipeline/blueflame-scale-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/blueflame-scale-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/blueflame-scale-preview.png' }] },
  { name: '星盐瓶', tint: notionTokens.tintLavender, status: '全流程', src: '/hero-icons/pipeline/star-salt-bottle.png', prompt: '星盐瓶，玻璃小瓶装着发光星盐，紫色瓶塞，炼金材料图标，透明 PNG，16 位 RPG 风格', brief: '瓶颈、晶盐和紫塞在低尺寸下仍能读出。', variants: [{ label: '源图', src: '/hero-icons/pipeline/star-salt-bottle-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/star-salt-bottle-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/star-salt-bottle-preview.png' }] },
  { name: '铜芽齿轮', tint: notionTokens.tintPeach, status: '全流程', src: '/hero-icons/pipeline/copper-sprout-gear.png', prompt: '铜芽齿轮，旧铜齿轮上长出绿色嫩芽，机关植物材料，透明背景，像素图标，硬边描边', brief: '齿轮圆形负责识别，嫩芽提供奇幻转折。', variants: [{ label: '源图', src: '/hero-icons/pipeline/copper-sprout-gear-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/copper-sprout-gear-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/copper-sprout-gear-preview.png' }] },
  { name: '夜萤孢子', tint: notionTokens.tintMint, status: '全流程', src: '/hero-icons/pipeline/nightglow-spore.png', prompt: '夜萤孢子，发光蘑菇孢囊，绿色荧光点，地下洞穴采集物，透明背景，像素游戏物品', brief: '蘑菇剪影配荧光点，适合洞穴素材包。', variants: [{ label: '源图', src: '/hero-icons/pipeline/nightglow-spore-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/nightglow-spore-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/nightglow-spore-preview.png' }] },
  { name: '琥珀龙泪', tint: notionTokens.tintYellow, status: '全流程', src: '/hero-icons/pipeline/amber-dragon-tear.png', prompt: '琥珀龙泪，橙金泪滴宝石，内部有红色火芯，传奇材料，透明背景，像素风 RPG 图标', brief: '泪滴轮廓和火芯让稀有度一眼可见。', variants: [{ label: '源图', src: '/hero-icons/pipeline/amber-dragon-tear-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/amber-dragon-tear-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/amber-dragon-tear-preview.png' }] },
  { name: '雾海罗盘', tint: notionTokens.tintSky, status: '全流程', src: '/hero-icons/pipeline/mistsea-compass.png', prompt: '雾海罗盘，蓝绿色圆形罗盘，金色指针，航海探索道具，透明背景，清晰像素边缘', brief: '圆盘与指针组成强识别度的探索道具。', variants: [{ label: '源图', src: '/hero-icons/pipeline/mistsea-compass-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/mistsea-compass-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/mistsea-compass-preview.png' }] },
  { name: '霜纹护符', tint: notionTokens.tintSky, status: '全流程', src: '/hero-icons/pipeline/frostmark-amulet.png', prompt: '霜纹护符，冰蓝六角护符，中心雪纹，防御装备材料，透明背景，16×16 可读', brief: '六角外形减少小尺寸误读。', variants: [{ label: '源图', src: '/hero-icons/pipeline/frostmark-amulet-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/frostmark-amulet-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/frostmark-amulet-preview.png' }] },
  { name: '裂雷结晶', tint: notionTokens.tintYellow, status: '全流程', src: '/hero-icons/pipeline/thunderrift-crystal.png', prompt: '裂雷结晶，黄色闪电水晶，紫色裂痕，法术强化材料，透明背景，深色描边，像素图标', brief: '亮黄主体和紫裂纹形成高对比。', variants: [{ label: '源图', src: '/hero-icons/pipeline/thunderrift-crystal-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/thunderrift-crystal-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/thunderrift-crystal-preview.png' }] },
  { name: '玄铁羽', tint: notionTokens.tintGray, status: '全流程', src: '/hero-icons/pipeline/blackiron-feather.png', prompt: '玄铁羽，黑铁质感羽毛，边缘有赤色锻痕，锻造材料，透明背景，像素游戏资产', brief: '羽毛斜线让轻薄形态更明确。', variants: [{ label: '源图', src: '/hero-icons/pipeline/blackiron-feather-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/blackiron-feather-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/blackiron-feather-preview.png' }] },
  { name: '朱砂符钉', tint: notionTokens.tintRose, status: '全流程', src: '/hero-icons/pipeline/cinnabar-rune-nail.png', prompt: '朱砂符钉，红色咒钉缠金色符线，封印道具，透明背景，硬边像素风，适合物品栏', brief: '红钉与符线让“封印”属性直接显现。', variants: [{ label: '源图', src: '/hero-icons/pipeline/cinnabar-rune-nail-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/cinnabar-rune-nail-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/cinnabar-rune-nail-preview.png' }] },
  { name: '青藤心核', tint: notionTokens.tintMint, status: '全流程', src: '/hero-icons/pipeline/vineheart-core.png', prompt: '青藤心核，绿色圆形生命核心，被藤蔓缠绕，德鲁伊材料，透明背景，清晰像素块', brief: '圆核心与藤蔓分叉展示生命系属性。', variants: [{ label: '源图', src: '/hero-icons/pipeline/vineheart-core-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/vineheart-core-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/vineheart-core-preview.png' }] },
]

const workflowStats = [
  { value: '12', label: '真实全流程样本', tone: notionTokens.brandOrange },
  { value: '76', label: '题材范例可追溯', tone: notionTokens.brandTeal },
  { value: 'Grid', label: '工程化验收', tone: notionTokens.brandPink },
]

const scaleSamples = showcaseItems.slice(0, 3).map((item) => ({
  name: item.name,
  note: item.brief,
  tint: item.tint,
  sizes: [
    { label: '源图', src: item.variants[0].src },
    { label: 'Grid', src: item.variants[1].src },
    { label: '预览', src: item.variants[2].src },
  ],
}))

const spriteShowcase = {
  name: '月刃骑士挥剑',
  status: '9 帧',
  prompt: '月刃骑士挥剑三段斩，银蓝盔甲小角色，侧身站姿，连续挥剑动作，适合 RPG 战斗序列帧，透明背景，像素动画精灵',
  brief: 'Pix sprite 全流程输出：3×3 生图 → 9 帧切分 → 共享调色板像素化 → 横向精灵图 + GIF。',
  source: '/hero-sprites/pipeline/moonblade-knight-source.png',
  sheet: '/hero-sprites/pipeline/moonblade-knight-sheet.png',
  gif: '/hero-sprites/pipeline/moonblade-knight.gif',
  frameSize: 64,
  displaySize: 88,
  frameCount: 9,
  durationMs: 120,
  frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/moonblade-knight-frame-${String(index + 1).padStart(2, '0')}.png`),
}

const checkerboardSx = {
  backgroundColor: notionTokens.canvas,
  backgroundImage: `linear-gradient(45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(-45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%), linear-gradient(-45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%)`,
  backgroundSize: '16px 16px',
  backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0',
}

export function AppHero({ user, balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: AppHeroProps) {
  const signedIn = Boolean(user)

  return (
    <Box
      component="section"
      sx={{
        position: 'relative',
        overflow: 'visible',
        scrollSnapAlign: signedIn ? 'none' : 'start',
        minHeight: signedIn ? 'auto' : { md: 'calc(100vh - 64px)' },
        display: 'flex',
        alignItems: 'center',
        bgcolor: notionTokens.brandNavyDeep,
        color: notionTokens.onDark,
        mx: signedIn ? 0 : { xs: -2, md: -4 },
        px: signedIn ? { xs: 2.25, md: 3 } : { xs: 2, md: 4 },
        py: signedIn ? { xs: 3.5, md: 4.5 } : { xs: 6.5, md: 8 },
        borderRadius: signedIn ? 2 : 0,
      }}
    >
      <PixelAtmosphere />
      <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1180, mx: 'auto' }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.96fr 1.04fr' }, gap: { xs: 4, lg: 6 }, alignItems: 'center' }}>
          <Stack spacing={3}>
            <Chip
              label={signedIn ? '今日工位 / 继续生产' : 'Pix Forge / 可交付像素资产'}
              sx={{ alignSelf: 'flex-start', bgcolor: 'oklch(25% .04 258)', color: notionTokens.onDark, border: '1px solid oklch(46% .035 258)', borderRadius: 1 }}
            />
            <Box>
              <Typography variant="h1" sx={{ maxWidth: 760, fontSize: signedIn ? { xs: 34, md: 50 } : { xs: 40, sm: 56, md: 74 }, color: notionTokens.onDark }}>
                把一批想法锻成可进游戏的像素资产
              </Typography>
              <Typography sx={{ mt: 2.4, maxWidth: 650, fontSize: { xs: 16, md: 18 }, lineHeight: 1.7, color: notionTokens.onDarkMuted }}>
                从中文素材名开始，生成源图、Pixel Grid、透明 PNG、动画帧与素材包 ZIP；失败项可单独重试，点数消耗全程可见。
              </Typography>
            </Box>

            <ProductionBrief />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.4}>
              <Button variant="contained" color="primary" href={signedIn ? '#/workspace' : '#auth-panel'}>开始生产素材包</Button>
              <Button variant="outlined" href={signedIn ? '#/packs' : '#examples'} sx={{ color: notionTokens.onDark, borderColor: 'oklch(62% .034 258)', bgcolor: 'oklch(18% .03 258)', '&:hover': { borderColor: 'oklch(76% .035 82)', bgcolor: 'oklch(22% .034 258)' } }}>{signedIn ? '查看素材包' : '查看 76 套题材'}</Button>
            </Stack>

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' }, gap: 1.1, maxWidth: 620 }}>
              {(signedIn ? [
                { value: activeJobs, label: '队列中', tone: notionTokens.brandTeal },
                { value: failedJobs, label: '失败待处理', tone: notionTokens.brandPink },
                { value: balance?.available_credits ?? '—', label: '可用点数', tone: notionTokens.brandOrange },
              ] : workflowStats).map((stat) => (
                <Box key={stat.label} sx={{ border: '1px solid oklch(44% .033 258)', borderRadius: 1.5, bgcolor: 'oklch(18% .03 258 / .76)', px: 1.7, py: 1.35 }}>
                  <Typography variant="h5" sx={{ color: stat.tone, fontVariantNumeric: 'tabular-nums' }}>{stat.value}</Typography>
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
    { label: '失败待处理', value: failedJobs, tint: failedJobs ? notionTokens.tintRose : notionTokens.tintGray, action: failedJobs ? '建议先重试。' : '队列健康。' },
    { label: '素材包', value: batchCount, tint: notionTokens.tintYellow, action: '可重试和下载。' },
  ]

  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent sx={{ p: { xs: 2.3, md: 2.8 } }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2.5} sx={{ alignItems: { xs: 'stretch', md: 'center' }, justifyContent: 'space-between' }}>
          <Box sx={{ maxWidth: 430 }}>
            <Typography variant="overline" color="text.secondary">今日工位</Typography>
            <Typography variant="h4">继续生产和导出</Typography>
            <Typography color="text.secondary" sx={{ mt: .75 }}>作品优先，队列次之；先处理失败项，再下载成功素材。</Typography>
          </Box>
          <Box sx={{ flex: 1, display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(5, 1fr)' }, gap: 1 }}>
            {items.map((item) => (
              <Box key={item.label} sx={{ bgcolor: item.tint, borderRadius: 1.5, border: `1px solid ${notionTokens.hairline}`, p: 1.35, minWidth: 0 }}>
                <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                <Typography variant="h5" sx={{ fontVariantNumeric: 'tabular-nums' }}>{item.value}</Typography>
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
    <Card sx={{ maxWidth: 660, bgcolor: 'oklch(22% .034 258)', borderColor: 'oklch(46% .036 258)', color: notionTokens.onDark }}>
      <CardContent sx={{ p: { xs: 2, md: 2.35 } }}>
        <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted, letterSpacing: '.08em', textTransform: 'uppercase' }}>一张任务单</Typography>
        <Box sx={{ mt: 1.4, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr auto' }, gap: 1.2, alignItems: 'center' }}>
          <Box sx={{ border: '1px solid oklch(46% .036 258)', borderRadius: 1, bgcolor: 'oklch(16% .028 258)', px: 1.6, py: 1.25 }}>
            <Typography sx={{ color: notionTokens.onDark }}>月蚀铃、苍火鳞、星盐瓶……生图、VL 分析、像素化与 Grid 验收串成同一条流水线。</Typography>
          </Box>
          <Chip label="批量 / 可追溯" sx={{ bgcolor: notionTokens.tintYellow, color: notionTokens.ink, borderRadius: 1 }} />
        </Box>
      </CardContent>
    </Card>
  )
}

function PixelBatchBoard({ user, balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: AppHeroProps) {
  return (
    <Card sx={{ bgcolor: notionTokens.surface, borderRadius: 2, boxShadow: notionTokens.mockupShadow, overflow: 'visible' }}>
      <CardContent sx={{ p: { xs: 1.7, md: 2.2 } }}>
        <Stack spacing={1.8}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">素材包验收台</Typography>
              <Typography variant="h5">{user ? `${user.display_name || user.email} 的进度` : 'RPG Starter Pack'}</Typography>
            </Box>
            <Chip label={user?.role ?? 'demo'} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800, borderRadius: 1 }} />
          </Stack>

          <Box sx={{ position: 'relative', overflow: 'visible', display: 'grid', gridTemplateColumns: { xs: 'repeat(3, 1fr)', sm: 'repeat(4, 1fr)' }, gap: 1 }}>
            {showcaseItems.map((tile) => <PixelTile key={tile.name} tile={tile} />)}
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: .85 }}>
            <BoardMetric label="完成" value={user ? completedJobs : 17} />
            <BoardMetric label="失败" value={user ? failedJobs : 3} />
            <BoardMetric label="素材包" value={batchCount} />
            <BoardMetric label="点数" value={balance?.available_credits ?? '—'} />
          </Box>

          <ScaleBench />
          <SpritePreviewBench />

          <Box sx={{ border: `1px solid ${notionTokens.hairline}`, bgcolor: notionTokens.canvas, borderRadius: 1.5, p: 1.35 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' } }}>
              <Box>
                <Typography sx={{ fontWeight: 600 }}>成功素材先导出</Typography>
                <Typography variant="body2" color="text.secondary">失败项留在队列里单独重试。</Typography>
              </Box>
              <Chip label={activeJobs ? '生产中' : 'ZIP 就绪'} sx={{ bgcolor: activeJobs ? notionTokens.tintSky : notionTokens.tintMint, borderRadius: 1 }} />
            </Stack>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}

function ScaleBench() {
  return (
    <Box sx={{ border: `1px solid ${notionTokens.hairline}`, borderRadius: 1.5, bgcolor: notionTokens.canvas, p: 1.2 }}>
      <Stack spacing={1}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">多图验收台</Typography>
            <Typography sx={{ fontWeight: 600, lineHeight: 1.15 }}>源图 / Grid / 预览同屏</Typography>
          </Box>
          <Chip size="small" label="focus" sx={{ bgcolor: notionTokens.tintYellow, color: notionTokens.ink, borderRadius: 1 }} />
        </Stack>

        <Stack spacing={.75}>
          {scaleSamples.map((sample) => (
            <Box key={sample.name} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'minmax(92px, .88fr) 1.45fr' }, gap: .9, alignItems: 'center', bgcolor: sample.tint, borderRadius: 1, border: `1px solid ${notionTokens.hairline}`, p: .85 }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }} noWrap>{sample.name}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.25 }}>{sample.note}</Typography>
              </Box>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: .65 }}>
                {sample.sizes.map((size) => <ScaleCell key={size.label} size={size} />)}
              </Box>
            </Box>
          ))}
        </Stack>
      </Stack>
    </Box>
  )
}

function ScaleCell({ size }: { size: typeof scaleSamples[number]['sizes'][number] }) {
  return (
    <Box sx={{ minWidth: 0, display: 'grid', placeItems: 'center', gap: .35, bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, py: .65, px: .45 }}>
      <Box component="img" src={size.src} alt={`${size.label} 版本`} width={48} height={48} loading="eager" decoding="async" sx={{ width: 40, height: 40, objectFit: 'contain', imageRendering: 'pixelated' }} />
      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>{size.label}</Typography>
    </Box>
  )
}

function PixelTile({ tile }: { tile: ShowcaseItem }) {
  return (
    <Box
      tabIndex={0}
      sx={{
        position: 'relative',
        bgcolor: tile.tint,
        borderRadius: 1.5,
        border: `1px solid ${notionTokens.hairline}`,
        p: .9,
        minWidth: 0,
        outline: 'none',
        isolation: 'isolate',
        transition: 'transform 220ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1), border-color 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        '&:hover, &:focus-visible, &:focus-within': {
          transform: 'translateY(-4px) scale(1.025)',
          boxShadow: notionTokens.liftShadow,
          borderColor: notionTokens.hairlineStrong,
          zIndex: 8,
        },
        '&:hover .pixel-tile-detail, &:focus-visible .pixel-tile-detail, &:focus-within .pixel-tile-detail': {
          opacity: 1,
          transform: { xs: 'translate(-50%, 8px) scale(1)', sm: 'translate(-50%, 10px) scale(1)' },
          pointerEvents: 'auto',
        },
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
          '&:hover, &:focus-visible, &:focus-within': { transform: 'none' },
          '& .pixel-tile-detail': { transition: 'none' },
        },
      }}
    >
      <Box sx={{ ...checkerboardSx, display: 'grid', placeItems: 'center', minHeight: 68, borderRadius: 1 }}>
        <Box component="img" src={tile.src} alt={`${tile.name} 64×64 像素素材`} width={64} height={64} loading="eager" decoding="async" sx={{ width: 62, height: 62, objectFit: 'contain', imageRendering: 'pixelated' }} />
      </Box>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: .7, mt: .75 }}>
        <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }} noWrap>{tile.name}</Typography>
        <Chip size="small" label={tile.status} sx={{ height: 20, borderRadius: .75, bgcolor: notionTokens.canvas, color: notionTokens.ink, '& .MuiChip-label': { px: .7, fontSize: 11 } }} />
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>中文 prompt</Typography>
      <PixelTileDetail tile={tile} />
    </Box>
  )
}

function PixelTileDetail({ tile }: { tile: ShowcaseItem }) {
  return (
    <Box
      className="pixel-tile-detail"
      aria-hidden="true"
      sx={{
        position: 'absolute',
        left: '50%',
        top: '100%',
        width: { xs: 252, sm: 292 },
        p: 1.2,
        borderRadius: 1.5,
        border: `1px solid ${notionTokens.hairlineStrong}`,
        bgcolor: notionTokens.canvas,
        color: notionTokens.ink,
        boxShadow: notionTokens.mockupShadow,
        opacity: 0,
        transform: { xs: 'translate(-50%, -4px) scale(.96)', sm: 'translate(-50%, -2px) scale(.96)' },
        transformOrigin: '50% 0',
        pointerEvents: 'none',
        transition: 'opacity 180ms cubic-bezier(0.22, 1, 0.36, 1), transform 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        zIndex: 20,
      }}
    >
      <Stack spacing={1}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 600, lineHeight: 1.1 }} noWrap>{tile.name}</Typography>
            <Typography variant="caption" color="text.secondary">Pix 全流程 / 16×16 / Grid</Typography>
          </Box>
          <Box component="img" src={tile.src} alt="" width={40} height={40} loading="eager" decoding="async" sx={{ width: 40, height: 40, imageRendering: 'pixelated', objectFit: 'contain' }} />
        </Stack>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: .65 }}>
          {tile.variants.map((variant) => (
            <Box key={variant.label} sx={{ minWidth: 0, bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .6, display: 'grid', placeItems: 'center', gap: .35 }}>
              <Box component="img" src={variant.src} alt={`${tile.name} ${variant.label}`} width={48} height={48} loading="lazy" decoding="async" sx={{ width: 46, height: 46, objectFit: 'contain', imageRendering: 'pixelated' }} />
              <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>{variant.label}</Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ bgcolor: tile.tint, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .85 }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: .35 }}>中文 Prompt</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.45 }}>{tile.prompt}</Typography>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.45 }}>{tile.brief}</Typography>
      </Stack>
    </Box>
  )
}

function SpritePreviewBench() {
  const displaySize = spriteShowcase.displaySize
  const sheetDisplayWidth = spriteShowcase.frameCount * displaySize
  const sheetTravel = (spriteShowcase.frameCount - 1) * displaySize

  return (
    <Box
      tabIndex={0}
      sx={{
        position: 'relative',
        overflow: 'visible',
        border: `1px solid ${notionTokens.hairlineStrong}`,
        borderRadius: 1.5,
        bgcolor: notionTokens.tintLavender,
        p: 1.15,
        outline: 'none',
        transition: 'transform 220ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1), border-color 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        '@keyframes spriteFrameRun': {
          to: { backgroundPosition: `-${sheetTravel}px 0` },
        },
        '&:hover, &:focus-visible, &:focus-within': {
          transform: 'translateY(-3px)',
          boxShadow: notionTokens.liftShadow,
          borderColor: notionTokens.primary,
          zIndex: 10,
        },
        '&:hover .sprite-frame-player, &:focus-visible .sprite-frame-player, &:focus-within .sprite-frame-player': {
          animation: `spriteFrameRun ${spriteShowcase.frameCount * spriteShowcase.durationMs}ms steps(${spriteShowcase.frameCount - 1}, end) infinite`,
        },
        '&:hover .sprite-detail, &:focus-visible .sprite-detail, &:focus-within .sprite-detail': {
          opacity: 1,
          transform: 'translate(-50%, 10px) scale(1)',
          pointerEvents: 'auto',
        },
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
          '&, &:hover, &:focus-visible, &:focus-within': { transform: 'none' },
          '& .sprite-frame-player': { animation: 'none !important' },
          '& .sprite-detail': { transition: 'none' },
        },
      }}
    >
      <Stack direction="row" spacing={1.2} sx={{ alignItems: 'center' }}>
        <Box sx={{ display: 'grid', placeItems: 'center', width: displaySize + 16, height: displaySize + 16, borderRadius: 1.5, bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}` }}>
          <Box
            className="sprite-frame-player"
            role="img"
            aria-label={`${spriteShowcase.name} 序列帧播放预览`}
            sx={{
              width: displaySize,
              height: displaySize,
              backgroundImage: `url(${spriteShowcase.sheet})`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: '0 0',
              backgroundSize: `${sheetDisplayWidth}px ${displaySize}px`,
              imageRendering: 'pixelated',
            }}
          />
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Typography variant="caption" color="text.secondary">序列帧预览</Typography>
            <Chip size="small" label={spriteShowcase.status} sx={{ height: 20, borderRadius: .75, bgcolor: notionTokens.canvas, color: notionTokens.ink, '& .MuiChip-label': { px: .75, fontSize: 11 } }} />
          </Stack>
          <Typography sx={{ fontWeight: 600, lineHeight: 1.2 }} noWrap>{spriteShowcase.name}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.35 }}>悬浮播放 9 帧，展开查看横向精灵图。</Typography>
        </Box>
      </Stack>
      <SpritePreviewDetail />
    </Box>
  )
}

function SpritePreviewDetail() {
  return (
    <Box
      className="sprite-detail"
      aria-hidden="true"
      sx={{
        position: 'absolute',
        left: '50%',
        top: '100%',
        width: { xs: 286, sm: 360 },
        p: 1.2,
        borderRadius: 1.5,
        border: `1px solid ${notionTokens.hairlineStrong}`,
        bgcolor: notionTokens.canvas,
        color: notionTokens.ink,
        boxShadow: notionTokens.mockupShadow,
        opacity: 0,
        transform: 'translate(-50%, -2px) scale(.96)',
        transformOrigin: '50% 0',
        pointerEvents: 'none',
        transition: 'opacity 180ms cubic-bezier(0.22, 1, 0.36, 1), transform 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        zIndex: 30,
      }}
    >
      <Stack spacing={1}>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 600, lineHeight: 1.1 }} noWrap>{spriteShowcase.name}</Typography>
            <Typography variant="caption" color="text.secondary">Pix sprite / 3×3 / 9 帧</Typography>
          </Box>
          <Box component="img" src={spriteShowcase.gif} alt="" width={48} height={48} loading="lazy" decoding="async" sx={{ width: 48, height: 48, objectFit: 'contain', imageRendering: 'pixelated' }} />
        </Stack>

        <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .75 }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: .45 }}>横向精灵图</Typography>
          <Box component="img" src={spriteShowcase.sheet} alt={`${spriteShowcase.name} 横向精灵图`} width={576} height={64} loading="lazy" decoding="async" sx={{ width: '100%', height: 52, objectFit: 'contain', imageRendering: 'pixelated', display: 'block' }} />
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(9, minmax(0, 1fr))', gap: .35 }}>
          {spriteShowcase.frames.map((frame, index) => (
            <Box key={frame} component="img" src={frame} alt={`${spriteShowcase.name} 第 ${index + 1} 帧`} width={64} height={64} loading="lazy" decoding="async" sx={{ width: '100%', aspectRatio: '1', objectFit: 'contain', imageRendering: 'pixelated', bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: .5 }} />
          ))}
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: .65 }}>
          <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .6, display: 'grid', placeItems: 'center', gap: .35 }}>
            <Box component="img" src={spriteShowcase.source} alt={`${spriteShowcase.name} 3×3 源图`} width={96} height={96} loading="lazy" decoding="async" sx={{ width: 72, height: 72, objectFit: 'contain' }} />
            <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>3×3 源图</Typography>
          </Box>
          <Box sx={{ bgcolor: notionTokens.tintLavender, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .75 }}>
            <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: .35 }}>中文 Prompt</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.4 }}>{spriteShowcase.prompt}</Typography>
          </Box>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.45 }}>{spriteShowcase.brief}</Typography>
      </Stack>
    </Box>
  )
}

function BoardMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <Box sx={{ borderRadius: 1, p: 1.05, bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}` }}>
      <Typography sx={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{value}</Typography>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Box>
  )
}

function PixelAtmosphere() {
  return (
    <>
      <Box sx={{ position: 'absolute', inset: 0, opacity: .12, backgroundImage: 'linear-gradient(oklch(92% .018 82 / .16) 1px, transparent 1px), linear-gradient(90deg, oklch(92% .018 82 / .16) 1px, transparent 1px)', backgroundSize: '32px 32px' }} />
      <Box sx={{ position: 'absolute', width: 18, height: 18, left: '9%', top: '18%', bgcolor: 'oklch(72% .07 86)', boxShadow: '32px 18px 0 oklch(68% .045 164), 68px -8px 0 oklch(70% .045 292)', opacity: .62 }} />
      <Box sx={{ position: 'absolute', width: 16, height: 16, right: '12%', bottom: '16%', bgcolor: 'oklch(66% .055 352)', boxShadow: '-28px -22px 0 oklch(66% .045 235), -72px 8px 0 oklch(71% .052 54)', opacity: .54 }} />
    </>
  )
}
