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

const showcaseItems = [
  { name: '月蚀铃', tint: notionTokens.tintSky, status: '全流程', src: '/hero-icons/pipeline/mooneclipse-bell.png', prompt: '月蚀铃，银蓝小铃铛，中间嵌一枚弯月，适合背包材料图标，透明背景，16×16 像素风，深色描边', brief: '暗夜祭司掉落物，轮廓用月弧和铃身区分。', variants: [{ label: '源图', src: '/hero-icons/pipeline/mooneclipse-bell-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/mooneclipse-bell-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/mooneclipse-bell-preview.png' }] },
  { name: '苍火鳞', tint: notionTokens.tintMint, status: '全流程', src: '/hero-icons/pipeline/blueflame-scale.png', prompt: '苍火鳞，青蓝火焰鳞片，边缘有冷焰高光，RPG 怪物素材，透明背景，清晰像素块', brief: '用斜切鳞片和冷色火线突出“苍火”。', variants: [{ label: '源图', src: '/hero-icons/pipeline/blueflame-scale-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/blueflame-scale-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/blueflame-scale-preview.png' }] },
  { name: '星盐瓶', tint: notionTokens.tintLavender, status: '全流程', src: '/hero-icons/pipeline/star-salt-bottle.png', prompt: '星盐瓶，玻璃小瓶装着发光星盐，紫色瓶塞，炼金材料图标，透明 PNG，16 位 RPG 风格', brief: '瓶颈、晶盐和紫塞在低尺寸下仍能读出。', variants: [{ label: '源图', src: '/hero-icons/pipeline/star-salt-bottle-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/star-salt-bottle-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/star-salt-bottle-preview.png' }] },
  { name: '铜芽齿轮', tint: notionTokens.tintPeach, status: '全流程', src: '/hero-icons/pipeline/copper-sprout-gear.png', prompt: '铜芽齿轮，旧铜齿轮上长出绿色嫩芽，机关植物材料，透明背景，像素图标，硬边描边', brief: '齿轮圆形负责识别，嫩芽提供奇幻转折。', variants: [{ label: '源图', src: '/hero-icons/pipeline/copper-sprout-gear-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/copper-sprout-gear-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/copper-sprout-gear-preview.png' }] },
  { name: '夜萤孢子', tint: notionTokens.tintMint, status: '全流程', src: '/hero-icons/pipeline/nightglow-spore.png', prompt: '夜萤孢子，发光蘑菇孢囊，绿色荧光点，地下洞穴采集物，透明背景，像素游戏物品', brief: '蘑菇剪影配荧光点，适合洞穴素材包。', variants: [{ label: '源图', src: '/hero-icons/pipeline/nightglow-spore-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/nightglow-spore-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/nightglow-spore-preview.png' }] },
  { name: '琥珀龙泪', tint: notionTokens.tintYellow, status: '全流程', src: '/hero-icons/pipeline/amber-dragon-tear.png', prompt: '琥珀龙泪，橙金泪滴宝石，内部有红色火芯，传奇材料，透明背景，像素风 RPG 图标', brief: '泪滴轮廓和火芯让稀有度一眼可见。', variants: [{ label: '源图', src: '/hero-icons/pipeline/amber-dragon-tear-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/amber-dragon-tear-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/amber-dragon-tear-preview.png' }] },
  { name: '雾海罗盘', tint: notionTokens.tintSky, status: '全流程', src: '/hero-icons/pipeline/mistsea-compass.png', prompt: '雾海罗盘，蓝绿色圆形罗盘，金色指针，航海探索道具，透明背景，清晰像素边缘', brief: '圆盘与指针组成强识别度的探索道具。', variants: [{ label: '源图', src: '/hero-icons/pipeline/mistsea-compass-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/mistsea-compass-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/mistsea-compass-preview.png' }] },
  { name: '霜纹护符', tint: notionTokens.tintSky, status: '全流程', src: '/hero-icons/pipeline/frostmark-amulet.png', prompt: '霜纹护符，冰蓝六角护符，中心雪纹，防御装备材料，透明背景，16×16 可读', brief: '六角外形减少小尺寸误读。', variants: [{ label: '源图', src: '/hero-icons/pipeline/frostmark-amulet-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/frostmark-amulet-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/frostmark-amulet-preview.png' }] },
  { name: '裂雷结晶', tint: notionTokens.tintYellowBold, status: '全流程', src: '/hero-icons/pipeline/thunderrift-crystal.png', prompt: '裂雷结晶，黄色闪电水晶，紫色裂痕，法术强化材料，透明背景，深色描边，像素图标', brief: '亮黄主体和紫裂纹形成高对比。', variants: [{ label: '源图', src: '/hero-icons/pipeline/thunderrift-crystal-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/thunderrift-crystal-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/thunderrift-crystal-preview.png' }] },
  { name: '玄铁羽', tint: notionTokens.tintGray, status: '全流程', src: '/hero-icons/pipeline/blackiron-feather.png', prompt: '玄铁羽，黑铁质感羽毛，边缘有赤色锻痕，锻造材料，透明背景，像素游戏资产', brief: '羽毛斜线让轻薄形态更明确。', variants: [{ label: '源图', src: '/hero-icons/pipeline/blackiron-feather-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/blackiron-feather-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/blackiron-feather-preview.png' }] },
  { name: '朱砂符钉', tint: notionTokens.tintRose, status: '全流程', src: '/hero-icons/pipeline/cinnabar-rune-nail.png', prompt: '朱砂符钉，红色咒钉缠金色符线，封印道具，透明背景，硬边像素风，适合物品栏', brief: '红钉与符线让“封印”属性直接显现。', variants: [{ label: '源图', src: '/hero-icons/pipeline/cinnabar-rune-nail-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/cinnabar-rune-nail-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/cinnabar-rune-nail-preview.png' }] },
  { name: '青藤心核', tint: notionTokens.tintMint, status: '全流程', src: '/hero-icons/pipeline/vineheart-core.png', prompt: '青藤心核，绿色圆形生命核心，被藤蔓缠绕，德鲁伊材料，透明背景，清晰像素块', brief: '圆核心与藤蔓分叉展示生命系属性。', variants: [{ label: '源图', src: '/hero-icons/pipeline/vineheart-core-source.png' }, { label: 'Grid', src: '/hero-icons/pipeline/vineheart-core-grid.png' }, { label: '预览', src: '/hero-icons/pipeline/vineheart-core-preview.png' }] },
]

const workflowStats = [
  { value: '12', label: '全流程素材', tone: notionTokens.brandOrange },
  { value: '3 图', label: '悬浮详情', tone: notionTokens.brandGreen },
  { value: 'VL+Grid', label: '完整验收', tone: notionTokens.brandPink },
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
  displaySize: 96,
  frameCount: 9,
  durationMs: 120,
  frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/moonblade-knight-frame-${String(index + 1).padStart(2, '0')}.png`),
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
              label={signedIn ? 'AI 批量工位' : 'AI 批量像素资产'}
              sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.tintYellowBold, color: notionTokens.ink, borderRadius: 1 }}
            />
            <Box>
              <Typography variant="h1" sx={{ maxWidth: 760, fontSize: signedIn ? { xs: 36, md: 52 } : { xs: 42, sm: 58, md: 76 }, color: notionTokens.onDark }}>
                AI 驱动，批量生成可用像素资产
              </Typography>
              <Typography sx={{ mt: 2.5, maxWidth: 650, fontSize: { xs: 16, md: 18 }, lineHeight: 1.65, color: notionTokens.onDarkMuted }}>
                一次输入一组需求，批量生成、挑选、微调、重试和下载，都在一个工位里完成。
              </Typography>
            </Box>

            <ProductionBrief />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href={signedIn ? '#/workspace' : '#auth-panel'}>开始批量生成</Button>
              <Button variant="outlined" href={signedIn ? '#/packs' : '#examples'} sx={{ color: notionTokens.onDark, borderColor: 'rgba(255,255,255,.45)' }}>{signedIn ? '查看素材包' : '看 76 套范例'}</Button>
            </Stack>

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, max-content)' }, gap: 1.5 }}>
              {(signedIn ? [
                { value: activeJobs, label: '队列中', tone: notionTokens.brandTeal },
                { value: failedJobs, label: '失败待处理', tone: notionTokens.brandPink },
                { value: balance?.available_credits ?? '—', label: '可用点数', tone: notionTokens.brandOrange },
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
            <Typography>全流程生成：月蚀铃、苍火鳞、星盐瓶……经过生图、VL 分析、像素化与 Grid 验收</Typography>
          </Box>
          <Chip label="批量生成" sx={{ bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, borderRadius: 1 }} />
        </Box>
      </CardContent>
    </Card>
  )
}

function PixelBatchBoard({ user, balance, activeJobs, completedJobs, failedJobs, batchCount = 0 }: AppHeroProps) {
  return (
    <Card sx={{ bgcolor: notionTokens.surfaceSoft, borderRadius: 2.5, boxShadow: notionTokens.mockupShadow, overflow: 'visible' }}>
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={2}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">素材包看板</Typography>
              <Typography variant="h5">{user ? `${user.display_name || user.email} 的进度` : 'RPG Starter Pack'}</Typography>
            </Box>
            <Chip label={user?.role ?? 'demo'} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800, borderRadius: 1 }} />
          </Stack>

          <Box sx={{ position: 'relative', overflow: 'visible', display: 'grid', gridTemplateColumns: { xs: 'repeat(3, 1fr)', sm: 'repeat(4, 1fr)' }, gap: 1.2 }}>
            {showcaseItems.map((tile) => <PixelTile key={tile.name} tile={tile} />)}
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1 }}>
            <BoardMetric label="完成" value={user ? completedJobs : 17} />
            <BoardMetric label="失败" value={user ? failedJobs : 3} />
            <BoardMetric label="素材包" value={batchCount} />
            <BoardMetric label="点数" value={balance?.available_credits ?? '—'} />
          </Box>

          <ScaleBench />

          <SpritePreviewBench />

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

function ScaleBench() {
  return (
    <Box sx={{ border: `1px solid ${notionTokens.hairline}`, borderRadius: 1.6, bgcolor: 'rgba(255,255,255,.035)', p: 1.35 }}>
      <Stack spacing={1.1}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">多图验收台</Typography>
            <Typography sx={{ fontWeight: 700, lineHeight: 1.15 }}>源图 / Grid / 预览同屏</Typography>
          </Box>
          <Chip size="small" label="hover" sx={{ bgcolor: notionTokens.tintYellowBold, color: notionTokens.ink, borderRadius: 1 }} />
        </Stack>

        <Stack spacing={.85}>
          {scaleSamples.map((sample) => (
            <Box key={sample.name} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'minmax(88px, .9fr) 1.45fr' }, gap: 1, alignItems: 'center', bgcolor: sample.tint, borderRadius: 1.4, border: `1px solid ${notionTokens.hairline}`, p: .9 }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="caption" sx={{ display: 'block', fontWeight: 700 }} noWrap>{sample.name}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.25 }}>{sample.note}</Typography>
              </Box>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: .75 }}>
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
    <Box sx={{ minWidth: 0, display: 'grid', placeItems: 'center', gap: .35, bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, py: .7, px: .5 }}>
      <Box component="img" src={size.src} alt={`${size.label} 版本`} width={48} height={48} loading="eager" decoding="async" sx={{ width: 42, height: 42, objectFit: 'contain', imageRendering: 'pixelated' }} />
      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>{size.label}</Typography>
    </Box>
  )
}

function PixelTile({ tile }: { tile: typeof showcaseItems[number] }) {
  return (
    <Box
      tabIndex={0}
      sx={{
        position: 'relative',
        bgcolor: tile.tint,
        borderRadius: 1.4,
        border: `1px solid ${notionTokens.hairline}`,
        p: 1,
        minWidth: 0,
        outline: 'none',
        isolation: 'isolate',
        transition: 'transform 220ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1), border-color 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        '&:hover, &:focus-visible, &:focus-within': {
          transform: 'translateY(-4px) scale(1.035)',
          boxShadow: notionTokens.liftShadow,
          borderColor: notionTokens.hairlineStrong,
          zIndex: 8,
        },
        '&:hover .pixel-tile-detail, &:focus-visible .pixel-tile-detail, &:focus-within .pixel-tile-detail': {
          opacity: 1,
          transform: { xs: 'translate(-50%, 8px) scale(1)', sm: 'translate(-50%, 10px) scale(1)' },
          pointerEvents: 'auto',
        },
      }}
    >
      <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 72, backgroundColor: notionTokens.canvas, backgroundImage: `linear-gradient(45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(-45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%), linear-gradient(-45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%)`, backgroundSize: '16px 16px', backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0', borderRadius: 1 }}>
        <Box component="img" src={tile.src} alt={`${tile.name} 64×64 像素素材`} width={64} height={64} loading="eager" decoding="async" sx={{ width: 64, height: 64, objectFit: 'contain', imageRendering: 'pixelated' }} />
      </Box>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: .75, mt: .8 }}>
        <Typography variant="caption" sx={{ display: 'block', fontWeight: 700 }} noWrap>{tile.name}</Typography>
        <Chip size="small" label={tile.status} sx={{ height: 20, borderRadius: .8, bgcolor: notionTokens.canvas, color: notionTokens.ink, '& .MuiChip-label': { px: .8, fontSize: 11 } }} />
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>中文 prompt</Typography>
      <PixelTileDetail tile={tile} />
    </Box>
  )
}

function PixelTileDetail({ tile }: { tile: typeof showcaseItems[number] }) {
  return (
    <Box
      className="pixel-tile-detail"
      aria-hidden="true"
      sx={{
        position: 'absolute',
        left: '50%',
        top: '100%',
        width: { xs: 250, sm: 286 },
        p: 1.25,
        borderRadius: 1.6,
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
      <Stack spacing={1.05}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 800, lineHeight: 1.1 }} noWrap>{tile.name}</Typography>
            <Typography variant="caption" color="text.secondary">Pix 全流程 / 16×16 / Grid</Typography>
          </Box>
          <Box component="img" src={tile.src} alt="" width={40} height={40} loading="eager" decoding="async" sx={{ width: 40, height: 40, imageRendering: 'pixelated', objectFit: 'contain' }} />
        </Stack>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: .75 }}>
          {tile.variants.map((variant) => (
            <Box key={variant.label} sx={{ minWidth: 0, bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .65, display: 'grid', placeItems: 'center', gap: .35 }}>
              <Box component="img" src={variant.src} alt={`${tile.name} ${variant.label}`} width={48} height={48} loading="lazy" decoding="async" sx={{ width: 48, height: 48, objectFit: 'contain', imageRendering: 'pixelated' }} />
              <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>{variant.label}</Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ bgcolor: tile.tint, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .9 }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 800, mb: .35 }}>中文 Prompt</Typography>
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
        borderRadius: 1.6,
        bgcolor: notionTokens.tintLavender,
        p: 1.25,
        outline: 'none',
        transition: 'transform 220ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1), border-color 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        '@keyframes spriteFrameRun': {
          to: { backgroundPosition: `-${sheetTravel}px 0` },
        },
        '&:hover, &:focus-visible, &:focus-within': {
          transform: 'translateY(-3px)',
          boxShadow: notionTokens.liftShadow,
          borderColor: notionTokens.brandPurple800,
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
          '& .sprite-frame-player': { animation: 'none !important' },
          '& .sprite-detail': { transition: 'none' },
        },
      }}
    >
      <Stack direction="row" spacing={1.3} sx={{ alignItems: 'center' }}>
        <Box sx={{ display: 'grid', placeItems: 'center', width: displaySize + 18, height: displaySize + 18, borderRadius: 1.4, bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}` }}>
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
            <Chip size="small" label={spriteShowcase.status} sx={{ height: 20, borderRadius: .8, bgcolor: notionTokens.canvas, color: notionTokens.ink, '& .MuiChip-label': { px: .8, fontSize: 11 } }} />
          </Stack>
          <Typography sx={{ fontWeight: 800, lineHeight: 1.2 }} noWrap>{spriteShowcase.name}</Typography>
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
        p: 1.25,
        borderRadius: 1.6,
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
      <Stack spacing={1.05}>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 800, lineHeight: 1.1 }} noWrap>{spriteShowcase.name}</Typography>
            <Typography variant="caption" color="text.secondary">Pix sprite / 3×3 / 9 帧</Typography>
          </Box>
          <Box component="img" src={spriteShowcase.gif} alt="" width={48} height={48} loading="lazy" decoding="async" sx={{ width: 48, height: 48, objectFit: 'contain', imageRendering: 'pixelated' }} />
        </Stack>

        <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .8 }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 800, mb: .45 }}>横向精灵图</Typography>
          <Box component="img" src={spriteShowcase.sheet} alt={`${spriteShowcase.name} 横向精灵图`} width={576} height={64} loading="lazy" decoding="async" sx={{ width: '100%', height: 54, objectFit: 'contain', imageRendering: 'pixelated', display: 'block' }} />
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(9, minmax(0, 1fr))', gap: .35 }}>
          {spriteShowcase.frames.map((frame, index) => (
            <Box key={frame} component="img" src={frame} alt={`${spriteShowcase.name} 第 ${index + 1} 帧`} width={64} height={64} loading="lazy" decoding="async" sx={{ width: '100%', aspectRatio: '1', objectFit: 'contain', imageRendering: 'pixelated', bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: .6 }} />
          ))}
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: .75 }}>
          <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .65, display: 'grid', placeItems: 'center', gap: .35 }}>
            <Box component="img" src={spriteShowcase.source} alt={`${spriteShowcase.name} 3×3 源图`} width={96} height={96} loading="lazy" decoding="async" sx={{ width: 74, height: 74, objectFit: 'contain' }} />
            <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>3×3 源图</Typography>
          </Box>
          <Box sx={{ bgcolor: notionTokens.tintLavender, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .85 }}>
            <Typography variant="caption" sx={{ display: 'block', fontWeight: 800, mb: .35 }}>中文 Prompt</Typography>
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
