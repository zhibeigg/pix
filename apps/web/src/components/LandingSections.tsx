import type { ReactNode } from 'react'
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'

const values = [
  { title: '单一工作区', body: '生成、作品、点数都在一处。', tone: notionTokens.tintLavender },
  { title: '批量生产', body: '一组素材统一入队、重试、下载。', tone: notionTokens.tintMint },
  { title: '参数可控', body: '尺寸、颜色、透明背景可调。', tone: notionTokens.tintSky },
  { title: '成本清楚', body: '入队前看消耗，失败自动退回。', tone: notionTokens.tintYellow },
]

const workflow = [
  { step: '01', title: '描述', body: '写素材名，设尺寸和颜色。' },
  { step: '02', title: '入队', body: '单张试方向，批量成素材包。' },
  { step: '03', title: '导出', body: '挑选、微调、打包下载。' },
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

type LandingSectionsProps = {
  authSlot: ReactNode
}

export function LandingSections({ authSlot }: LandingSectionsProps) {
  return (
    <>
      <SectionFrame id="values" eyebrow="核心价值" title="一张可控的像素工位台" description="从想法到素材包，生成、成本和结果都放在同一处。">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          {values.map((item) => (
            <Card key={item.title} sx={{ bgcolor: item.tone, overflow: 'hidden', transition: 'transform .22s ease, box-shadow .22s ease', '&:hover': { transform: 'translateY(-4px)', boxShadow: notionTokens.liftShadow } }}>
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

      <SectionFrame id="workflow" eyebrow="工作流" title="三步出素材包" description="描述、入队、导出。失败项单独重试。">
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

      <Box id="auth-panel" component="section" sx={{ scrollSnapAlign: { md: 'start' }, minHeight: { md: '100vh' }, display: 'flex', alignItems: 'center', bgcolor: notionTokens.surfaceSoft, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 } }}>
        <Box sx={{ width: '100%', maxWidth: 1152, mx: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 4, lg: 7 }, alignItems: 'center' }}>
          <Stack spacing={2.5}>
            <Chip label="开始" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark }} />
            <Typography variant="h2" sx={{ fontSize: { xs: 36, md: 56 } }}>进入像素工位台</Typography>
            <Typography color="text.secondary" sx={{ maxWidth: 560, fontSize: { md: 18 } }}>创建单图或素材包，完成后在作品库挑选和导出。</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button variant="contained" color="primary" href="#auth-panel">登录</Button>
              <Button variant="outlined" href="#values">看能力</Button>
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
  children: ReactNode
}

function SectionFrame({ id, eyebrow, title, description, children }: SectionFrameProps) {
  return (
    <Box id={id} component="section" sx={{ scrollSnapAlign: { md: 'start' }, minHeight: { md: '100vh' }, display: 'flex', alignItems: 'center', bgcolor: notionTokens.canvas, px: { xs: 2, md: 4 }, py: { xs: 7, md: 9 } }}>
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
