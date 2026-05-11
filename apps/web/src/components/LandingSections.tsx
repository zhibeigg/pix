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

const scenarios = ['RPG Icon', 'UI Item', 'Tileset', 'Avatar', 'Skill Badge', 'Sprite Sheet', 'Inventory', 'Quest Prop', 'Shop Asset', 'Game Jam', 'Prototype', 'Indie Toolkit']

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
