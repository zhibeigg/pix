import { useMemo, useState, type ReactNode } from 'react'
import { homepageExampleCategories, homepageExamples, type HomepageExample } from '../homepageExamples'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { PixPreviewFrame } from './pix/PixPreviewFrame'

const advantageProofs = [
  { label: '工程图', title: '不只给一张图', body: '源图、Pixel Grid、透明 PNG、预览与 meta 一起归档，便于复查和返修。', mark: 'JSON', tone: 'bg-[hsl(var(--pix-lavender)/.62)]' },
  { label: '批量包', title: '按素材包生产', body: '一组素材统一入队；失败项单独重试，成功项直接打包下载。', mark: 'ZIP', tone: 'bg-[hsl(var(--pix-mint)/.58)]' },
  { label: '小尺寸', title: '交付前先验收', body: '16×16、32×32 关注轮廓和色板，不把大图粗暴缩小当成像素资产。', mark: '16', tone: 'bg-[hsl(var(--pix-sky)/.62)]' },
]

const pipelineProofs = [
  { step: '01', title: '定规格', body: '名称、尺寸、颜色数、透明背景进入同一张任务单。' },
  { step: '02', title: '跑流水线', body: '图像模型、Grid 提取、像素化与后处理串联。' },
  { step: '03', title: '验收导出', body: '查看结果、点数、失败原因，再决定重试或下载。' },
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

const spriteShowcase = {
  name: '月刃骑士挥剑',
  status: '9 帧',
  prompt: '月刃骑士挥剑三段斩，银蓝盔甲小角色，侧身站姿，连续挥剑动作，适合 RPG 战斗序列帧，透明背景，像素动画精灵',
  brief: 'Pix sprite 全流程输出：3×3 生图 → 9 帧切分 → 共享调色板像素化 → 横向精灵图 + GIF。',
  source: '/hero-sprites/pipeline/moonblade-knight-source.png',
  sheet: '/hero-sprites/pipeline/moonblade-knight-sheet.png',
  gif: '/hero-sprites/pipeline/moonblade-knight.gif',
  frameCount: 9,
  durationMs: 120,
  frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/moonblade-knight-frame-${String(index + 1).padStart(2, '0')}.png`),
}

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

type LandingSectionsProps = { authSlot: ReactNode }

export function LandingSections({ authSlot }: LandingSectionsProps) {
  return (
    <>
      <SectionFrame id="workflow" eyebrow="核心优势" title="不是 AI 生图相册，是像素素材生产线" description="Pix 的重点不是把 prompt 变成一张好看的图，而是把一批想法变成可检查、可重试、可导出的游戏素材。">
        <div className="grid items-stretch gap-6 lg:grid-cols-[.92fr_1.08fr]">
          <div className="flex min-h-[410px] flex-col justify-between rounded-[2rem] border border-border bg-card p-6 shadow-xl md:p-8">
            <div>
              <Badge className="bg-[hsl(var(--pix-navy))] text-white">为什么是 Pix</Badge>
              <h3 className="mt-5 max-w-xl text-3xl font-black tracking-tight md:text-5xl">从“生成图片”推进到“交付素材”</h3>
              <p className="mt-5 max-w-2xl text-base leading-8 text-muted-foreground">普通 AI 图像工具停在预览图。Pix 把源图、像素工程图、透明 PNG、任务状态、失败重试和 ZIP 导出放在同一条流水线里，适合独立游戏和 RPG 素材包快速打样。</p>
            </div>
            <div className="mt-8 grid grid-cols-3 gap-3">
              {pipelineProofs.map((item) => <div key={item.step} className="rounded-2xl border border-border bg-muted/40 p-3"><p className="text-xs font-black text-primary">{item.step}</p><p className="mt-2 font-bold">{item.title}</p><p className="mt-1 hidden text-xs leading-5 text-muted-foreground sm:block">{item.body}</p></div>)}
            </div>
          </div>
          <div className="grid gap-4 lg:grid-rows-3">
            {advantageProofs.map((item) => <article key={item.title} className={`rounded-[2rem] border border-border p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-xl ${item.tone}`}><div className="grid grid-cols-[56px_minmax(0,1fr)] items-center gap-4"><div className="grid h-14 w-14 place-items-center rounded-2xl border border-border bg-card font-black">{item.mark}</div><div><p className="text-xs font-bold uppercase tracking-[.12em] text-muted-foreground">{item.label}</p><h3 className="mt-1 text-xl font-black">{item.title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p></div></div></article>)}
          </div>
        </div>
      </SectionFrame>

      <StatRow />

      <SectionFrame id="pixel-ui" eyebrow="像素 UI" title="道具和界面一起做" description="图标、HUD、按钮、面板可以放进同一批素材里；先把原型需要的交互表面补齐。">
        <div className="grid items-center gap-8 lg:grid-cols-[.78fr_1.22fr]">
          <div className="rounded-[2rem] border border-border bg-card p-7 shadow-sm">
            <Badge className="bg-[hsl(var(--pix-navy))] text-white">UI Kit</Badge>
            <h3 className="mt-5 text-3xl font-black">同一批次补齐道具和 UI</h3>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">少切工具，先把原型需要的图标、血条、按钮和对话面板做出来。素材和 UI 使用同一套队列与点数规则，结果统一进作品库。</p>
            <div className="mt-6 grid grid-cols-3 gap-2">{['透明 PNG', 'Pixel Grid', 'ZIP 导出'].map((item) => <div key={item} className="rounded-xl border border-border bg-muted/40 p-3 text-xs font-bold">{item}</div>)}</div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            {uiWorks.map((item) => <article key={item.name} className={`rounded-2xl border border-border bg-card p-3 transition hover:-translate-y-1 hover:shadow-xl ${item.span}`}><PixPreviewFrame url={item.src} className="min-h-32" /><p className="mt-3 text-sm font-black">{item.name}</p><p className="text-xs text-muted-foreground">{item.note}</p></article>)}
          </div>
        </div>
      </SectionFrame>

      <SectionFrame id="sprite-preview" eyebrow="序列帧" title="角色动作也能做成可播放的精灵图" description="九宫格源图会切成帧、统一调色板像素化，并导出横向精灵图与 GIF 预览。">
        <SpriteShowcase />
      </SectionFrame>

      <SectionFrame id="examples" eyebrow="范例图库" title="76 套题材范例，像首屏一样悬浮验收" description="默认用紧凑素材格展示题材边界；选择题材后拆开 8 个物品格，并展开 16:9 UI 展示图、中文 Prompt 和文件名。">
        <ExampleAtlas />
      </SectionFrame>

      <section id="auth-panel" className="scroll-mt-28 border-t border-border bg-muted/35 px-4 py-16 md:px-8 md:py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-[.9fr_1.1fr]">
          <div>
            <Badge>开始生产</Badge>
            <h2 className="mt-5 font-serif text-4xl font-black tracking-tight md:text-6xl">进入像素工位台</h2>
            <p className="mt-5 max-w-xl text-base leading-8 text-muted-foreground">创建单图或素材包，完成后在作品库挑选、重试、打包导出。</p>
            <div className="mt-6 flex flex-wrap gap-3"><Button asChild><a href="#auth-panel">登录</a></Button><Button variant="outline" asChild><a href="#workflow">看优势</a></Button></div>
          </div>
          <div>{authSlot}</div>
        </div>
      </section>
    </>
  )
}

function StatRow() {
  return <section className="border-y border-border bg-card/70 px-4 py-12 md:px-8"><div className="mx-auto max-w-6xl"><p className="mb-6 text-center text-xs font-black uppercase tracking-[.16em] text-muted-foreground">更高效率，更少工具</p><div className="grid grid-cols-2 gap-3 md:grid-cols-4">{statRowItems.map((item) => <div key={item.label} className="rounded-2xl border border-border bg-background p-5 text-center transition hover:-translate-y-1 hover:shadow-lg"><p className="text-xl opacity-50">{item.icon}</p><p className="mt-1 text-3xl font-black text-primary">{item.value}</p><p className="mt-1 text-sm text-muted-foreground">{item.label}</p></div>)}</div></div></section>
}

function SpriteShowcase() {
  const sheetWidth = spriteShowcase.frameCount * 96
  return (
    <div className="grid items-center gap-8 lg:grid-cols-[.82fr_1.18fr]">
      <div className="rounded-[2rem] border border-border bg-[hsl(var(--pix-lavender)/.55)] p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Badge className="bg-[hsl(var(--pix-navy))] text-white">Sprite Pipeline</Badge>
            <h3 className="mt-5 text-3xl font-black">{spriteShowcase.name}</h3>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">{spriteShowcase.brief}</p>
          </div>
          <Badge variant="outline">{spriteShowcase.status}</Badge>
        </div>
        <div className="mt-6 grid place-items-center rounded-3xl border border-border bg-card p-6">
          <div
            role="img"
            aria-label={`${spriteShowcase.name} 序列帧播放预览`}
            className="h-24 w-24 [image-rendering:pixelated]"
            style={{
              backgroundImage: `url(${spriteShowcase.sheet})`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: '0 0',
              backgroundSize: `${sheetWidth}px 96px`,
              animation: `spriteFrameRun ${spriteShowcase.frameCount * spriteShowcase.durationMs}ms steps(${spriteShowcase.frameCount}, end) infinite`,
            }}
          />
        </div>
        <PromptBox title="中文 Prompt" text={spriteShowcase.prompt} />
      </div>
      <div className="grid gap-4">
        <div className="rounded-[2rem] border border-border bg-card p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between gap-3"><p className="text-sm font-black">横向精灵图</p><Badge variant="outline">9 frames</Badge></div>
          <div className="pix-checkerboard overflow-hidden rounded-2xl border border-border p-3">
            <img src={spriteShowcase.sheet} alt={`${spriteShowcase.name} 横向精灵图`} loading="lazy" decoding="async" className="h-20 w-full object-contain [image-rendering:pixelated]" />
          </div>
        </div>
        <div className="grid grid-cols-9 gap-1.5 rounded-[2rem] border border-border bg-card p-4 shadow-sm">
          {spriteShowcase.frames.map((frame, index) => (
            <img key={frame} src={frame} alt={`${spriteShowcase.name} 第 ${index + 1} 帧`} loading="lazy" decoding="async" className="aspect-square w-full rounded-lg border border-border bg-muted/35 object-contain p-1 [image-rendering:pixelated]" />
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-border bg-card p-4"><p className="mb-2 text-xs font-black uppercase tracking-[.12em] text-muted-foreground">3×3 源图</p><PixPreviewFrame url={spriteShowcase.source} className="min-h-44" /></div>
          <div className="rounded-2xl border border-border bg-card p-4"><p className="mb-2 text-xs font-black uppercase tracking-[.12em] text-muted-foreground">GIF 预览</p><PixPreviewFrame url={spriteShowcase.gif} className="min-h-44" /></div>
        </div>
      </div>
    </div>
  )
}

function ExampleAtlas() {
  const [activeId, setActiveId] = useState(homepageExamples[0]?.id ?? '')
  const activeExample = useMemo(() => homepageExamples.find((example) => example.id === activeId) ?? homepageExamples[0], [activeId])
  return (
    <div className="grid gap-6">
      <div className="rounded-[2rem] border border-border bg-[hsl(var(--pix-navy))] p-6 text-white shadow-xl md:p-8">
        <div className="grid items-center gap-6 lg:grid-cols-[.9fr_1.1fr]">
          <div><Badge className="bg-[hsl(var(--pix-amber))] text-foreground">Sample Atlas</Badge><h3 className="mt-5 text-3xl font-black md:text-5xl">题材不是列表，是可验收的样本墙</h3><p className="mt-4 max-w-2xl text-sm leading-7 text-white/68">每套范例包含一张透明物品精灵表和一张 1920×1080 UI 展示图。默认轻量浏览，需要细节时把物品拆成 8 个独立格逐个验收。</p></div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">{examplesByCategory.map((group) => <button type="button" key={group.category} onClick={() => setActiveId(group.examples[0]?.id ?? activeId)} className="rounded-2xl border border-white/12 bg-white/7 p-3 text-left transition hover:bg-white/12"><p className="font-black">{group.category}</p><p className="text-xs text-white/55">{group.examples.length} 套范例</p></button>)}</div>
        </div>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,520px)]">
        <div className="grid gap-6">
          {examplesByCategory.map((group) => <div key={group.category}><div className="mb-3 flex items-end justify-between gap-3"><div><h3 className="text-2xl font-black">{group.category}</h3><p className="text-sm text-muted-foreground">{group.examples.length} 套物品 + UI 范例</p></div><Badge variant="outline">{group.examples[0]?.number}—{group.examples[group.examples.length - 1]?.number}</Badge></div><div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">{group.examples.map((example) => <ExampleTile key={example.id} example={example} active={activeExample.id === example.id} onSelect={() => setActiveId(example.id)} />)}</div></div>)}
        </div>
        {activeExample && <ExampleDetail example={activeExample} />}
      </div>
    </div>
  )
}

function ExampleTile({ example, active, onSelect }: { example: HomepageExample; active: boolean; onSelect: () => void }) {
  return <button type="button" onClick={onSelect} onMouseEnter={onSelect} className={`rounded-2xl border bg-card p-2 text-left transition hover:-translate-y-1 hover:shadow-xl ${active ? 'border-primary ring-2 ring-primary/15' : 'border-border'}`}><div className="pix-checkerboard rounded-xl p-2"><ItemSpriteGrid example={example} compact /></div><div className="mt-2 flex items-center justify-between gap-2"><p className="truncate text-xs font-black">{example.theme}</p><Badge variant="outline" className="shrink-0">{example.number}</Badge></div><p className="truncate text-xs text-muted-foreground">{example.category} · 物品 + UI</p></button>
}

function ExampleDetail({ example }: { example: HomepageExample }) {
  return <aside className="sticky top-24 grid gap-3 rounded-[2rem] border border-border bg-card p-4 shadow-xl"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-[.14em] text-primary">Pix 范例</p><h3 className="mt-1 text-2xl font-black">{example.number} · {example.theme}</h3><p className="text-sm text-muted-foreground">{example.category} / 8 个 64×64 物品 / 16:9 UI</p></div><Badge>{example.category}</Badge></div><div className="grid gap-3 sm:grid-cols-[.9fr_1.1fr]"><div className="rounded-2xl border border-border pix-checkerboard p-3"><div className="mb-2 flex items-center justify-between"><p className="text-xs font-black">拆分物品格</p><Badge variant="outline">4×2</Badge></div><ItemSpriteGrid example={example} /></div><div className="overflow-hidden rounded-2xl border border-border bg-muted"><img src={example.uiSrc} alt={`${example.theme} 像素 UI 展示图`} loading="lazy" decoding="async" className="h-full min-h-44 w-full object-cover [image-rendering:pixelated]" /></div></div><PromptBox title="物品 Prompt" text={buildChineseItemPrompt(example)} /><PromptBox title="UI Prompt" text={buildChineseUiPrompt(example)} /><div className="grid grid-cols-2 gap-2"><FilePill label="item" value={example.itemFile} /><FilePill label="ui" value={example.uiFile} /></div></aside>
}

function ItemSpriteGrid({ example, compact = false }: { example: HomepageExample; compact?: boolean }) {
  return <div className="grid grid-cols-4 gap-1">{itemSpriteSlots.map((index) => <div key={index} className={`aspect-square overflow-hidden rounded-lg border border-border bg-card ${compact ? 'p-0.5' : 'p-1'}`}><img src={itemSlotSrc(example, index)} alt={`${example.theme} 第 ${index + 1} 个物品`} loading="lazy" decoding="async" className="h-full w-full object-contain [image-rendering:pixelated]" /></div>)}</div>
}

function PromptBox({ title, text }: { title: string; text: string }) { return <div className="rounded-2xl border border-border bg-muted/40 p-3"><p className="text-xs font-black uppercase tracking-[.12em] text-muted-foreground">{title}</p><p className="mt-2 text-xs leading-6 text-muted-foreground">{text}</p></div> }
function FilePill({ label, value }: { label: string; value: string }) { return <div className="min-w-0 rounded-xl border border-border bg-muted/30 px-3 py-2"><p className="text-[11px] text-muted-foreground">{label}</p><code className="block truncate text-xs">{value}</code></div> }
function itemSlotSrc(example: HomepageExample, index: number) { return example.itemSrc.replace('.png', `_${String(index + 1).padStart(2, '0')}.png`) }
function buildChineseItemPrompt(example: HomepageExample) { return `像素风「${example.theme}」物品素材表，拆成 4×2 共 8 个独立道具格；每个物品独立输出为 64×64 透明 PNG，居中构图、硬边像素、有限调色板、无抗锯齿，适合作为背包图标或掉落物素材。` }
function buildChineseUiPrompt(example: HomepageExample) { return `像素风「${example.theme}」16:9 UI 展示图，包含主题面板、边框、按钮、图标、状态区和游戏界面示例；整体为 16-bit RPG / 独立游戏可用风格。` }

function SectionFrame({ id, eyebrow, title, description, children }: { id: string; eyebrow: string; title: string; description: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-28 bg-card/45 px-4 py-16 md:px-8 md:py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10">
          <p className="text-xs font-black uppercase tracking-[.16em] text-primary">{eyebrow}</p>
          <h2 className="mt-3 max-w-4xl font-serif text-4xl font-black tracking-tight md:text-6xl">{title}</h2>
          <p className="mt-4 max-w-3xl text-base leading-8 text-muted-foreground">{description}</p>
        </div>
        {children}
      </div>
    </section>
  )
}
