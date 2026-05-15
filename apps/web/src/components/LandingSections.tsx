import type { ReactNode } from 'react'
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { checkerboardSx, notionTokens } from '../theme'
import { homepageExampleCategories, homepageExamples, type HomepageExample } from '../homepageExamples'

const advantageProofs = [
  { label: '工程图', title: '不只给一张图', body: '源图、Pixel Grid、透明 PNG、预览与 meta 一起归档，便于复查和返修。', tone: notionTokens.tintLavender, mark: 'JSON' },
  { label: '批量包', title: '按素材包生产', body: '一组素材统一入队；失败项单独重试，成功项直接打包下载。', tone: notionTokens.tintMint, mark: 'ZIP' },
  { label: '小尺寸', title: '交付前先验收', body: '16×16、32×32 关注轮廓和色板，不把大图粗暴缩小当成像素资产。', tone: notionTokens.tintSky, mark: '16' },
]

const pipelineProofs = [
  { step: '01', title: '定规格', body: '名称、尺寸、颜色数、透明背景进入同一张任务单。' },
  { step: '02', title: '跑流水线', body: '图像模型、Grid 提取、像素化与后处理串联。' },
  { step: '03', title: '验收导出', body: '查看结果、点数、失败原因，再决定重试或下载。' },
]

const uiWorks = [
  { name: '背包格', src: '/hero-ui/inventory-slot.png', note: '物品栏 / 装备槽', width: 128, height: 128, span: 1 },
  { name: '技能按钮', src: '/hero-ui/skill-button.png', note: '技能栏 / 快捷键', width: 128, height: 128, span: 1 },
  { name: '生命条', src: '/hero-ui/health-bar.png', note: 'HUD / 战斗状态', width: 256, height: 128, span: 2 },
  { name: '对话框', src: '/hero-ui/dialog-panel.png', note: 'NPC 对话 / 提示窗', width: 256, height: 168, span: 2 },
  { name: '任务牌', src: '/hero-ui/quest-card.png', note: '任务列表 / 公告板', width: 256, height: 184, span: 2 },
  { name: '金币计数器', src: '/hero-ui/coin-counter.png', note: '经济系统 / 商店', width: 240, height: 112, span: 2 },
  { name: '菜单标签', src: '/hero-ui/menu-tab.png', note: '页签 / 设置面板', width: 240, height: 128, span: 2 },
  { name: '确认勾选', src: '/hero-ui/check-toggle.png', note: '开关 / 选项状态', width: 128, height: 128, span: 1 },
]

const examplesByCategory = homepageExampleCategories.map((category) => ({
  category,
  examples: homepageExamples.filter((example) => example.category === category),
}))

const itemSpriteSlots = Array.from({ length: 8 }, (_, index) => ({
  index,
  col: index % 4,
  row: Math.floor(index / 4),
}))

const categoryPromptNotes: Record<string, string> = {
  东方: '东方幻想、历史器物、水墨纹样与玉石/朱砂/青铜材质。',
  西幻: 'RPG 冒险装备、魔法器物、纹章、皮革、金属与卷轴材质。',
  科幻: '未来装备、能源核心、终端芯片、机械零件与清晰发光状态。',
  恐怖: '诡异遗物、仪式物件、破损材质与高识别度阴影轮廓。',
  现代: '当代生活道具、职业线索、街区物件与可读 UI 状态。',
  历史: '时代器物、地图、武器、徽章与旧纸/木材/金属质感。',
  混搭: '跨题材组合物、鲜明符号、夸张轮廓与易拆分素材。',
  跨文化: '地域纹样、民俗器物、自然色板与尊重题材来源的装饰。',
  主题: '玩法导向道具、活动物件、清晰图标语义与统一色板。',
}

type LandingSectionsProps = {
  authSlot: ReactNode
}

export function LandingSections({ authSlot }: LandingSectionsProps) {
  return (
    <>
      <SectionFrame id="workflow" eyebrow="核心优势" title="不是 AI 生图相册，是像素素材生产线" description="Pix 的重点不是把 prompt 变成一张好看的图，而是把一批想法变成可检查、可重试、可导出的游戏素材。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.92fr 1.08fr' }, gap: { xs: 2.5, lg: 3.5 }, alignItems: 'stretch' }}>
          <Card sx={{ bgcolor: notionTokens.surface, minHeight: { md: 410 }, overflow: 'hidden' }}>
            <CardContent sx={{ p: { xs: 2.5, md: 3.5 }, height: '100%' }}>
              <Stack spacing={3} sx={{ height: '100%', justifyContent: 'space-between' }}>
                <Stack spacing={2.2}>
                  <Chip label="为什么是 Pix" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, borderRadius: 1 }} />
                  <Typography variant="h3" sx={{ maxWidth: 520 }}>从“生成图片”推进到“交付素材”</Typography>
                  <Typography color="text.secondary" sx={{ maxWidth: 570, fontSize: { md: 17 }, lineHeight: 1.7 }}>
                    普通 AI 图像工具停在预览图。Pix 把源图、像素工程图、透明 PNG、任务状态、失败重试和 ZIP 导出放在同一条流水线里，适合独立游戏和 RPG 素材包快速打样。
                  </Typography>
                </Stack>

                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: .9 }}>
                  {pipelineProofs.map((item) => (
                    <Box key={item.step} sx={{ bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: { xs: 1.15, sm: 1.4 }, minWidth: 0 }}>
                      <Typography variant="caption" sx={{ color: notionTokens.brandPurple800, fontWeight: 600 }}>{item.step}</Typography>
                      <Typography sx={{ mt: .65, fontWeight: 600 }} noWrap>{item.title}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', sm: 'block' }, mt: .45, lineHeight: 1.35 }}>{item.body}</Typography>
                    </Box>
                  ))}
                </Box>
              </Stack>
            </CardContent>
          </Card>

          <Box sx={{ display: 'grid', gridTemplateRows: { xs: 'auto', lg: 'repeat(3, 1fr)' }, gap: 1.25 }}>
            {advantageProofs.map((item) => (
              <Card key={item.title} sx={{ bgcolor: item.tone, overflow: 'hidden', transition: 'transform .22s cubic-bezier(.22,1,.36,1), box-shadow .22s ease', '&:hover': { transform: 'translateY(-3px)', boxShadow: notionTokens.liftShadow }, '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } } }}>
                <CardContent sx={{ p: { xs: 2, md: 2.4 } }}>
                  <Box sx={{ display: 'grid', gridTemplateColumns: 'auto minmax(0, 1fr)', gap: 1.7, alignItems: 'center' }}>
                    <Box sx={{ width: 48, height: 48, borderRadius: 1.5, display: 'grid', placeItems: 'center', bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, fontWeight: 600 }}>{item.mark}</Box>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                      <Typography variant="h5" sx={{ mt: .2 }}>{item.title}</Typography>
                      <Typography color="text.secondary" sx={{ mt: .6 }}>{item.body}</Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>
        </Box>
      </SectionFrame>

      <SectionFrame id="pixel-ui" eyebrow="像素 UI" title="道具和界面一起做" description="图标、HUD、按钮、面板可以放进同一批素材里；先把原型需要的交互表面补齐。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.78fr 1.22fr' }, gap: { xs: 3, lg: 4.5 }, alignItems: 'center' }}>
          <Card sx={{ bgcolor: notionTokens.surface, minHeight: 330 }}>
            <CardContent sx={{ p: { xs: 2.7, md: 3.5 } }}>
              <Stack spacing={2.4}>
                <Chip label="UI Kit" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, borderRadius: 1 }} />
                <Typography variant="h4">同一批次补齐道具和 UI</Typography>
                <Typography color="text.secondary">少切工具，先把原型需要的图标、血条、按钮和对话面板做出来。素材和 UI 使用同一套队列与点数规则，结果统一进作品库。</Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: .9 }}>
                  {['透明 PNG', 'Pixel Grid', 'ZIP 导出'].map((item) => (
                    <Box key={item} sx={{ bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: 1.1 }}>
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>{item}</Typography>
                    </Box>
                  ))}
                </Box>
              </Stack>
            </CardContent>
          </Card>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(4, minmax(0, 1fr))' }, gap: 1.2 }}>
            {uiWorks.map((item) => (
              <Box key={item.name} sx={{ gridColumn: { xs: 'span 1', sm: item.span === 2 ? 'span 2' : 'span 1' }, bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1.5, p: 1.1, transition: 'transform .22s cubic-bezier(.22,1,.36,1), box-shadow .22s ease', '&:hover': { transform: 'translateY(-4px)', boxShadow: notionTokens.liftShadow }, '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } } }}>
                <Box sx={{ ...checkerboardSx, display: 'grid', placeItems: 'center', minHeight: item.height + 22, borderRadius: 1, p: item.span === 2 ? 0 : 1 }}>
                  <Box component="img" src={item.src} alt={`${item.name} ${item.width}×${item.height} 像素 UI 作品`} width={item.width} height={item.height} loading="lazy" decoding="async" sx={{ width: '100%', maxWidth: item.width, height: 'auto', objectFit: 'contain', imageRendering: 'pixelated' }} />
                </Box>
                <Typography variant="body2" sx={{ mt: 1, fontWeight: 600 }}>{item.name}</Typography>
                <Typography variant="caption" color="text.secondary">{item.note}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </SectionFrame>

      <SectionFrame id="examples" eyebrow="范例图库" title="76 套题材范例，像首屏一样悬浮验收" description="默认用紧凑素材格展示题材边界；悬浮或键盘聚焦后拆开 8 个物品格，并展开 16:9 UI 展示图、中文 Prompt 和文件名。">
        <ExampleAtlas />
      </SectionFrame>

      <Box id="auth-panel" component="section" sx={{ scrollSnapAlign: { md: 'start' }, position: 'relative', minHeight: { md: '100vh' }, display: 'flex', alignItems: 'center', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 }, overflow: 'hidden' }}>
        <Box sx={{ position: 'absolute', inset: 0, opacity: .14, backgroundImage: 'linear-gradient(oklch(92% .018 82 / .18) 1px, transparent 1px), linear-gradient(90deg, oklch(92% .018 82 / .18) 1px, transparent 1px)', backgroundSize: '32px 32px' }} aria-hidden="true" />
        <Box sx={{ position: 'absolute', left: { xs: -64, md: 48 }, bottom: { xs: 24, md: 72 }, width: 168, height: 168, opacity: .32, background: 'linear-gradient(135deg, oklch(56% .06 86), oklch(42% .06 292))', clipPath: 'polygon(0 0, 100% 0, 100% 18%, 18% 18%, 18% 100%, 0 100%)' }} aria-hidden="true" />
        <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1152, mx: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 4, lg: 7 }, alignItems: 'center' }}>
          <Stack spacing={2.5} sx={{ maxWidth: 560 }}>
            <Chip label="开始生产" sx={{ alignSelf: 'flex-start', bgcolor: 'oklch(16% .03 263)', color: notionTokens.onDark, border: '1px solid oklch(45% .04 256)', borderRadius: 1 }} />
            <Typography variant="h2" sx={{ color: notionTokens.onDark, fontSize: { xs: 38, md: 56 }, letterSpacing: '-.05em' }}>进入像素工位台</Typography>
            <Typography sx={{ color: notionTokens.onDarkMuted, maxWidth: 560, fontSize: { md: 18 }, lineHeight: 1.72 }}>创建单图或素材包，完成后在作品库挑选、重试、打包导出。</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href="#auth-panel">登录</Button>
              <Button variant="outlined" href="#workflow" sx={{ borderColor: 'oklch(58% .04 254)', color: notionTokens.onDark, bgcolor: 'oklch(14% .024 263)', '&:hover': { borderColor: 'oklch(78% .05 250)', bgcolor: 'oklch(20% .03 263)' } }}>看优势</Button>
            </Stack>
          </Stack>
          <Box>{authSlot}</Box>
        </Box>
      </Box>
    </>
  )
}

function ExampleAtlas() {
  return (
    <Stack spacing={3.5}>
      <Card sx={{ bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, overflow: 'hidden', borderColor: 'oklch(42% .035 258)' }}>
        <CardContent sx={{ p: { xs: 2.4, md: 3.2 } }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 2.5, lg: 4.5 }, alignItems: 'center' }}>
            <Stack spacing={2.1}>
              <Chip label="Sample Atlas" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.tintYellow, color: notionTokens.ink, borderRadius: 1 }} />
              <Box>
                <Typography variant="h3" sx={{ color: notionTokens.onDark, maxWidth: 570 }}>题材不是列表，是可验收的样本墙</Typography>
                <Typography sx={{ mt: 1.4, maxWidth: 620, color: notionTokens.onDarkMuted, lineHeight: 1.68 }}>
                  每套范例包含一张透明物品精灵表和一张 1920×1080 UI 展示图。默认像首屏素材格一样轻量浏览，需要细节时把物品拆成 8 个独立格逐个验收。
                </Typography>
              </Box>
            </Stack>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' }, gap: .9 }}>
              {examplesByCategory.map((group) => (
                <Box key={group.category} sx={{ border: '1px solid oklch(46% .035 258)', bgcolor: 'oklch(20% .032 258)', borderRadius: 1.5, p: 1.25 }}>
                  <Typography sx={{ color: notionTokens.onDark, fontWeight: 600 }}>{group.category}</Typography>
                  <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>{group.examples.length} 套范例</Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </CardContent>
      </Card>

      {examplesByCategory.map((group) => (
        <Box key={group.category}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.1} sx={{ alignItems: { xs: 'flex-start', sm: 'center' }, justifyContent: 'space-between', mb: 1.5 }}>
            <Box>
              <Typography variant="h4">{group.category}</Typography>
              <Typography color="text.secondary">{group.examples.length} 套物品 + UI 范例</Typography>
            </Box>
            <Chip label={`${group.examples[0]?.number ?? ''}—${group.examples[group.examples.length - 1]?.number ?? ''}`} sx={{ bgcolor: notionTokens.surface, borderRadius: 1 }} />
          </Stack>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', md: 'repeat(4, minmax(0, 1fr))', xl: 'repeat(6, minmax(0, 1fr))' }, gap: 1 }}>
            {group.examples.map((example) => (
              <ExampleTile key={example.id} example={example} />
            ))}
          </Box>
        </Box>
      ))}
    </Stack>
  )
}

function ExampleTile({ example }: { example: HomepageExample }) {
  const tint = exampleTint(example.category)

  return (
    <Box
      tabIndex={0}
      sx={{
        position: 'relative',
        isolation: 'isolate',
        minWidth: 0,
        bgcolor: tint,
        border: `1px solid ${notionTokens.hairline}`,
        borderRadius: 1.5,
        p: .9,
        outline: 'none',
        transition: 'transform 220ms cubic-bezier(.22,1,.36,1), box-shadow 220ms cubic-bezier(.22,1,.36,1), border-color 220ms ease',
        '&:hover, &:focus-visible, &:focus-within': {
          transform: 'translateY(-4px) scale(1.015)',
          boxShadow: notionTokens.liftShadow,
          borderColor: notionTokens.hairlineStrong,
          zIndex: 15,
        },
        '&:hover .example-detail, &:focus-visible .example-detail, &:focus-within .example-detail': {
          opacity: 1,
          transform: { xs: 'translate(-50%, 9px) scale(1)', sm: 'translate(-50%, 10px) scale(1)' },
          pointerEvents: 'auto',
        },
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
          '&:hover, &:focus-visible, &:focus-within': { transform: 'none' },
          '& .example-detail': { transition: 'none' },
        },
      }}
    >
      <Box sx={{ ...checkerboardSx, display: 'grid', placeItems: 'center', minHeight: { xs: 106, sm: 116 }, borderRadius: 1, p: .75 }}>
        <ItemSpriteGrid example={example} density="compact" />
      </Box>
      <Stack direction="row" spacing={.7} sx={{ alignItems: 'center', justifyContent: 'space-between', mt: .85 }}>
        <Typography variant="caption" sx={{ fontWeight: 600 }} noWrap>{example.theme}</Typography>
        <Chip size="small" label={example.number} sx={{ height: 20, bgcolor: notionTokens.canvas, borderRadius: .75, '& .MuiChip-label': { px: .7, fontSize: 11 } }} />
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>{example.category} · 物品 + UI</Typography>
      <ExampleDetail example={example} tint={tint} />
    </Box>
  )
}

function ExampleDetail({ example, tint }: { example: HomepageExample; tint: string }) {
  return (
    <Box
      className="example-detail"
      aria-hidden="true"
      sx={{
        position: 'absolute',
        left: '50%',
        top: '100%',
        width: { xs: 286, sm: 392, md: 436 },
        maxWidth: 'calc(100vw - 28px)',
        maxHeight: 'min(520px, calc(100vh - 120px))',
        overflowY: 'auto',
        p: 1.15,
        borderRadius: 1.5,
        border: `1px solid ${notionTokens.hairlineStrong}`,
        bgcolor: notionTokens.canvas,
        color: notionTokens.ink,
        boxShadow: notionTokens.mockupShadow,
        opacity: 0,
        transform: 'translate(-50%, -4px) scale(.96)',
        transformOrigin: '50% 0',
        pointerEvents: 'none',
        transition: 'opacity 180ms cubic-bezier(.22,1,.36,1), transform 220ms cubic-bezier(.22,1,.36,1)',
        zIndex: 40,
      }}
    >
      <Stack spacing={1}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 600, lineHeight: 1.12 }} noWrap>{example.number} · {example.theme}</Typography>
            <Typography variant="caption" color="text.secondary">{example.category} / 透明物品精灵表 / 16:9 UI</Typography>
          </Box>
          <Chip size="small" label="Pix 范例" sx={{ bgcolor: tint, borderRadius: .75 }} />
        </Stack>

        <Box sx={{ ...checkerboardSx, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .75 }}>
          <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: .65 }}>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>拆分物品格</Typography>
            <Chip size="small" label="4×2" sx={{ height: 20, bgcolor: notionTokens.canvas, borderRadius: .75, '& .MuiChip-label': { px: .7, fontSize: 11 } }} />
          </Stack>
          <ItemSpriteGrid example={example} density="detail" />
        </Box>

        <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, overflow: 'hidden' }}>
          <Box component="img" src={example.uiSrc} alt={`${example.theme} 像素 UI 展示图`} loading="lazy" decoding="async" width={1920} height={1080} sx={{ width: '100%', aspectRatio: '16 / 9', objectFit: 'contain', imageRendering: 'pixelated', display: 'block' }} />
        </Box>

        <Box sx={{ bgcolor: tint, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .85 }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: .35 }}>物品 Prompt</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.5 }}>{buildChineseItemPrompt(example)}</Typography>
        </Box>

        <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .85 }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: .35 }}>UI Prompt</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.5 }}>{buildChineseUiPrompt(example)}</Typography>
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: .75 }}>
          <FilePill label="item" value={example.itemFile} />
          <FilePill label="ui" value={example.uiFile} />
        </Box>
      </Stack>
    </Box>
  )
}

function ItemSpriteGrid({ example, density }: { example: HomepageExample; density: 'compact' | 'detail' }) {
  const isDetail = density === 'detail'
  const cellGap = isDetail ? .55 : .35

  return (
    <Box
      role="list"
      aria-label={`${example.theme} 拆分物品格`}
      sx={{
        width: '100%',
        display: 'grid',
        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
        gap: cellGap,
      }}
    >
      {itemSpriteSlots.map((slot) => (
        <Box
          key={slot.index}
          role="listitem"
          title={`${example.theme} 物品 ${slot.index + 1}`}
          sx={{
            aspectRatio: '1 / 1',
            minWidth: 0,
            borderRadius: isDetail ? .75 : .5,
            border: `1px solid ${notionTokens.hairline}`,
            bgcolor: notionTokens.canvas,
            overflow: 'hidden',
          }}
        >
          <Box
            role="img"
            aria-label={`${example.theme} 第 ${slot.index + 1} 个物品`}
            sx={{
              width: '100%',
              height: '100%',
              backgroundImage: `url(${example.itemSrc})`,
              backgroundRepeat: 'no-repeat',
              backgroundSize: '400% 200%',
              backgroundPosition: `${(slot.col / 3) * 100}% ${slot.row * 100}%`,
              imageRendering: 'pixelated',
            }}
          />
        </Box>
      ))}
    </Box>
  )
}

function buildChineseItemPrompt(example: HomepageExample) {
  const note = categoryPromptNotes[example.category] ?? '统一题材符号、清晰道具轮廓与可读游戏图标语义。'
  return `像素风「${example.theme}」物品素材表，拆成 4×2 共 8 个独立道具格；每个物品居中构图、透明背景、硬边像素、有限调色板、无抗锯齿，适合作为背包图标或掉落物素材；每格至少 64×64，在 32×32 和 64×64 下都能读清主体。题材方向：${note}`
}

function buildChineseUiPrompt(example: HomepageExample) {
  const note = categoryPromptNotes[example.category] ?? '题材符号明确，面板层级清楚，图标和按钮可读。'
  return `像素风「${example.theme}」16:9 UI 展示图，包含主题面板、边框、按钮、图标、状态区和游戏界面示例；整体为 16-bit RPG / 独立游戏可用风格，像素边缘清晰、信息层级明确、按钮和图标可读，适合作为原型界面视觉方向。题材方向：${note}`
}

function FilePill({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0, bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, px: .85, py: .65 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1 }}>{label}</Typography>
      <Typography component="code" sx={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>{value}</Typography>
    </Box>
  )
}

function exampleTint(category: string) {
  const tints = [notionTokens.tintCream, notionTokens.tintSky, notionTokens.tintMint, notionTokens.tintLavender, notionTokens.tintPeach, notionTokens.tintGray, notionTokens.tintRose, notionTokens.tintYellow]
  const index = (homepageExampleCategories as readonly string[]).indexOf(category)
  return tints[(index >= 0 ? index : 0) % tints.length]
}

type SectionFrameProps = {
  id: string
  eyebrow: string
  title: string
  description: string
  children: ReactNode
}

function SectionFrame({ id, eyebrow, title, description, children }: SectionFrameProps) {
  const isLongSection = id === 'examples'

  return (
    <Box id={id} component="section" sx={{ scrollSnapAlign: { md: 'start' }, minHeight: { md: isLongSection ? 'auto' : '100vh' }, display: 'flex', alignItems: isLongSection ? 'flex-start' : 'center', bgcolor: notionTokens.canvas, px: { xs: 2, md: 4 }, py: { xs: 8, md: 12 } }}>
      <Box sx={{ width: '100%', maxWidth: 1180, mx: 'auto' }}>
        <Box sx={{ mb: { xs: 3.5, md: 4.5 } }}>
          <Typography variant="overline" color="text.secondary">{eyebrow}</Typography>
          <Typography variant="h2" sx={{ mt: 1, fontSize: { xs: 34, md: 48 }, maxWidth: 780 }}>{title}</Typography>
          <Typography color="text.secondary" sx={{ mt: 1.8, maxWidth: 720, fontSize: { md: 18 }, lineHeight: 1.7 }}>{description}</Typography>
        </Box>
        {children}
      </Box>
    </Box>
  )
}
