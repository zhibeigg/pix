import { useEffect, useMemo, useState, type MouseEvent, type ReactNode } from 'react'
import { homepageExampleCategories, homepageExamples, type HomepageExample } from '../homepageExamples'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { PixPreviewFrame } from './pix/PixPreviewFrame'

const stickyNotes = [
  { label: '任务单', title: '先定交付规格', body: '名称、尺寸、颜色数、透明背景和批次备注先进同一张生产单。', mark: '01', tone: 'bg-[hsl(var(--pix-peach))]' },
  { label: '工程图', title: '不只给一张图', body: '源图、Pixel Grid、透明 PNG、预览与 meta 一起归档，便于复查和返修。', mark: 'JSON', tone: 'bg-[hsl(var(--pix-lavender))]' },
  { label: '批量包', title: '按素材包推进', body: '一组素材统一入队；失败项单独重试，成功项直接打包下载。', mark: 'ZIP', tone: 'bg-[hsl(var(--pix-mint))]' },
  { label: '小尺寸', title: '交付前先验收', body: '16×16、32×32 关注轮廓和色板，不把大图粗暴缩小当成像素资产。', mark: '16', tone: 'bg-[hsl(var(--pix-sky))]' },
]

const pipelineProofs = [
  { step: '01', title: '定规格', body: 'Prompt、尺寸、透明背景和颜色数进入同一张任务单。' },
  { step: '02', title: '跑流水线', body: '图像模型、Grid 提取、像素化与后处理串联。' },
  { step: '03', title: '验收导出', body: '查看结果、点数、失败原因，再决定重试或下载。' },
]

const assistantTiles = [
  { title: 'Prompt 助手', body: '把题材、用途、尺寸和透明背景整理成可复用提示词。', badge: 'Prompt', tone: 'bg-[hsl(var(--pix-peach))]' },
  { title: '验收助手', body: '把源图、像素图和透明 PNG 放在一张卡片里比对。', badge: 'Review', tone: 'bg-[hsl(var(--pix-rose))]' },
  { title: '打包助手', body: '批量导出、路径复制和失败重试从作品库直接完成。', badge: 'Pack', tone: 'bg-[hsl(var(--pix-mint))]' },
]

const uiWorks = [
  { name: '背包格', src: '/hero-ui/inventory-slot.png', note: '物品栏 / 装备槽', span: 'sm:col-span-1' },
  { name: '技能按钮', src: '/hero-ui/skill-button.png', note: '技能栏 / 快捷键', span: 'sm:col-span-1' },
  { name: '生命条', src: '/hero-ui/health-bar.png', note: 'HUD / 战斗状态', span: 'sm:col-span-2' },
  { name: '对话框', src: '/hero-ui/dialog-panel.png', note: 'NPC 对话 / 提示窗', span: 'sm:col-span-2' },
  { name: '任务牌', src: '/hero-ui/quest-card.png', note: '任务列表 / 公告板', span: 'sm:col-span-2' },
  { name: '金币计数器', src: '/hero-ui/coin-counter.png', note: '经济系统 / 商店', span: 'sm:col-span-2' },
  { name: '菜单标签', src: '/hero-ui/menu-tab.png', note: '页签 / 设置面板', span: 'sm:col-span-2' },
  { name: '确认勾选', src: '/hero-ui/check-toggle.png', note: '开关 / 选项状态', span: 'sm:col-span-1' },
]

const spriteShowcases = [
  {
    name: '月刃骑士挥剑',
    status: '9 帧',
    prompt: '月刃骑士挥剑三段斩，银蓝盔甲小角色，侧身站姿，连续挥剑动作，适合 RPG 战斗序列帧，透明背景，像素动画精灵',
    brief: 'Pix sprite 全流程输出：3×3 生图 → 9 帧切分 → 共享调色板像素化 → 横向精灵图 + 序列帧播放。',
    source: '/hero-sprites/pipeline/moonblade-knight-source.png',
    sourceLabel: '3×3 源图',
    sheet: '/hero-sprites/pipeline/moonblade-knight-sheet.png',
    frameCount: 9,
    durationMs: 120,
    tone: 'bg-[hsl(var(--pix-lavender))] text-[hsl(var(--pix-charcoal))]',
    frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/moonblade-knight-frame-${String(index + 1).padStart(2, '0')}.png`),
  },
  {
    name: '黑紫魔气爆炸特效',
    status: '9 帧 VFX',
    prompt: '黑紫魔气爆炸特效，64×64 low-detail pixel art VFX，暗紫能量核心、黑色烟雾外扩、九帧爆发消散，透明背景，适合技能命中特效',
    brief: '9 帧 64×64 像素 VFX：单帧 PNG → 横向精灵图 → 序列帧播放，可直接用于技能爆炸/魔法命中动画。',
    source: '/hero-sprites/pipeline/dark-purple-magic-explosion-source.png',
    sourceLabel: '3×3 帧源图',
    sheet: '/hero-sprites/pipeline/dark-purple-magic-explosion-sheet.png',
    frameCount: 9,
    durationMs: 90,
    tone: 'bg-[hsl(var(--pix-rose))] text-[hsl(var(--pix-charcoal))]',
    frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/dark-purple-magic-explosion-frame-${String(index + 1).padStart(2, '0')}.png`),
  },
]

const statRowItems = [
  { value: '12', label: '真实全流程样本', icon: '◆' },
  { value: '76', label: '题材范例可追溯', icon: '◇' },
  { value: 'PNG', label: '透明成品导出', icon: '▣' },
  { value: 'ZIP', label: '素材包一键下载', icon: '▤' },
]

const itemSpriteSlots = Array.from({ length: 8 }, (_, index) => index)

const examplesByCategory = homepageExampleCategories.map((category) => ({
  category,
  examples: homepageExamples.filter((example) => example.category === category),
}))

const featuredExamples = homepageExamples.slice(0, 4)

type LandingSectionsProps = { authSlot: ReactNode }

export function LandingSections({ authSlot }: LandingSectionsProps) {
  return (
    <>
      <SectionFrame id="workflow" eyebrow="Keep work moving 24/7" title="不是 AI 生图相册，是像素素材生产线" description="深色模式沿用 DESIGN.md 的深 navy hero 与清晰卡片层级：作品、队列、成本和导出状态都能在夜间工作台里快速辨认。">
        <WorkflowSection />
      </SectionFrame>

      <StatRow />

      <SectionFrame id="assistant" surface="soft" eyebrow="On-demand assistants" title="把提示词、验收和打包拆成三张助手卡" description="用 Notion 式 pastel feature cards 承接复杂流程：每张卡只负责一个动作，进入工作台后再展开完整参数。">
        <AssistantSection />
      </SectionFrame>

      <SectionFrame id="pixel-ui" eyebrow="Bring work together" title="道具、UI 和动作帧在同一个素材工作区里验收" description="图标、HUD、按钮、面板、角色动作和技能特效可以放进同一批素材；先把原型需要的交互表面补齐。">
        <WorkTogetherSection />
      </SectionFrame>

      <SectionFrame id="sprite-preview" surface="soft" eyebrow="Sprite Pipeline" title="角色动作和技能特效都能做成可播放的精灵图" description="九宫格源图或单帧序列会切成帧、统一调色板像素化，并导出横向精灵图与真实序列帧播放。">
        <SpriteShowcaseList />
      </SectionFrame>

      <SectionFrame id="examples" eyebrow="Sample Atlas" title="76 套题材范例，像首屏一样悬浮验收" description="默认用紧凑素材格展示题材边界；选择题材后拆开 8 个物品格，并展开 16:9 UI 展示图、中文 Prompt 和文件名。">
        <ExampleAtlas />
      </SectionFrame>

      <AuthSection authSlot={authSlot} />
    </>
  )
}

function WorkflowSection() {
  return (
    <div className="grid items-stretch gap-6 lg:grid-cols-[.95fr_1.05fr]">
      <div className="flex min-h-[430px] flex-col justify-between rounded-lg bg-[hsl(var(--pix-amber))] p-8 text-[hsl(var(--pix-charcoal))] md:p-10">
        <div>
          <Badge className="bg-[hsl(var(--pix-navy))] text-white">为什么是 Pix</Badge>
          <h3 className="mt-5 max-w-2xl text-3xl font-semibold tracking-tight md:text-5xl">从“生成图片”推进到“交付素材”</h3>
          <p className="mt-5 max-w-2xl text-base leading-8 text-[hsl(var(--pix-slate))]">普通 AI 图像工具停在预览图。Pix 把源图、像素工程图、透明 PNG、任务状态、失败重试和 ZIP 导出放在同一条流水线里，适合独立游戏和 RPG 素材包快速打样。</p>
        </div>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {pipelineProofs.map((item) => <div key={item.step} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-3"><p className="text-xs font-semibold text-primary">{item.step}</p><p className="mt-2 font-bold">{item.title}</p><p className="mt-1 text-xs leading-5 text-[hsl(var(--pix-slate))]">{item.body}</p></div>)}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {stickyNotes.map((item) => <FeatureNote key={item.title} {...item} />)}
      </div>
    </div>
  )
}

function FeatureNote({ label, title, body, mark, tone }: { label: string; title: string; body: string; mark: string; tone: string }) {
  return (
    <article className={`rounded-lg border border-border p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_1px_2px_rgba(15,15,15,0.04)] transition hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] ${tone}`}>
      <div className="grid grid-cols-[56px_minmax(0,1fr)] items-start gap-4">
        <div className="grid h-14 w-14 place-items-center rounded-lg border border-border bg-card font-semibold text-[hsl(var(--pix-ink))] dark:border-white/15 dark:bg-white/7 dark:text-white">{mark}</div>
        <div>
          <p className="text-xs font-bold uppercase tracking-[.12em] text-[hsl(var(--pix-steel))] dark:text-white/55">{label}</p>
          <h3 className="mt-1 text-xl font-semibold">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-[hsl(var(--pix-slate))] dark:text-white/66">{body}</p>
        </div>
      </div>
    </article>
  )
}

function AssistantSection() {
  return (
    <div className="grid gap-6 lg:grid-cols-[.92fr_1.08fr]">
      <article className="rounded-lg bg-[hsl(var(--pix-amber))] p-8 text-[hsl(var(--pix-charcoal))] md:p-10">
        <Badge className="bg-primary text-primary-foreground">Ask the assistant</Badge>
        <h3 className="mt-5 max-w-2xl text-3xl font-semibold tracking-tight md:text-5xl">把复杂素材需求拆成可执行队列</h3>
        <p className="mt-5 max-w-2xl text-base leading-8 text-[hsl(var(--pix-slate))]">深色主页保留一个高强调黄色卡片说明核心价值，再把具体动作分配给右侧三张 pastel tiles；即使在暗背景里也能一眼分清 Prompt、Grid 和 Pack。</p>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {['Prompt', 'Grid', 'Pack'].map((item) => <div key={item} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-4 text-center font-semibold">{item}</div>)}
        </div>
      </article>
      <div className="grid gap-4">
        {assistantTiles.map((tile) => <AssistantTile key={tile.title} {...tile} />)}
      </div>
    </div>
  )
}

function AssistantTile({ title, body, badge, tone }: { title: string; body: string; badge: string; tone: string }) {
  return (
    <article className={`rounded-lg border border-border p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] ${tone}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <Badge variant="outline" className="bg-white/65 text-[hsl(var(--pix-navy))] dark:border-white/20 dark:bg-white/7 dark:text-white/75">{badge}</Badge>
          <h3 className="mt-4 text-2xl font-semibold">{title}</h3>
          <p className="mt-2 text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/66">{body}</p>
        </div>
        <div className="hidden w-36 rounded-lg border border-border bg-white/60 p-3 dark:border-white/12 dark:bg-white/7 sm:block">
          <div className="h-2 rounded-full bg-[hsl(var(--pix-stone))]/45 dark:bg-white/25" />
          <div className="mt-2 h-2 w-2/3 rounded-full bg-[hsl(var(--pix-stone))]/30 dark:bg-white/15" />
          <div className="mt-4 grid gap-1.5">
            <span className="h-8 rounded-md bg-card dark:bg-white/10" />
            <span className="h-8 rounded-md bg-card dark:bg-white/10" />
          </div>
        </div>
      </div>
    </article>
  )
}

function WorkTogetherSection() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <article className="rounded-lg border border-border bg-card p-6 shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card))] dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] lg:col-span-2">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">UI Kit</Badge>
            <h3 className="mt-4 text-3xl font-semibold">同一批次补齐道具和 UI</h3>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/68">少切工具，先把原型需要的图标、血条、按钮和对话面板做出来。素材和 UI 使用同一套队列与点数规则，结果统一进作品库。</p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs font-bold text-[hsl(var(--pix-charcoal))] dark:text-white/75">
            {['透明 PNG', 'Pixel Grid', 'ZIP 导出'].map((item) => <span key={item} className="rounded-lg border border-border bg-[hsl(var(--secondary))] px-3 py-2 dark:border-white/10 dark:bg-white/7">{item}</span>)}
          </div>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-4">
          {uiWorks.map((item) => <article key={item.name} className={`rounded-lg border border-border bg-card p-3 transition hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${item.span}`}><PixPreviewFrame url={item.src} className="min-h-32" /><p className="mt-3 text-sm font-semibold">{item.name}</p><p className="text-xs text-muted-foreground">{item.note}</p></article>)}
        </div>
      </article>

      <div className="grid gap-6">
        <article className="rounded-lg bg-[hsl(var(--pix-lavender))] p-6 text-[hsl(var(--pix-charcoal))]">
          <Badge variant="secondary">Sprite</Badge>
          <h3 className="mt-4 text-2xl font-semibold">动作帧可播放验收</h3>
          <div className="mt-5 grid place-items-center rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-6">
            <SpriteFramePlayer showcase={spriteShowcases[0]} className="h-28 w-28" />
          </div>
        </article>
        <article className="rounded-lg bg-[hsl(var(--pix-sky))] p-6 text-[hsl(var(--pix-charcoal))]">
          <Badge variant="info">Atlas</Badge>
          <h3 className="mt-4 text-2xl font-semibold">题材范例可追溯</h3>
          <div className="mt-5 grid grid-cols-2 gap-2">
            {featuredExamples.map((example) => <div key={example.id} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-2"><ItemSpriteGrid example={example} compact /><p className="mt-2 truncate text-xs font-semibold">{example.theme}</p></div>)}
          </div>
        </article>
      </div>
    </div>
  )
}

function StatRow() {
  return (
    <section className="border-y border-border bg-[hsl(var(--secondary))] px-4 py-12 md:px-8 dark:border-white/10 dark:bg-[hsl(var(--pix-dark-band))]">
      <div className="mx-auto max-w-7xl">
        <p className="mb-6 text-center text-xs font-semibold uppercase tracking-[.16em] text-muted-foreground dark:text-white/55">更高效率，更少工具</p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {statRowItems.map((item) => <div key={item.label} className="rounded-lg border border-border bg-background p-5 text-center transition hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-white/7 dark:hover:bg-white/10"><p className="text-xl opacity-50">{item.icon}</p><p className="mt-1 text-3xl font-semibold text-primary">{item.value}</p><p className="mt-1 text-sm text-muted-foreground dark:text-white/62">{item.label}</p></div>)}
        </div>
      </div>
    </section>
  )
}

function SpriteShowcaseList() {
  return <div className="grid gap-8">{spriteShowcases.map((showcase) => <SpriteShowcase key={showcase.name} showcase={showcase} />)}</div>
}

function SpriteShowcase({ showcase }: { showcase: typeof spriteShowcases[number] }) {
  const isDarkShowcase = showcase.tone.includes('text-white')
  const mutedTextClass = isDarkShowcase ? 'text-white/70' : 'text-[hsl(var(--pix-slate))]'
  const insetCardClass = isDarkShowcase ? 'border-white/12 bg-white/10' : 'border-[hsl(var(--pix-navy))]/15 bg-white/65'
  const statusBadgeClass = isDarkShowcase
    ? 'border-white/25 bg-white/10 text-white dark:border-white/25 dark:bg-white/10 dark:text-white'
    : 'border-[hsl(var(--pix-navy))]/20 bg-white/55 text-[hsl(var(--pix-navy))] dark:border-[hsl(var(--pix-navy))]/20 dark:bg-white/55 dark:text-[hsl(var(--pix-navy))]'
  return (
    <div className="grid items-center gap-8 lg:grid-cols-[.82fr_1.18fr]">
      <div className={`rounded-lg border border-border p-6 shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${showcase.tone}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Badge className="bg-[hsl(var(--pix-navy))] text-white">Sprite Pipeline</Badge>
            <h3 className="mt-5 text-3xl font-semibold">{showcase.name}</h3>
            <p className={`mt-3 text-sm leading-7 ${mutedTextClass}`}>{showcase.brief}</p>
          </div>
          <Badge variant="outline" className={statusBadgeClass}>{showcase.status}</Badge>
        </div>
        <div className={`mt-6 grid place-items-center rounded-lg border p-6 ${insetCardClass}`}>
          <SpriteFramePlayer showcase={showcase} className="h-24 w-24" />
        </div>
        <PromptBox title="中文 Prompt" text={showcase.prompt} tone={isDarkShowcase ? 'dark' : 'light'} />
      </div>
      <div className="grid gap-4">
        <div className="rounded-lg border border-border bg-card p-4 shadow-[0_1px_2px_rgba(15,15,15,0.04)]">
          <div className="mb-3 flex items-center justify-between gap-3"><p className="text-sm font-semibold">横向精灵图</p><Badge variant="outline">{showcase.frameCount} frames</Badge></div>
          <div className="pix-checkerboard overflow-hidden rounded-lg border border-border p-3">
            <img src={showcase.sheet} alt={`${showcase.name} 横向精灵图`} loading="lazy" decoding="async" className="h-20 w-full object-contain [image-rendering:pixelated]" />
          </div>
        </div>
        <div className="grid grid-cols-9 gap-1.5 rounded-lg border border-border bg-card p-4 shadow-[0_1px_2px_rgba(15,15,15,0.04)]">
          {showcase.frames.map((frame, index) => (
            <img key={frame} src={frame} alt={`${showcase.name} 第 ${index + 1} 帧`} loading="lazy" decoding="async" className="aspect-square w-full rounded-lg border border-border bg-muted/35 object-contain p-1 [image-rendering:pixelated]" />
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-border bg-card p-4"><p className="mb-2 text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{showcase.sourceLabel}</p><PixPreviewFrame url={showcase.source} className="min-h-44" /></div>
          <div className="rounded-lg border border-border bg-card p-4"><p className="mb-2 text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">序列帧播放</p><div className="pix-checkerboard grid min-h-44 place-items-center rounded-lg border border-border p-4"><SpriteFramePlayer showcase={showcase} className="h-32 w-32" /></div></div>
        </div>
      </div>
    </div>
  )
}

function SpriteFramePlayer({ showcase, className }: { showcase: typeof spriteShowcases[number]; className: string }) {
  const [frameIndex, setFrameIndex] = useState(0)
  useEffect(() => {
    showcase.frames.forEach((frame) => { const image = new Image(); image.src = frame })
    if (showcase.frames.length <= 1) return
    const timer = window.setInterval(() => setFrameIndex((value) => (value + 1) % showcase.frames.length), showcase.durationMs)
    return () => window.clearInterval(timer)
  }, [showcase.durationMs, showcase.frames])
  const frame = showcase.frames[frameIndex] ?? showcase.frames[0]
  return <img src={frame} alt={`${showcase.name} 序列帧播放预览`} className={`${className} object-contain [image-rendering:pixelated]`} draggable={false} />
}

function ExampleAtlas() {
  const [activeId, setActiveId] = useState(homepageExamples[0]?.id ?? '')
  const [floating, setFloating] = useState<{ example: HomepageExample; x: number; y: number } | null>(null)
  const activeExample = useMemo(() => homepageExamples.find((example) => example.id === activeId) ?? homepageExamples[0], [activeId])
  function showFloating(example: HomepageExample, x: number, y: number) { setActiveId(example.id); setFloating({ example, x, y }) }
  return (
    <div className="relative grid gap-6" onMouseLeave={() => setFloating(null)}>
      <div className="rounded-lg border border-border bg-[hsl(var(--pix-cream))] p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] md:p-8">
        <div className="grid items-center gap-6 lg:grid-cols-[.9fr_1.1fr]">
          <div><Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">Sample Atlas</Badge><h3 className="mt-5 text-3xl font-semibold md:text-5xl">题材不是列表，是可验收的样本墙</h3><p className="mt-4 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/66">每套范例包含一张透明物品精灵表和一张 1920×1080 UI 展示图。悬浮左侧卡片即可在鼠标旁展开详情。</p></div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">{examplesByCategory.map((group) => <button type="button" key={group.category} onClick={() => setActiveId(group.examples[0]?.id ?? activeId)} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/65 p-3 text-left transition hover:bg-white dark:border-white/10 dark:bg-white/7 dark:hover:bg-white/10"><p className="font-semibold">{group.category}</p><p className="text-xs text-[hsl(var(--pix-steel))] dark:text-white/55">{group.examples.length} 套范例</p></button>)}</div>
        </div>
      </div>
      <div className="grid gap-6">
        {examplesByCategory.map((group) => <div key={group.category}><div className="mb-4 flex items-end justify-between gap-3"><div><h3 className="text-3xl font-semibold">{group.category}</h3><p className="text-sm text-muted-foreground">{group.examples.length} 套物品 + UI 范例</p></div><Badge variant="outline">{group.examples[0]?.number}—{group.examples[group.examples.length - 1]?.number}</Badge></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">{group.examples.map((example) => <ExampleTile key={example.id} example={example} active={activeExample.id === example.id} onSelect={() => setActiveId(example.id)} onHover={(event) => showFloating(example, event.clientX, event.clientY)} />)}</div></div>)}
      </div>
      {floating && <ExampleFloatingDetail example={floating.example} x={floating.x} y={floating.y} />}
    </div>
  )
}

function ExampleTile({ example, active, onSelect, onHover }: { example: HomepageExample; active: boolean; onSelect: () => void; onHover: (event: MouseEvent<HTMLButtonElement>) => void }) {
  return <button type="button" onClick={onSelect} onMouseEnter={onHover} onMouseMove={onHover} className={`rounded-lg border bg-card p-3 text-left transition hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${active ? 'border-primary ring-2 ring-primary/15' : 'border-border'}`}><div className="pix-checkerboard rounded-lg p-2"><ItemSpriteGrid example={example} compact /></div><div className="mt-3 flex items-start justify-between gap-2"><div className="min-w-0"><p className="text-base font-semibold leading-tight">{example.theme}</p><p className="mt-1 text-xs text-muted-foreground">{example.category} · 物品 + UI</p></div><Badge variant="outline" className="shrink-0">{example.number}</Badge></div></button>
}

function ExampleFloatingDetail({ example, x, y }: { example: HomepageExample; x: number; y: number }) {
  const style = { left: Math.min(x + 22, window.innerWidth - 580), top: Math.min(y + 22, window.innerHeight - 640) }
  return <aside className="pointer-events-none fixed z-[90] grid w-[560px] max-w-[calc(100vw-32px)] gap-3 rounded-lg border border-border bg-card/96 p-4 shadow-[0_16px_48px_-8px_rgba(15,15,15,0.16)] backdrop-blur-xl" style={style}><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-primary">Pix 范例</p><h3 className="mt-1 text-2xl font-semibold">{example.number} · {example.theme}</h3><p className="text-sm text-muted-foreground">{example.category} / 8 个 64×64 物品 / 16:9 UI</p></div><Badge>{example.category}</Badge></div><div className="grid gap-3 sm:grid-cols-[.9fr_1.1fr]"><div className="pix-checkerboard rounded-lg border border-border p-3"><div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold">拆分物品格</p><Badge variant="outline">4×2</Badge></div><ItemSpriteGrid example={example} /></div><div className="overflow-hidden rounded-lg border border-border bg-muted"><img src={example.uiSrc} alt={`${example.theme} 像素 UI 展示图`} loading="lazy" decoding="async" className="h-full min-h-44 w-full object-cover [image-rendering:pixelated]" /></div></div><PromptBox title="物品 Prompt" text={buildChineseItemPrompt(example)} /><PromptBox title="UI Prompt" text={buildChineseUiPrompt(example)} /></aside>
}

function ItemSpriteGrid({ example, compact = false }: { example: HomepageExample; compact?: boolean }) {
  return <div className="grid grid-cols-4 gap-1">{itemSpriteSlots.map((index) => <div key={index} className={`aspect-square overflow-hidden rounded-lg border border-border bg-card ${compact ? 'p-0.5' : 'p-1'}`}><img src={itemSlotSrc(example, index)} alt={`${example.theme} 第 ${index + 1} 个物品`} loading="lazy" decoding="async" className="h-full w-full object-contain [image-rendering:pixelated]" /></div>)}</div>
}

function PromptBox({ title, text, tone = 'default' }: { title: string; text: string; tone?: 'default' | 'light' | 'dark' }) {
  const boxClass = tone === 'dark'
    ? 'border-white/12 bg-white/7 text-white/70'
    : tone === 'light'
      ? 'border-[hsl(var(--pix-navy))]/15 bg-white/55 text-[hsl(var(--pix-slate))]'
      : 'border-border bg-muted/40 text-muted-foreground'
  const titleClass = tone === 'dark' ? 'text-white/65' : tone === 'light' ? 'text-[hsl(var(--pix-steel))]' : 'text-muted-foreground'
  return <div className={`mt-4 rounded-lg border p-3 ${boxClass}`}><p className={`text-xs font-semibold uppercase tracking-[.12em] ${titleClass}`}>{title}</p><p className="mt-2 text-xs leading-6">{text}</p></div>
}

function AuthSection({ authSlot }: { authSlot: ReactNode }) {
  return (
    <section id="auth-panel" className="scroll-mt-28 border-t border-border bg-[hsl(var(--secondary))] px-4 py-16 md:px-8 md:py-20 dark:border-white/10 dark:bg-[hsl(var(--pix-navy-deep))]">
      <div className="mx-auto grid max-w-7xl items-center gap-10 rounded-lg bg-card p-6 shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card))] dark:shadow-[0_30px_80px_-46px_rgba(0,0,0,0.9)] md:p-10 lg:grid-cols-[.9fr_1.1fr]">
        <div>
          <Badge>开始生产</Badge>
          <h2 className="mt-5 font-sans text-4xl font-semibold tracking-tight md:text-6xl">进入像素工位台</h2>
          <p className="mt-5 max-w-xl text-base leading-8 text-muted-foreground">创建单图或素材包，完成后在作品库挑选、重试、打包导出。</p>
          <div className="mt-6 flex flex-wrap gap-3"><Button asChild><a href="#auth-panel">登录</a></Button><Button variant="outline" asChild><a href="#workflow">看优势</a></Button></div>
        </div>
        <div>{authSlot}</div>
      </div>
    </section>
  )
}

function SectionFrame({ id, eyebrow, title, description, children, surface = 'default' }: { id: string; eyebrow: string; title: string; description: string; children: ReactNode; surface?: 'default' | 'soft' }) {
  const frameClass = surface === 'soft' ? 'bg-[hsl(var(--secondary))] dark:bg-[hsl(var(--pix-dark-band))]' : 'bg-background dark:bg-[hsl(var(--pix-navy-deep))]'
  return (
    <section id={id} className={`scroll-mt-28 px-4 py-16 md:px-8 md:py-24 ${frameClass}`}>
      <div className="mx-auto max-w-7xl">
        <div className="mb-10">
          <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-primary dark:text-[hsl(var(--pix-brand-purple-300))]">{eyebrow}</p>
          <h2 className="mt-3 max-w-4xl font-sans text-4xl font-semibold tracking-tight md:text-6xl dark:text-white">{title}</h2>
          <p className="mt-4 max-w-3xl text-base leading-8 text-muted-foreground dark:text-white/66">{description}</p>
        </div>
        {children}
      </div>
    </section>
  )
}

function itemSlotSrc(example: HomepageExample, index: number) { return example.itemSrc.replace('.png', `_${String(index + 1).padStart(2, '0')}.png`) }
function buildChineseItemPrompt(example: HomepageExample) { return `像素风「${example.theme}」物品素材表，拆成 4×2 共 8 个独立道具格；每个物品独立输出为 64×64 透明 PNG，居中构图、硬边像素、有限调色板、无抗锯齿，适合作为背包图标或掉落物素材。` }
function buildChineseUiPrompt(example: HomepageExample) { return `像素风「${example.theme}」16:9 UI 展示图，包含主题面板、边框、按钮、图标、状态区和游戏界面示例；整体为 16-bit RPG / 独立游戏可用风格。` }
