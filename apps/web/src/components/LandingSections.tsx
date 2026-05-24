import { memo, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode, type Ref } from 'react'
import { useI18n } from '../i18n'
import { homepageExampleCategories, homepageExamples, getHomepageExampleLabel, type HomepageExample } from '../homepageExamples'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { PixPreviewFrame } from './pix/PixPreviewFrame'

const spriteShowcases = [
  {
    name: '月刃骑士挥剑',
    nameEn: 'Moonblade knight slash',
    status: '9 帧',
    statusEn: '9 frames',
    prompt: '月刃骑士挥剑三段斩，银蓝盔甲小角色，侧身站姿，连续挥剑动作，适合 RPG 战斗序列帧，透明背景，像素动画精灵',
    promptEn: 'Moonblade knight three-hit slash, silver-blue armored small character, side stance, continuous sword motion for RPG combat animation frames, transparent background, pixel animated sprite.',
    brief: 'Pix sprite 全流程输出：3×3 生图 → 9 帧切分 → 共享调色板像素化 → 横向精灵图 + 序列帧播放。',
    briefEn: 'Full Pix sprite pipeline: 3×3 source image → 9 frame split → shared-palette pixelization → horizontal sprite sheet + frame playback.',
    source: '/hero-sprites/pipeline/moonblade-knight-source.png',
    sourceLabel: '3×3 源图',
    sourceLabelEn: '3×3 source',
    sheet: '/hero-sprites/pipeline/moonblade-knight-sheet.png',
    frameCount: 9,
    durationMs: 120,
    tone: 'bg-[hsl(var(--pix-lavender))] text-[hsl(var(--pix-charcoal))] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)]',
    frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/moonblade-knight-frame-${String(index + 1).padStart(2, '0')}.png`),
  },
  {
    name: '黑紫魔气爆炸特效',
    nameEn: 'Black-purple magic burst VFX',
    status: '9 帧特效',
    statusEn: '9-frame VFX',
    prompt: '黑紫魔气爆炸特效，64×64 low-detail pixel art VFX，暗紫能量核心、黑色烟雾外扩、九帧爆发消散，透明背景，适合技能命中特效',
    promptEn: 'Black-purple magic explosion VFX, 64×64 low-detail pixel art, dark purple energy core, black smoke expansion, nine-frame burst and fade, transparent background, suitable for skill hit effects.',
    brief: '9 帧 64×64 像素特效：单帧 PNG → 横向精灵图 → 序列帧播放，可直接用于技能爆炸/魔法命中动画。',
    briefEn: '9-frame 64×64 pixel VFX: single-frame PNGs → horizontal sprite sheet → frame playback, ready for skill explosions or magic hit animations.',
    source: '/hero-sprites/pipeline/dark-purple-magic-explosion-source.png',
    sourceLabel: '3×3 帧源图',
    sourceLabelEn: '3×3 frame source',
    sheet: '/hero-sprites/pipeline/dark-purple-magic-explosion-sheet.png',
    frameCount: 9,
    durationMs: 90,
    tone: 'bg-[hsl(var(--pix-rose))] text-[hsl(var(--pix-charcoal))] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)]',
    frames: Array.from({ length: 9 }, (_, index) => `/hero-sprites/pipeline/dark-purple-magic-explosion-frame-${String(index + 1).padStart(2, '0')}.png`),
  },
]

const itemSpriteSlots = Array.from({ length: 8 }, (_, index) => index)
type ItemSpriteVariant = 'original64' | 'outline32'

const examplesByCategory = homepageExampleCategories.map((category) => ({
  category,
  examples: homepageExamples.filter((example) => example.category === category),
}))

const featuredExamples = homepageExamples.slice(0, 4)

type LandingSectionsProps = { authSlot: ReactNode }

export function LandingSections({ authSlot }: LandingSectionsProps) {
  const { text } = useI18n()
  return (
    <>
      <SectionFrame id="pixel-ui" eyebrow={text('统一验收', 'Bring work together')} title={text('道具、UI 和动作帧在同一个素材工作区里验收', 'Review items, UI, and motion frames in one asset workspace')} description={text('图标、HUD、按钮、面板、角色动作和技能特效可以放进同一批素材；先把原型需要的交互表面补齐。', 'Icons, HUDs, buttons, panels, character actions, and skill VFX can live in the same batch so prototypes get the surfaces they need first.')}>
        <WorkTogetherSection />
      </SectionFrame>

      <SectionFrame id="sprite-preview" surface="soft" eyebrow={text('精灵图流水线', 'Sprite pipeline')} title={text('角色动作和技能特效都能做成可播放的精灵图', 'Character actions and skill VFX become playable sprite sheets')} description={text('九宫格源图或单帧序列会切成帧、统一调色板像素化，并导出横向精灵图与真实序列帧播放。', '3×3 sources or single-frame sequences are split, palette-aligned, pixelized, and exported as horizontal sheets with real frame playback.')}>
        <SpriteShowcaseList />
      </SectionFrame>

      <SectionFrame id="examples" eyebrow={text('范例图谱', 'Sample atlas')} title={text('76 套题材范例，像首屏一样悬浮验收', '76 sample themes with hover-to-review details')} description={text('默认同时展示原 64×64 资源和新 32×32 outline 图标；选择题材后拆开两套物品格，并展开 16:9 UI 展示图和当前语言提示词。', 'Show both original 64×64 resources and new 32×32 outline icons by default; selecting a theme opens both item sets, a 16:9 UI showcase, and localized prompts.')}>
        <ExampleAtlas />
      </SectionFrame>

      <AuthSection authSlot={authSlot} />
    </>
  )
}

function WorkTogetherSection() {
  const { language, text } = useI18n()
  const uiWorks = [
    { name: text('背包格', 'Inventory slot'), src: '/hero-ui/inventory-slot.png', note: text('物品栏 / 装备槽', 'Inventory / Equipment'), span: 'sm:col-span-1' },
    { name: text('技能按钮', 'Skill button'), src: '/hero-ui/skill-button.png', note: text('技能栏 / 快捷键', 'Skill bar / Hotkey'), span: 'sm:col-span-1' },
    { name: text('生命条', 'Health bar'), src: '/hero-ui/health-bar.png', note: text('HUD / 战斗状态', 'HUD / Combat state'), span: 'sm:col-span-2' },
    { name: text('对话框', 'Dialog panel'), src: '/hero-ui/dialog-panel.png', note: text('NPC 对话 / 提示窗', 'NPC dialog / Prompt'), span: 'sm:col-span-2' },
    { name: text('任务牌', 'Quest card'), src: '/hero-ui/quest-card.png', note: text('任务列表 / 公告板', 'Quest list / Board'), span: 'sm:col-span-2' },
    { name: text('金币计数器', 'Coin counter'), src: '/hero-ui/coin-counter.png', note: text('经济系统 / 商店', 'Economy / Shop'), span: 'sm:col-span-2' },
    { name: text('菜单标签', 'Menu tab'), src: '/hero-ui/menu-tab.png', note: text('页签 / 设置面板', 'Tabs / Settings'), span: 'sm:col-span-2' },
    { name: text('确认勾选', 'Check toggle'), src: '/hero-ui/check-toggle.png', note: text('开关 / 选项状态', 'Toggle / Option state'), span: 'sm:col-span-1' },
  ]
  const chips = [text('透明 PNG', 'Transparent PNG'), text('像素网格', 'Pixel grid'), text('ZIP 导出', 'ZIP export')]
  return (
    <div className="grid gap-6 lg:grid-cols-3 lg:items-start">
      <article className="rounded-lg border border-border bg-card p-6 shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card))] dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] lg:col-span-2">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">{text('界面套件', 'UI kit')}</Badge>
            <h3 className="mt-4 text-3xl font-semibold">{text('同一批次补齐道具和界面', 'Complete items and UI in one batch')}</h3>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/68">{text('少切工具，先把原型需要的图标、血条、按钮和对话面板做出来。素材和界面使用同一套队列与点数规则，结果统一进作品库。', 'Switch tools less: create icons, health bars, buttons, and dialog panels needed by the prototype first. Assets and UI share the same queue and credit rules, then land in the gallery.')}</p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs font-bold text-[hsl(var(--pix-charcoal))] dark:text-white/75">
            {chips.map((item) => <span key={item} className="rounded-lg border border-border bg-[hsl(var(--secondary))] px-3 py-2 dark:border-white/10 dark:bg-white/7">{item}</span>)}
          </div>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-4">
          {uiWorks.map((item) => <article key={item.name} className={`rounded-lg border border-border bg-card p-3 transition hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${item.span}`}><PixPreviewFrame url={item.src} className="min-h-32" /><p className="mt-3 text-sm font-semibold">{item.name}</p><p className="text-xs text-muted-foreground">{item.note}</p></article>)}
        </div>
      </article>

      <div className="grid gap-4 lg:self-start">
        <article className="rounded-lg bg-[hsl(var(--pix-lavender))] p-5 text-[hsl(var(--pix-charcoal))] dark:border dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)]">
          <Badge variant="secondary">{text('精灵帧', 'Sprite')}</Badge>
          <h3 className="mt-4 text-xl font-semibold">{text('动作帧可播放验收', 'Playable action-frame review')}</h3>
          <div className="mt-4 grid h-32 place-items-center rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-4 dark:border-white/12 dark:bg-white/7">
            <SpriteFramePlayer showcase={spriteShowcases[0]} className="h-24 w-24" />
          </div>
        </article>
        <article className="rounded-lg bg-[hsl(var(--pix-sky))] p-5 text-[hsl(var(--pix-charcoal))] dark:border dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)]">
          <Badge variant="info">{text('图谱', 'Atlas')}</Badge>
          <h3 className="mt-4 text-xl font-semibold">{text('题材范例可追溯', 'Traceable theme samples')}</h3>
          <div className="mt-4 grid grid-cols-2 gap-2">
            {featuredExamples.map((example) => <div key={example.id} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-2 dark:border-white/10 dark:bg-white/7"><ItemVariantPair example={example} compact /><p className="mt-2 truncate text-xs font-semibold">{getHomepageExampleLabel(example, language).theme}</p></div>)}
          </div>
        </article>
      </div>
    </div>
  )
}

function SpriteShowcaseList() {
  return <div className="grid gap-8">{spriteShowcases.map((showcase) => <SpriteShowcase key={showcase.name} showcase={showcase} />)}</div>
}

function SpriteShowcase({ showcase }: { showcase: typeof spriteShowcases[number] }) {
  const { text } = useI18n()
  const name = text(showcase.name, showcase.nameEn)
  const status = text(showcase.status, showcase.statusEn)
  const prompt = text(showcase.prompt, showcase.promptEn)
  const brief = text(showcase.brief, showcase.briefEn)
  const sourceLabel = text(showcase.sourceLabel, showcase.sourceLabelEn)
  const mutedTextClass = 'text-[hsl(var(--pix-slate))] dark:text-white/70'
  const insetCardClass = 'border-[hsl(var(--pix-navy))]/15 bg-white/65 dark:border-white/12 dark:bg-white/7'
  const statusBadgeClass = 'border-[hsl(var(--pix-navy))]/20 bg-white/55 text-[hsl(var(--pix-navy))] dark:border-white/20 dark:bg-white/7 dark:text-white'
  return (
    <div className="grid items-center gap-8 lg:grid-cols-[.82fr_1.18fr]">
      <div className={`rounded-lg border border-border p-6 shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${showcase.tone}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">{text('精灵图流水线', 'Sprite pipeline')}</Badge>
            <h3 className="mt-5 text-3xl font-semibold">{name}</h3>
            <p className={`mt-3 text-sm leading-7 ${mutedTextClass}`}>{brief}</p>
          </div>
          <Badge variant="outline" className={statusBadgeClass}>{status}</Badge>
        </div>
        <div className={`mt-6 grid place-items-center rounded-lg border p-6 ${insetCardClass}`}>
          <SpriteFramePlayer showcase={showcase} className="h-24 w-24" />
        </div>
        <PromptBox title={text('中文提示词', 'English prompt')} text={prompt} tone="light" />
      </div>
      <div className="grid gap-4">
        <div className="rounded-lg border border-border bg-card p-4 shadow-[0_1px_2px_rgba(15,15,15,0.04)]">
          <div className="mb-3 flex items-center justify-between gap-3"><p className="text-sm font-semibold">{text('横向精灵图', 'Horizontal sprite sheet')}</p><Badge variant="outline">{text(`${showcase.frameCount} 帧`, `${showcase.frameCount} frames`)}</Badge></div>
          <div className="pix-checkerboard overflow-hidden rounded-lg border border-border p-3">
            <img src={showcase.sheet} alt={text(`${showcase.name} 横向精灵图`, `${showcase.nameEn} horizontal sprite sheet`)} loading="lazy" decoding="async" className="h-20 w-full object-contain [image-rendering:pixelated]" />
          </div>
        </div>
        <div className="grid grid-cols-9 gap-1.5 rounded-lg border border-border bg-card p-4 shadow-[0_1px_2px_rgba(15,15,15,0.04)]">
          {showcase.frames.map((frame, index) => (
            <img key={frame} src={frame} alt={text(`${showcase.name} 第 ${index + 1} 帧`, `${showcase.nameEn} frame ${index + 1}`)} loading="lazy" decoding="async" className="aspect-square w-full rounded-lg border border-border bg-muted/35 object-contain p-1 [image-rendering:pixelated]" />
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-border bg-card p-4"><p className="mb-2 text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{sourceLabel}</p><PixPreviewFrame url={showcase.source} className="min-h-44" /></div>
          <div className="rounded-lg border border-border bg-card p-4"><p className="mb-2 text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('序列帧播放', 'Frame playback')}</p><div className="pix-checkerboard grid min-h-44 place-items-center rounded-lg border border-border p-4"><SpriteFramePlayer showcase={showcase} className="h-32 w-32" /></div></div>
        </div>
      </div>
    </div>
  )
}

function SpriteFramePlayer({ showcase, className }: { showcase: typeof spriteShowcases[number]; className: string }) {
  const { text } = useI18n()
  const [frameIndex, setFrameIndex] = useState(0)
  useEffect(() => {
    showcase.frames.forEach((frame) => { const image = new Image(); image.src = frame })
    if (showcase.frames.length <= 1) return
    const timer = window.setInterval(() => setFrameIndex((value) => (value + 1) % showcase.frames.length), showcase.durationMs)
    return () => window.clearInterval(timer)
  }, [showcase.durationMs, showcase.frames])
  const frame = showcase.frames[frameIndex] ?? showcase.frames[0]
  return <img src={frame} alt={text(`${showcase.name} 序列帧播放预览`, `${showcase.nameEn} frame playback preview`)} className={`${className} object-contain [image-rendering:pixelated]`} draggable={false} />
}

function ExampleAtlas() {
  const { language, text } = useI18n()
  const [activeId, setActiveId] = useState(homepageExamples[0]?.id ?? '')
  const [floatingExample, setFloatingExample] = useState<HomepageExample | null>(null)
  const floatingPanelRef = useRef<HTMLElement | null>(null)
  const floatingFrameRef = useRef<number | null>(null)
  const floatingPointerRef = useRef({ x: 0, y: 0 })
  const floatingSizeRef = useRef({ width: 760, height: 720 })

  const updateFloatingPosition = useCallback(() => {
    floatingFrameRef.current = null
    const panel = floatingPanelRef.current
    if (!panel) return

    const { x, y } = floatingPointerRef.current
    const { width, height } = floatingSizeRef.current
    const left = Math.max(16, Math.min(x + 22, window.innerWidth - width - 16))
    const top = Math.max(16, Math.min(y + 22, window.innerHeight - height - 16))
    panel.style.transform = `translate3d(${Math.round(left)}px, ${Math.round(top)}px, 0)`
  }, [])

  const scheduleFloatingPosition = useCallback((event?: MouseEvent<HTMLButtonElement>) => {
    if (event) floatingPointerRef.current = { x: event.clientX, y: event.clientY }
    if (floatingFrameRef.current !== null) return
    floatingFrameRef.current = window.requestAnimationFrame(updateFloatingPosition)
  }, [updateFloatingPosition])

  const cancelFloatingPosition = useCallback(() => {
    if (floatingFrameRef.current === null) return
    window.cancelAnimationFrame(floatingFrameRef.current)
    floatingFrameRef.current = null
  }, [])

  const bindFloatingPanel = useCallback((node: HTMLElement | null) => {
    floatingPanelRef.current = node
    if (!node) return
    floatingSizeRef.current = {
      width: node.offsetWidth || 760,
      height: node.offsetHeight || 720,
    }
    scheduleFloatingPosition()
  }, [scheduleFloatingPosition])

  useEffect(() => () => cancelFloatingPosition(), [cancelFloatingPosition])

  useEffect(() => {
    if (floatingExample) scheduleFloatingPosition()
  }, [floatingExample, scheduleFloatingPosition])

  const hideFloating = useCallback(() => {
    cancelFloatingPosition()
    setFloatingExample(null)
  }, [cancelFloatingPosition])

  const selectExample = useCallback((id: string) => {
    setActiveId((current) => (current === id ? current : id))
  }, [])

  const selectCategory = useCallback((id?: string) => {
    if (!id) return
    selectExample(id)
  }, [selectExample])

  const showFloating = useCallback((example: HomepageExample, event: MouseEvent<HTMLButtonElement>) => {
    selectExample(example.id)
    setFloatingExample((current) => (current?.id === example.id ? current : example))
    scheduleFloatingPosition(event)
  }, [scheduleFloatingPosition, selectExample])

  const moveFloating = useCallback((event: MouseEvent<HTMLButtonElement>) => {
    scheduleFloatingPosition(event)
  }, [scheduleFloatingPosition])

  const labeledGroups = useMemo(() => examplesByCategory.map((group) => ({
    ...group,
    label: getHomepageExampleLabel(group.examples[0] ?? { category: group.category, theme: group.category } as HomepageExample, language).category,
  })), [language])

  return (
    <div className="relative grid gap-6" onMouseLeave={hideFloating}>
      <div className="rounded-lg border border-border bg-[hsl(var(--pix-cream))] p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] md:p-8">
        <div className="grid items-center gap-6 lg:grid-cols-[.9fr_1.1fr]">
          <div><Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">{text('范例图谱', 'Sample atlas')}</Badge><h3 className="mt-5 text-3xl font-semibold md:text-5xl">{text('题材不是列表，是可验收的样本墙', 'Themes are reviewable sample walls, not lists')}</h3><p className="mt-4 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/66">{text('每套范例同时保留原 64×64 透明资源、新 32×32 outline 图标和一张 1920×1080 界面展示图。悬浮左侧卡片即可在鼠标旁展开详情。', 'Each sample keeps the original 64×64 transparent resources, new 32×32 outline icons, and a 1920×1080 UI showcase. Hover a card to open the detail panel near the cursor.')}</p></div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">{labeledGroups.map((group) => <button type="button" key={group.category} onClick={() => selectCategory(group.examples[0]?.id)} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/65 p-3 text-left transition hover:bg-white dark:border-white/10 dark:bg-white/7 dark:hover:bg-white/10"><p className="font-semibold">{group.label}</p><p className="text-xs text-[hsl(var(--pix-steel))] dark:text-white/55">{text(`${group.examples.length} 套范例`, `${group.examples.length} samples`)}</p></button>)}</div>
        </div>
      </div>
      <div className="grid gap-6">
        {labeledGroups.map((group) => <div key={group.category}><div className="mb-4 flex items-end justify-between gap-3"><div><h3 className="text-3xl font-semibold">{group.label}</h3><p className="text-sm text-muted-foreground">{text(`${group.examples.length} 套双尺寸物品 + 界面范例`, `${group.examples.length} dual-size item + UI samples`)}</p></div><Badge variant="outline">{group.examples[0]?.number}—{group.examples[group.examples.length - 1]?.number}</Badge></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">{group.examples.map((example) => <ExampleTile key={example.id} example={example} active={activeId === example.id} onSelect={selectExample} onHoverStart={showFloating} onHoverMove={moveFloating} />)}</div></div>)}
      </div>
      {floatingExample && <ExampleFloatingDetail key={floatingExample.id} example={floatingExample} panelRef={bindFloatingPanel} />}
    </div>
  )
}

type ExampleTileProps = {
  example: HomepageExample
  active: boolean
  onSelect: (id: string) => void
  onHoverStart: (example: HomepageExample, event: MouseEvent<HTMLButtonElement>) => void
  onHoverMove: (event: MouseEvent<HTMLButtonElement>) => void
}

const ExampleTile = memo(function ExampleTile({ example, active, onSelect, onHoverStart, onHoverMove }: ExampleTileProps) {
  const { language, text } = useI18n()
  const label = getHomepageExampleLabel(example, language)
  const handleSelect = useCallback(() => onSelect(example.id), [example.id, onSelect])
  const handleHoverStart = useCallback((event: MouseEvent<HTMLButtonElement>) => onHoverStart(example, event), [example, onHoverStart])
  return <button type="button" onClick={handleSelect} onMouseEnter={handleHoverStart} onMouseMove={onHoverMove} className={`rounded-lg border bg-card p-3 text-left transition hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${active ? 'border-primary ring-2 ring-primary/15' : 'border-border'}`}><div className="pix-checkerboard rounded-lg p-2"><ItemVariantPair example={example} compact /></div><div className="mt-3 flex items-start justify-between gap-2"><div className="min-w-0"><p className="text-base font-semibold leading-tight">{label.theme}</p><p className="mt-1 text-xs text-muted-foreground">{label.category} · {text('64×64 + 32×32 + 界面', '64×64 + 32×32 + UI')}</p></div><Badge variant="outline" className="shrink-0">{example.number}</Badge></div></button>
})

const ExampleFloatingDetail = memo(function ExampleFloatingDetail({ example, panelRef }: { example: HomepageExample; panelRef: Ref<HTMLElement> }) {
  const { language, text } = useI18n()
  const label = getHomepageExampleLabel(example, language)
  return <aside ref={panelRef} className="pointer-events-none fixed left-0 top-0 z-[90] grid w-[760px] max-w-[calc(100vw-32px)] gap-3 rounded-lg border border-border bg-card/96 p-4 shadow-[0_16px_48px_-8px_rgba(15,15,15,0.16)] backdrop-blur-xl will-change-transform" style={{ transform: 'translate3d(-9999px, -9999px, 0)' }}><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-primary">{text('Pix 范例', 'Pix sample')}</p><h3 className="mt-1 text-2xl font-semibold">{example.number} · {label.theme}</h3><p className="text-sm text-muted-foreground">{label.category} / {text('原 64×64 + 新 32×32 outline / 16:9 界面', 'Original 64×64 + new 32×32 outline / 16:9 UI')}</p></div><Badge>{label.category}</Badge></div><div className="grid gap-3 lg:grid-cols-[1.05fr_.95fr]"><div className="pix-checkerboard rounded-lg border border-border p-3"><div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold">{text('物品资源对比', 'Item resource comparison')}</p><Badge variant="outline">64×64 + 32×32</Badge></div><ItemVariantPair example={example} /></div><div className="overflow-hidden rounded-lg border border-border bg-muted"><img src={example.uiSrc} alt={text(`${example.theme} 像素界面展示图`, `${label.theme} pixel UI showcase`)} loading="lazy" decoding="async" className="h-full min-h-44 w-full object-cover [image-rendering:pixelated]" /></div></div><PromptBox title={text('物品提示词', 'Item prompt')} text={language === 'en' ? example.itemPrompt : buildChineseItemPrompt(example)} /><PromptBox title={text('界面提示词', 'UI prompt')} text={language === 'en' ? example.uiPrompt : buildChineseUiPrompt(example)} /></aside>
})

function ItemVariantPair({ example, compact = false }: { example: HomepageExample; compact?: boolean }) {
  const { text } = useI18n()
  return <div className={`grid gap-2 ${compact ? '' : 'sm:grid-cols-2'}`}><ItemVariantPanel example={example} variant="original64" compact={compact} title={text('原 64×64', 'Original 64×64')} badge="64×64" /><ItemVariantPanel example={example} variant="outline32" compact={compact} title={text('新 32×32 outline', 'New 32×32 outline')} badge="32×32" /></div>
}

function ItemVariantPanel({ example, variant, compact, title, badge }: { example: HomepageExample; variant: ItemSpriteVariant; compact: boolean; title: string; badge: string }) {
  return <div className={`rounded-lg border border-border bg-card/75 ${compact ? 'p-1.5' : 'p-2'}`}><div className={`flex items-center justify-between gap-2 ${compact ? 'mb-1' : 'mb-2'}`}><p className={`${compact ? 'text-[10px]' : 'text-xs'} font-semibold text-muted-foreground`}>{title}</p><Badge variant="outline" className="shrink-0 text-[10px]">{badge}</Badge></div><ItemSpriteGrid example={example} variant={variant} compact={compact} /></div>
}

function ItemSpriteGrid({ example, variant = 'outline32', compact = false }: { example: HomepageExample; variant?: ItemSpriteVariant; compact?: boolean }) {
  const { language, text } = useI18n()
  const label = getHomepageExampleLabel(example, language)
  const variantAlt = variant === 'original64' ? text('原 64×64 物品', 'original 64×64 item') : text('32×32 outline 物品', '32×32 outline item')
  return <div className="grid grid-cols-4 gap-1">{itemSpriteSlots.map((index) => <div key={index} className={`aspect-square overflow-hidden rounded-lg border border-border bg-card ${compact ? 'p-0.5' : 'p-1'}`}><img src={itemSlotSrc(example, index, variant)} alt={text(`${example.theme} ${variantAlt} ${index + 1}`, `${label.theme} ${variantAlt} ${index + 1}`)} loading="lazy" decoding="async" className="h-full w-full object-contain [image-rendering:pixelated]" /></div>)}</div>
}

function PromptBox({ title, text, tone = 'default' }: { title: string; text: string; tone?: 'default' | 'light' | 'dark' }) {
  const boxClass = tone === 'dark'
    ? 'border-white/12 bg-white/7 text-white/70'
    : tone === 'light'
      ? 'border-[hsl(var(--pix-navy))]/15 bg-white/55 text-[hsl(var(--pix-slate))] dark:border-white/12 dark:bg-white/7 dark:text-white/68'
      : 'border-border bg-muted/40 text-muted-foreground'
  const titleClass = tone === 'dark' ? 'text-white/65' : tone === 'light' ? 'text-[hsl(var(--pix-steel))] dark:text-white/55' : 'text-muted-foreground'
  return <div className={`mt-4 rounded-lg border p-3 ${boxClass}`}><p className={`text-xs font-semibold uppercase tracking-[.12em] ${titleClass}`}>{title}</p><p className="mt-2 text-xs leading-6">{text}</p></div>
}

function AuthSection({ authSlot }: { authSlot: ReactNode }) {
  const { text } = useI18n()
  return (
    <section id="auth-panel" className="scroll-mt-28 border-t border-border bg-[hsl(var(--secondary))] px-4 py-16 md:px-8 md:py-20 dark:border-white/10 dark:bg-[hsl(var(--pix-navy-deep))]">
      <div className="mx-auto grid max-w-7xl items-center gap-10 rounded-lg bg-card p-6 shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card))] dark:shadow-[0_30px_80px_-46px_rgba(0,0,0,0.9)] md:p-10 lg:grid-cols-[.9fr_1.1fr]">
        <div>
          <Badge>{text('开始生产', 'Start producing')}</Badge>
          <h2 className="mt-5 font-sans text-4xl font-semibold tracking-tight md:text-6xl">{text('进入像素工位台', 'Enter the pixel workbench')}</h2>
          <p className="mt-5 max-w-xl text-base leading-8 text-muted-foreground">{text('创建单图或批量任务，完成后在作品库挑选、保存到素材包、重试和导出。', 'Create single images or batch jobs, then review, save to packs, retry, and export from the gallery.')}</p>
          <div className="mt-6 flex flex-wrap gap-3"><Button asChild><a href="#auth-panel">{text('登录', 'Sign in')}</a></Button><Button variant="outline" asChild><a href="#examples">{text('看范例', 'View samples')}</a></Button></div>
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

function itemSlotSrc(example: HomepageExample, index: number, variant: ItemSpriteVariant = 'outline32') {
  const slotSrc = example.itemSrc.replace('.png', `_${String(index + 1).padStart(2, '0')}.png`)
  return variant === 'original64' ? slotSrc.replace('/homepage-examples/items/', '/homepage-examples/items-64/') : slotSrc
}
function buildChineseItemPrompt(example: HomepageExample) { return `像素风「${example.theme}」物品图标组，拆成 4×2 共 8 个独立道具格；主页同时展示原 64×64 透明资源和新 32×32 outline 图标，居中构图、硬边像素、有限调色板、无抗锯齿，适合作为背包图标或掉落物素材。` }
function buildChineseUiPrompt(example: HomepageExample) { return `像素风「${example.theme}」16:9 UI 展示图，包含主题面板、边框、按钮、图标、状态区和游戏界面示例；整体为 16-bit RPG / 独立游戏可用风格。` }
