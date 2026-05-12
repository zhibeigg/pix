import type { ReactNode } from 'react'
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import { homepageExampleCategories, homepageExamples, type HomepageExample } from '../homepageExamples'

const advantageProofs = [
  { label: '工程图', title: '不只给你一张图', body: '生成后落成 Pixel Grid：palette、pixels、透明 PNG、预览和源图都能追溯。', tone: notionTokens.tintLavender, mark: 'JSON' },
  { label: '批量包', title: '按素材包生产', body: '一组素材统一入队，失败项单独重试，成功项直接打包下载。', tone: notionTokens.tintMint, mark: 'ZIP' },
  { label: '多尺寸', title: '交付尺寸可验收', body: '32x / 16x / 8x 有不同策略，低尺寸不是简单缩图，而是工程化重绘。', tone: notionTokens.tintSky, mark: '8×' },
]

const pipelineProofs = [
  { step: '01', title: '先定规格', body: '名称、尺寸、颜色数、透明背景先进入同一张任务单。' },
  { step: '02', title: '再批量跑', body: '图像模型、Grid 提取、AI 直绘和后处理串成可追踪流水线。' },
  { step: '03', title: '最后验收', body: '看结果、看点数、看失败原因，导出前就知道哪些能用。' },
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

type LandingSectionsProps = {
  authSlot: ReactNode
}

export function LandingSections({ authSlot }: LandingSectionsProps) {
  return (
    <>
      <SectionFrame id="workflow" eyebrow="核心优势" title="不是 AI 生图相册，是像素素材生产线" description="Pix 的重点不是把 prompt 变成一张好看的图，而是把一批想法变成可检查、可重试、可导出的游戏素材。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.92fr 1.08fr' }, gap: { xs: 3, lg: 4 }, alignItems: 'stretch' }}>
          <Card sx={{ bgcolor: notionTokens.tintYellow, minHeight: { md: 420 }, overflow: 'hidden' }}>
            <CardContent sx={{ p: { xs: 3, md: 4 }, height: '100%' }}>
              <Stack spacing={3} sx={{ height: '100%', justifyContent: 'space-between' }}>
                <Stack spacing={2.2}>
                  <Chip label="为什么是 Pix" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, borderRadius: 1 }} />
                  <Typography variant="h3" sx={{ maxWidth: 520 }}>从“生成图片”推进到“交付素材”</Typography>
                  <Typography color="text.secondary" sx={{ maxWidth: 560, fontSize: { md: 17 }, lineHeight: 1.65 }}>
                    普通 AI 图像工具停在预览图。Pix 把源图、像素工程图、透明 PNG、任务状态、失败重试和 ZIP 导出放在同一条流水线里，适合独立游戏和 RPG 素材包快速打样。
                  </Typography>
                </Stack>

                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
                  {pipelineProofs.map((item) => (
                    <Box key={item.step} sx={{ bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1.4, p: { xs: 1.2, sm: 1.5 }, minWidth: 0 }}>
                      <Typography variant="caption" sx={{ color: notionTokens.brandPurple800, fontWeight: 700 }}>{item.step}</Typography>
                      <Typography sx={{ mt: .7, fontWeight: 700 }} noWrap>{item.title}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', sm: 'block' }, mt: .5, lineHeight: 1.35 }}>{item.body}</Typography>
                    </Box>
                  ))}
                </Box>
              </Stack>
            </CardContent>
          </Card>

          <Box sx={{ display: 'grid', gridTemplateRows: { xs: 'auto', lg: 'repeat(3, 1fr)' }, gap: 1.6 }}>
            {advantageProofs.map((item) => (
              <Card key={item.title} sx={{ bgcolor: item.tone, overflow: 'hidden', transition: 'transform .22s ease, box-shadow .22s ease', '&:hover': { transform: 'translateY(-3px)', boxShadow: notionTokens.liftShadow } }}>
                <CardContent sx={{ p: { xs: 2.3, md: 2.7 } }}>
                  <Box sx={{ display: 'grid', gridTemplateColumns: 'auto minmax(0, 1fr) auto', gap: 2, alignItems: 'center' }}>
                    <Box sx={{ width: 48, height: 48, borderRadius: 2, display: 'grid', placeItems: 'center', bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, fontWeight: 800 }}>{item.mark}</Box>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="caption" color="text.secondary">{item.label}</Typography>
                      <Typography variant="h5" sx={{ mt: .25 }}>{item.title}</Typography>
                      <Typography color="text.secondary" sx={{ mt: .7 }}>{item.body}</Typography>
                    </Box>
                    <Box sx={{ display: { xs: 'none', sm: 'block' }, width: 28, height: 28, borderRadius: 1, bgcolor: notionTokens.tintYellowBold, opacity: .72 }} />
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>
        </Box>
      </SectionFrame>

      <SectionFrame id="pixel-ui" eyebrow="像素 UI" title="道具和界面一起做" description="图标、HUD、按钮、面板可以放进同一批素材里。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.78fr 1.22fr' }, gap: { xs: 3, lg: 5 }, alignItems: 'center' }}>
          <Card sx={{ bgcolor: notionTokens.tintYellow, minHeight: 340 }}>
            <CardContent sx={{ p: { xs: 3, md: 4 } }}>
              <Stack spacing={2.4}>
                <Chip label="UI Kit" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark }} />
                <Typography variant="h4">同一批次补齐道具和 UI</Typography>
                <Typography color="text.secondary">少切工具，先把原型需要的图标、条、按钮和面板做出来。</Typography>
              </Stack>
            </CardContent>
          </Card>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(4, minmax(0, 1fr))' }, gap: 1.5 }}>
            {uiWorks.map((item) => (
              <Box key={item.name} sx={{ gridColumn: { xs: 'span 1', sm: item.span === 2 ? 'span 2' : 'span 1' }, bgcolor: notionTokens.surfaceSoft, border: `1px solid ${notionTokens.hairline}`, borderRadius: 2, p: 1.3, transition: 'transform .22s ease, box-shadow .22s ease', '&:hover': { transform: 'translateY(-4px)', boxShadow: notionTokens.liftShadow } }}>
                <Box sx={{ display: 'grid', placeItems: 'center', minHeight: item.height + 28, borderRadius: 1.4, bgcolor: notionTokens.canvas, backgroundImage: `linear-gradient(45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(-45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%), linear-gradient(-45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%)`, backgroundSize: '16px 16px', backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0' }}>
                  <Box component="img" src={item.src} alt={`${item.name} ${item.width}×${item.height} 像素 UI 作品`} width={item.width} height={item.height} loading="lazy" decoding="async" sx={{ width: '100%', maxWidth: item.width, height: 'auto', objectFit: 'contain', imageRendering: 'pixelated' }} />
                </Box>
                <Typography variant="body2" sx={{ mt: 1, fontWeight: 600 }}>{item.name}</Typography>
                <Typography variant="caption" color="text.secondary">{item.note}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </SectionFrame>

      <SectionFrame id="examples" eyebrow="范例图库" title="76 套题材范例，一屏铺开生产边界" description="物品精灵表和 16:9 UI 展示图都由 Pix 像素化管线生成，适合作为主页上的题材覆盖证明。">
        <ExampleAtlas />
      </SectionFrame>

      <Box id="auth-panel" component="section" sx={{ scrollSnapAlign: { md: 'start' }, position: 'relative', minHeight: { md: '100vh' }, display: 'flex', alignItems: 'center', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 }, overflow: 'hidden' }}>
        <Box sx={{ position: 'absolute', inset: 0, opacity: .2, backgroundImage: 'linear-gradient(oklch(92% .03 248 / .18) 1px, transparent 1px), linear-gradient(90deg, oklch(92% .03 248 / .18) 1px, transparent 1px)', backgroundSize: '32px 32px' }} aria-hidden="true" />
        <Box sx={{ position: 'absolute', left: { xs: -64, md: 48 }, bottom: { xs: 24, md: 72 }, width: 180, height: 180, opacity: .5, background: 'linear-gradient(135deg, oklch(77% .17 82), oklch(64% .16 322))', clipPath: 'polygon(0 0, 100% 0, 100% 18%, 18% 18%, 18% 100%, 0 100%)' }} aria-hidden="true" />
        <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1152, mx: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 4, lg: 7 }, alignItems: 'center' }}>
          <Stack spacing={2.5} sx={{ maxWidth: 560 }}>
            <Chip label="开始" sx={{ alignSelf: 'flex-start', bgcolor: 'oklch(16% .03 263)', color: notionTokens.onDark, border: '1px solid oklch(45% .06 256)', borderRadius: 1.2 }} />
            <Typography variant="h2" sx={{ color: notionTokens.onDark, fontSize: { xs: 38, md: 56 }, letterSpacing: '-.06em' }}>进入像素工位台</Typography>
            <Typography sx={{ color: notionTokens.onDarkMuted, maxWidth: 560, fontSize: { md: 18 }, lineHeight: 1.72 }}>创建单图或素材包，完成后在作品库挑选、重试、打包导出。</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href="#auth-panel" sx={{ bgcolor: 'oklch(71% .17 296)', color: 'oklch(12% .028 263)', fontWeight: 900, '&:hover': { bgcolor: 'oklch(76% .16 296)' } }}>登录</Button>
              <Button variant="outlined" href="#workflow" sx={{ borderColor: 'oklch(58% .06 254)', color: notionTokens.onDark, bgcolor: 'oklch(14% .024 263)', '&:hover': { borderColor: 'oklch(78% .07 250)', bgcolor: 'oklch(20% .036 263)' } }}>看优势</Button>
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
    <Stack spacing={4}>
      <Card sx={{ bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, overflow: 'hidden', borderColor: 'rgba(255,255,255,.14)' }}>
        <CardContent sx={{ p: { xs: 2.5, md: 3.5 } }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.92fr 1.08fr' }, gap: { xs: 3, lg: 5 }, alignItems: 'center' }}>
            <Stack spacing={2.2}>
              <Chip label="Sample Atlas" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.tintYellowBold, color: notionTokens.ink, borderRadius: 1 }} />
              <Box>
                <Typography variant="h3" sx={{ color: notionTokens.onDark, maxWidth: 560 }}>从东方武侠到多元宇宙，先给玩家看见可能性</Typography>
                <Typography sx={{ mt: 1.5, maxWidth: 620, color: notionTokens.onDarkMuted, lineHeight: 1.65 }}>
                  每套范例包含一张透明物品精灵表和一张 1920×1080 UI 展示图。主页不只展示“能生成图”，而是展示题材库可以如何服务游戏原型。
                </Typography>
              </Box>
            </Stack>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)' }, gap: 1 }}>
              {examplesByCategory.map((group) => (
                <Box key={group.category} sx={{ border: '1px solid rgba(255,255,255,.16)', bgcolor: 'rgba(255,255,255,.055)', borderRadius: 1.4, p: 1.4 }}>
                  <Typography sx={{ color: notionTokens.onDark, fontWeight: 700 }}>{group.category}</Typography>
                  <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>{group.examples.length} 套范例</Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </CardContent>
      </Card>

      {examplesByCategory.map((group, groupIndex) => (
        <Box key={group.category}>
          <Stack direction="row" spacing={1.2} sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Box>
              <Typography variant="h4">{group.category}</Typography>
              <Typography color="text.secondary">{group.examples.length} 套物品 + UI 范例</Typography>
            </Box>
            <Chip label={`${group.examples[0]?.number ?? ''}—${group.examples[group.examples.length - 1]?.number ?? ''}`} sx={{ bgcolor: notionTokens.tintCream, borderRadius: 1 }} />
          </Stack>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))', xl: 'repeat(3, minmax(0, 1fr))' }, gap: 1.4 }}>
            {group.examples.map((example, index) => (
              <ExampleCard key={example.id} example={example} featured={(groupIndex + index) % 11 === 0} />
            ))}
          </Box>
        </Box>
      ))}
    </Stack>
  )
}

function ExampleCard({ example, featured }: { example: HomepageExample; featured: boolean }) {
  return (
    <Box sx={{ gridColumn: { xl: featured ? 'span 2' : 'span 1' }, bgcolor: notionTokens.surfaceSoft, border: `1px solid ${notionTokens.hairline}`, borderRadius: 2, overflow: 'hidden', minWidth: 0, transition: 'transform .2s ease, box-shadow .2s ease', '&:hover': { transform: 'translateY(-3px)', boxShadow: notionTokens.liftShadow }, '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } } }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: featured ? '.9fr 1.1fr' : '1fr' }, gap: 0 }}>
        <ExampleImage kind="item" src={example.itemSrc} alt={`${example.theme} 透明物品精灵表`} />
        <ExampleImage kind="ui" src={example.uiSrc} alt={`${example.theme} 像素 UI 展示图`} />
      </Box>
      <Box sx={{ p: 1.6 }}>
        <Stack direction="row" spacing={.8} sx={{ alignItems: 'center', flexWrap: 'wrap', mb: .9 }}>
          <Chip size="small" label={example.number} sx={{ bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, borderRadius: .8, height: 24 }} />
          <Chip size="small" label={example.category} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800, borderRadius: .8, height: 24 }} />
        </Stack>
        <Typography variant="h6" sx={{ lineHeight: 1.15 }}>{example.theme}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: .8, fontFamily: 'monospace' }}>{example.itemFile} · {example.uiFile}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', mt: .8, lineHeight: 1.35 }}>
          {example.itemPrompt}
        </Typography>
      </Box>
    </Box>
  )
}

function ExampleImage({ kind, src, alt }: { kind: 'item' | 'ui'; src: string; alt: string }) {
  const isItem = kind === 'item'
  return (
    <Box sx={{ minHeight: isItem ? 124 : 166, display: 'grid', placeItems: 'center', bgcolor: notionTokens.canvas, borderBottom: `1px solid ${notionTokens.hairline}`, backgroundImage: `linear-gradient(45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(-45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%), linear-gradient(-45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%)`, backgroundSize: '16px 16px', backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0', p: isItem ? 2 : 0 }}>
      <Box component="img" src={src} alt={alt} loading="lazy" decoding="async" width={isItem ? 128 : 1920} height={isItem ? 64 : 1080} sx={{ width: isItem ? 'min(100%, 256px)' : '100%', height: 'auto', maxHeight: isItem ? 96 : 220, objectFit: 'contain', imageRendering: 'pixelated', display: 'block' }} />
    </Box>
  )
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
    <Box id={id} component="section" sx={{ scrollSnapAlign: { md: 'start' }, minHeight: { md: isLongSection ? 'auto' : '100vh' }, display: 'flex', alignItems: isLongSection ? 'flex-start' : 'center', bgcolor: notionTokens.canvas, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 } }}>
      <Box sx={{ width: '100%', maxWidth: 1152, mx: 'auto' }}>
        <Box sx={{ mb: 5 }}>
          <Typography variant="overline" color="text.secondary">{eyebrow}</Typography>
          <Typography variant="h2" sx={{ mt: 1, fontSize: { xs: 34, md: 48 }, maxWidth: 760 }}>{title}</Typography>
          <Typography color="text.secondary" sx={{ mt: 2, maxWidth: 700, fontSize: { md: 18 } }}>{description}</Typography>
        </Box>
        {children}
      </Box>
    </Box>
  )
}
