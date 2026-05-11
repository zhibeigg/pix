import type { ReactNode } from 'react'
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'

const values = [
  { title: '单一工作区', body: '把生成、批量任务、作品库、素材包和点数流水放在同一个操作面板里，减少上下文切换。', tone: notionTokens.tintLavender },
  { title: '批量素材生产', body: '用素材包管理一组任务，失败项可重试，完成后集中查看、筛选和下载。', tone: notionTokens.tintMint },
  { title: '可控像素化管线', body: '像素尺寸、颜色数、透明背景和参考图理解都可配置，适合稳定复现同一风格。', tone: notionTokens.tintSky },
  { title: '成本可见', body: '所有生成都会预估点数，订单、冻结、退回和手动调整都有流水记录。', tone: notionTokens.tintYellow },
]

const workflow = [
  { step: '01', title: '描述想法', body: '从一句素材描述或一组参考图开始，设定像素尺寸、颜色数量和背景处理。' },
  { step: '02', title: '批量入队', body: '单图任务直接验证方向，批量任务会进入素材包，便于追踪每个结果。' },
  { step: '03', title: '沉淀复用', body: '在作品库中微调、复制路径、打包下载，把可用资产沉淀到项目流程。' },
]

const scenarios = ['RPG Icon', 'UI Item', 'Pixel HUD', 'Tileset', 'Avatar', 'Skill Badge', 'Sprite Sheet', 'Inventory', 'Quest Prop', 'Shop Asset', 'Game Jam', 'Prototype', 'Indie Toolkit']

const uiWorks = [
  { name: '背包格', src: '/hero-ui/inventory-slot.png', note: '物品栏 / 装备槽', width: 128, height: 128, span: 1 },
  { name: '技能按钮', src: '/hero-ui/skill-button.png', note: '技能栏 / 快捷键', width: 128, height: 128, span: 1 },
  { name: '生命条', src: '/hero-ui/health-bar.png', note: 'HUD / 战斗状态', width: 256, height: 96, span: 2 },
  { name: '对话框', src: '/hero-ui/dialog-panel.png', note: 'NPC 对话 / 提示窗', width: 256, height: 128, span: 2 },
  { name: '任务牌', src: '/hero-ui/quest-card.png', note: '任务列表 / 公告板', width: 256, height: 128, span: 2 },
  { name: '金币计数器', src: '/hero-ui/coin-counter.png', note: '经济系统 / 商店', width: 240, height: 48, span: 2 },
  { name: '菜单标签', src: '/hero-ui/menu-tab.png', note: '页签 / 设置面板', width: 240, height: 64, span: 2 },
  { name: '确认勾选', src: '/hero-ui/check-toggle.png', note: '开关 / 选项状态', width: 128, height: 128, span: 1 },
]

type LandingSectionsProps = {
  authSlot: ReactNode
}

export function LandingSections({ authSlot }: LandingSectionsProps) {
  return (
    <>
      <SectionFrame id="values" eyebrow="核心价值" title="让像素素材生产更像一张稳定工位台" description="Pix Forge 把创意、队列、成本和资产沉淀拆成可理解的模块，让一组游戏素材从草稿推进到可交付。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          {values.map((item) => (
            <Card key={item.title} sx={{ bgcolor: item.tone, overflow: 'hidden', transition: 'transform .22s ease, box-shadow .22s ease', '&:hover': { transform: 'translateY(-4px)', boxShadow: 'rgba(15, 15, 15, 0.10) 0px 16px 36px -16px' } }}>
              <CardContent sx={{ p: { xs: 3, md: 3.5 } }}>
                <Stack spacing={2}>
                  <Box sx={{ width: 48, height: 48, borderRadius: 2, display: 'grid', placeItems: 'center', bgcolor: notionTokens.canvas, border: `1px solid ${notionTokens.hairline}`, fontWeight: 700 }}>{item.title.slice(0, 1)}</Box>
                  <Typography variant="h5">{item.title}</Typography>
                  <Typography color="text.secondary">{item.body}</Typography>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      </SectionFrame>

      <SectionFrame id="workflow" eyebrow="工作流" title="用 3 个步骤把想法变成可交付素材包" description="从素材描述到批量入队，再到作品库微调和素材包下载，整个流程保持统一状态和统一成本视图。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 3 }}>
          {workflow.map((item) => (
            <Card key={item.step} sx={{ position: 'relative', overflow: 'hidden', minHeight: 230 }}>
              <Box sx={{ position: 'absolute', right: 18, top: 18, width: 28, height: 28, borderRadius: 1, bgcolor: notionTokens.tintYellowBold, opacity: .7 }} />
              <CardContent sx={{ p: { xs: 3, md: 3.5 } }}>
                <Stack spacing={2}>
                  <Chip label={item.step} sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} />
                  <Typography variant="h5">{item.title}</Typography>
                  <Typography color="text.secondary">{item.body}</Typography>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      </SectionFrame>

      <SectionFrame id="pixel-ui" eyebrow="像素 UI" title="不只做道具，也覆盖界面素材" description="游戏原型通常同时需要图标、HUD、背包格、按钮和对话面板。首页展示一组由 Pix 生成的多尺寸 UI 作品，横向条、面板和方形控件都按有效像素贴合画布。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.78fr 1.22fr' }, gap: { xs: 3, lg: 5 }, alignItems: 'center' }}>
          <Card sx={{ bgcolor: notionTokens.tintYellow, minHeight: 340 }}>
            <CardContent sx={{ p: { xs: 3, md: 4 } }}>
              <Stack spacing={2.4}>
                <Chip label="UI Kit Preview" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.inkDeep, color: notionTokens.onDark }} />
                <Typography variant="h4">把 UI 元件和道具放在同一套素材生产节奏里</Typography>
                <Typography color="text.secondary">同一批次可以先生成 RPG 道具，再补 HUD、按钮、背包格和对话框，原型期不用在多个工具之间来回切换。</Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                  {['HUD', 'Inventory', 'Dialog', 'Shop', 'Skill Bar'].map((item) => <Chip key={item} label={item} variant="outlined" />)}
                </Stack>
              </Stack>
            </CardContent>
          </Card>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(4, minmax(0, 1fr))' }, gap: 1.5 }}>
            {uiWorks.map((item) => (
              <Box key={item.name} sx={{ gridColumn: { xs: 'span 1', sm: item.span === 2 ? 'span 2' : 'span 1' }, bgcolor: notionTokens.surfaceSoft, border: `1px solid ${notionTokens.hairline}`, borderRadius: 2, p: 1.3, transition: 'transform .22s ease, box-shadow .22s ease', '&:hover': { transform: 'translateY(-4px)', boxShadow: 'rgba(15, 15, 15, 0.10) 0px 16px 36px -16px' } }}>
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

      <SectionFrame centered id="ecosystem" eyebrow="素材生态" title="覆盖常见独立游戏素材场景" description="不追求无限复杂，而是把高频、小体量、需要一致风格的像素素材生产流程打磨顺手。">
        <Stack direction="row" spacing={1.5} sx={{ flexWrap: 'wrap', justifyContent: 'center', rowGap: 1.5 }}>
          {scenarios.map((item, index) => (
            <Chip
              key={item}
              label={item}
              sx={{
                height: 58,
                px: 2,
                borderRadius: 2,
                bgcolor: index % 4 === 0 ? notionTokens.tintCream : index % 4 === 1 ? notionTokens.tintMint : index % 4 === 2 ? notionTokens.tintSky : notionTokens.tintLavender,
                border: `1px solid ${notionTokens.hairline}`,
                fontSize: 15,
              }}
            />
          ))}
        </Stack>
      </SectionFrame>

      <Box id="auth-panel" component="section" sx={{ scrollSnapAlign: { md: 'start' }, minHeight: { md: '100vh' }, display: 'flex', alignItems: 'center', bgcolor: notionTokens.surfaceSoft, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 } }}>
        <Box sx={{ width: '100%', maxWidth: 1152, mx: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 4, lg: 7 }, alignItems: 'center' }}>
          <Stack spacing={2.5}>
            <Chip label="立即开始" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.inkDeep, color: notionTokens.onDark }} />
            <Typography variant="h2" sx={{ fontSize: { xs: 36, md: 56 } }}>把像素素材流程接进你的项目节奏</Typography>
            <Typography color="text.secondary" sx={{ maxWidth: 560, fontSize: { md: 18 } }}>注册后即可进入生产工作台，创建单图任务、批量素材包，并用作品库持续微调沉淀。</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href="#auth-panel">登录工作台</Button>
              <Button variant="outlined" href="#values">回看能力</Button>
            </Stack>
          </Stack>
          <Box>{authSlot}</Box>
        </Box>
      </Box>
    </>
  )
}

type SectionFrameProps = {
  id: string
  eyebrow: string
  title: string
  description: string
  centered?: boolean
  children: ReactNode
}

function SectionFrame({ id, eyebrow, title, description, centered = false, children }: SectionFrameProps) {
  return (
    <Box id={id} component="section" sx={{ scrollSnapAlign: { md: 'start' }, minHeight: { md: '100vh' }, display: 'flex', alignItems: 'center', bgcolor: notionTokens.canvas, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 } }}>
      <Box sx={{ width: '100%', maxWidth: 1152, mx: 'auto' }}>
        <Box sx={{ textAlign: centered ? 'center' : 'left', mb: 5 }}>
          <Typography variant="overline" color="text.secondary">{eyebrow}</Typography>
          <Typography variant="h2" sx={{ mt: 1, fontSize: { xs: 34, md: 48 }, maxWidth: centered ? 820 : 760, mx: centered ? 'auto' : 0 }}>{title}</Typography>
          <Typography color="text.secondary" sx={{ mt: 2, maxWidth: centered ? 760 : 700, mx: centered ? 'auto' : 0, fontSize: { md: 18 } }}>{description}</Typography>
        </Box>
        {children}
      </Box>
    </Box>
  )
}
