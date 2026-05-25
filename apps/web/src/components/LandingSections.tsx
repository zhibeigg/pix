import { memo, useCallback, useEffect, useMemo, useState, type MouseEvent, type ReactNode } from 'react'
import { Check, Copy, Download } from 'lucide-react'
import { useI18n } from '../i18n'
import { homepageExampleIconSizes, homepageExampleItemIcons, getHomepageIconsForExample, type HomepageExampleItemIcon } from '../homepageIconExamples'
import { homepageExampleCategories, homepageExamples, getHomepageExampleItemSubject, getHomepageExampleItemSubjectPrompt, getHomepageExampleLabel, type HomepageExample } from '../homepageExamples'
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

const homepageExampleById = new Map(homepageExamples.map((example) => [example.id, example]))
const featuredExamples = homepageExamples.slice(0, 4)

type LandingSectionsProps = { authSlot: ReactNode }
type IconSizeFilter = 'all' | string
type CategoryFilter = 'all' | string
type ThemeFilter = 'all' | string
type ItemContextMenuHandler = (icon: HomepageExampleItemIcon, event: MouseEvent<HTMLElement>) => void
type ExampleItemActionTarget = {
  icon: HomepageExampleItemIcon
  x: number
  y: number
}

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

      <SectionFrame id="examples" eyebrow={text('新版图标墙', 'Processed icon wall')} title={text('608 张后处理图标，按真实尺寸和风格筛选', '608 processed icons filtered by real size and style')} description={text('主页范例区只展示当前新版物品图；每张卡片标出 PNG 实际尺寸、题材风格和物品主体，方便按尺寸档位或世界观题材快速筛选观看。', 'The sample area now shows only the current processed item icons; every card exposes the real PNG size, theme style, and subject so you can quickly review by size tier or setting.')}>
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
          <h3 className="mt-4 text-xl font-semibold">{text('题材样本带真实尺寸', 'Theme samples keep real sizes')}</h3>
          <div className="mt-4 grid grid-cols-2 gap-2">
            {featuredExamples.map((example) => <div key={example.id} className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/55 p-2 dark:border-white/10 dark:bg-white/7"><ExampleIconStrip example={example} compact /><p className="mt-2 truncate text-xs font-semibold">{getHomepageExampleLabel(example, language).theme}</p></div>)}
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
  const [sizeFilter, setSizeFilter] = useState<IconSizeFilter>('all')
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
  const [themeFilter, setThemeFilter] = useState<ThemeFilter>('all')
  const [itemActionTarget, setItemActionTarget] = useState<ExampleItemActionTarget | null>(null)

  const categoryOptions = useMemo(() => homepageExampleCategories.map((category) => {
    const example = homepageExamples.find((item) => item.category === category)
    return {
      category,
      label: example ? getHomepageExampleLabel(example, language).category : category,
      count: homepageExampleItemIcons.filter((icon) => homepageExampleById.get(icon.exampleId)?.category === category).length,
    }
  }), [language])

  const themeOptions = useMemo(() => homepageExamples.filter((example) => categoryFilter === 'all' || example.category === categoryFilter), [categoryFilter])

  const filteredIcons = useMemo(() => homepageExampleItemIcons.filter((icon) => {
    const example = homepageExampleById.get(icon.exampleId)
    if (!example) return false
    if (sizeFilter !== 'all' && iconSizeKey(icon) !== sizeFilter) return false
    if (categoryFilter !== 'all' && example.category !== categoryFilter) return false
    if (themeFilter !== 'all' && example.id !== themeFilter) return false
    return true
  }), [categoryFilter, sizeFilter, themeFilter])

  const activeFilterCount = [sizeFilter, categoryFilter, themeFilter].filter((value) => value !== 'all').length
  const clearFilters = useCallback(() => {
    setSizeFilter('all')
    setCategoryFilter('all')
    setThemeFilter('all')
  }, [])
  const selectCategory = useCallback((nextCategory: CategoryFilter) => {
    setCategoryFilter(nextCategory)
    setThemeFilter('all')
  }, [])
  const closeItemActionMenu = useCallback(() => setItemActionTarget(null), [])
  const openItemActionMenu = useCallback<ItemContextMenuHandler>((icon, event) => {
    event.preventDefault()
    event.stopPropagation()
    const menuWidth = 304
    const menuHeight = 188
    setItemActionTarget({
      icon,
      x: Math.max(12, Math.min(event.clientX, window.innerWidth - menuWidth - 12)),
      y: Math.max(12, Math.min(event.clientY, window.innerHeight - menuHeight - 12)),
    })
  }, [])

  return (
    <div className="grid gap-6">
      <div className="rounded-lg border border-border bg-[hsl(var(--pix-cream))] p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] md:p-8">
        <div className="grid items-start gap-6 lg:grid-cols-[.86fr_1.14fr]">
          <div>
            <Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">{text('新版后处理', 'Processed set')}</Badge>
            <h3 className="mt-5 text-3xl font-semibold md:text-5xl">{text('所有样本拆成单张图标，尺寸一眼可查', 'Every sample is a single icon with visible dimensions')}</h3>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/66">{text('这里不再混入旧 64×64 对比图或 UI 展示图，只展示当前替换后的 608 张物品 PNG。点击任意图标可打开原图，右键可下载或复制该物品主体 Prompt。', 'This area no longer mixes old 64×64 comparisons or UI showcases; it only displays the 608 current processed item PNGs. Click any icon to open the source image, or right-click to download it or copy the subject prompt.')}</p>
          </div>
          <div className="grid gap-3 rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/60 p-4 dark:border-white/10 dark:bg-white/7">
            <div className="grid grid-cols-3 gap-2 text-center">
              <AtlasStat label={text('当前命中', 'Showing')} value={filteredIcons.length} />
              <AtlasStat label={text('全部图标', 'Total icons')} value={homepageExampleItemIcons.length} />
              <AtlasStat label={text('尺寸档位', 'Size tiers')} value={homepageExampleIconSizes.length} />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-[hsl(var(--pix-steel))] dark:text-white/58">
              <span>{text('已按实际 PNG 宽高生成 tag', 'Tags are generated from real PNG dimensions')}</span>
              {activeFilterCount > 0 && <Button type="button" size="sm" variant="ghost" onClick={clearFilters} className="h-7 px-2 text-xs">{text('清空筛选', 'Clear filters')}</Button>}
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          <FilterGroup label={text('尺寸', 'Size')}>
            <FilterChip active={sizeFilter === 'all'} onClick={() => setSizeFilter('all')}>{text('全部尺寸', 'All sizes')}</FilterChip>
            {homepageExampleIconSizes.map((sizeKey) => <FilterChip key={sizeKey} active={sizeFilter === sizeKey} onClick={() => setSizeFilter(sizeKey)}><span className="font-mono">{formatIconSize(sizeKey)}</span></FilterChip>)}
          </FilterGroup>

          <FilterGroup label={text('大类', 'Category')}>
            <FilterChip active={categoryFilter === 'all'} onClick={() => selectCategory('all')}>{text('全部大类', 'All categories')}</FilterChip>
            {categoryOptions.map((option) => <FilterChip key={option.category} active={categoryFilter === option.category} onClick={() => selectCategory(option.category)}>{option.label}<span className="ml-1 opacity-60">{option.count}</span></FilterChip>)}
          </FilterGroup>

          <label className="grid gap-2 sm:max-w-sm">
            <span className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('风格 / 题材', 'Style / theme')}</span>
            <select value={themeFilter} onChange={(event) => setThemeFilter(event.target.value)} className="h-10 rounded-lg border border-border bg-card px-3 text-sm text-foreground shadow-[0_1px_2px_rgba(15,15,15,0.04)] outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15 dark:bg-[hsl(var(--pix-dark-card))]">
              <option value="all">{text('全部风格', 'All styles')}</option>
              {themeOptions.map((example) => {
                const label = getHomepageExampleLabel(example, language)
                return <option key={example.id} value={example.id}>{example.number} · {label.theme}</option>
              })}
            </select>
          </label>
        </div>
      </div>

      {filteredIcons.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {filteredIcons.map((icon) => {
            const example = homepageExampleById.get(icon.exampleId)
            if (!example) return null
            return <ExampleIconCard key={icon.id} icon={icon} example={example} onItemContextMenu={openItemActionMenu} />
          })}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center text-muted-foreground">
          <p className="text-base font-semibold text-foreground">{text('没有匹配的图标', 'No matching icons')}</p>
          <p className="mt-2 text-sm">{text('换一个尺寸或风格筛选条件再看看。', 'Try another size or style filter.')}</p>
          <Button type="button" variant="outline" onClick={clearFilters} className="mt-4">{text('查看全部 608 张', 'Show all 608')}</Button>
        </div>
      )}
      {itemActionTarget && <ExampleItemActionMenu target={itemActionTarget} onClose={closeItemActionMenu} />}
    </div>
  )
}

function AtlasStat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/70 px-3 py-2 dark:border-white/10 dark:bg-white/7"><p className="text-[11px] text-[hsl(var(--pix-steel))] dark:text-white/55">{label}</p><p className="text-xl font-semibold leading-tight">{value}</p></div>
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return <div className="grid gap-2"><p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{label}</p><div className="flex flex-wrap gap-2">{children}</div></div>
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button type="button" onClick={onClick} className={filterChipClass(active)} aria-pressed={active}>{children}</button>
}

const ExampleIconCard = memo(function ExampleIconCard({ icon, example, onItemContextMenu }: { icon: HomepageExampleItemIcon; example: HomepageExample; onItemContextMenu: ItemContextMenuHandler }) {
  const { language, text } = useI18n()
  const label = getHomepageExampleLabel(example, language)
  const subject = getHomepageExampleItemSubject(example, icon.slot, language)
  const sizeKey = iconSizeKey(icon)
  return (
    <article onContextMenu={(event) => onItemContextMenu(icon, event)} className="group rounded-lg border border-border bg-card p-3 transition hover:-translate-y-0.5 hover:border-primary/55 hover:shadow-[0_10px_24px_-18px_rgba(15,15,15,0.45)] dark:bg-[hsl(var(--pix-dark-card))]">
      <a href={icon.src} target="_blank" rel="noreferrer" className="block" title={text(`打开 ${subject} 原图`, `Open source image for ${subject}`)}>
        <div className="pix-checkerboard grid aspect-square place-items-center overflow-hidden rounded-lg border border-border bg-card p-3 dark:bg-[hsl(var(--pix-dark-band))]">
          <img src={icon.src} alt={text(`${label.theme} ${subject}，实际尺寸 ${formatIconSize(sizeKey)}`, `${label.theme} ${subject}, actual size ${formatIconSize(sizeKey)}`)} loading="lazy" decoding="async" draggable={false} className="h-full w-full object-contain [image-rendering:pixelated]" />
        </div>
      </a>
      <div className="mt-3 min-w-0">
        <p className="truncate text-sm font-semibold">{subject}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">{label.category} · {example.number}-{icon.slotLabel}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <IconSizeBadge sizeKey={sizeKey} />
          <span className="rounded-full border border-border bg-[hsl(var(--secondary))] px-2 py-0.5 text-[11px] font-semibold text-[hsl(var(--pix-slate))] dark:bg-white/7 dark:text-white/68">{label.theme}</span>
        </div>
      </div>
    </article>
  )
})

function ExampleIconStrip({ example, compact = false, onItemContextMenu }: { example: HomepageExample; compact?: boolean; onItemContextMenu?: ItemContextMenuHandler }) {
  const { language, text } = useI18n()
  const label = getHomepageExampleLabel(example, language)
  const icons = getHomepageIconsForExample(example.id)
  return <div className="grid grid-cols-4 gap-1">{icons.map((icon) => {
    const subject = getHomepageExampleItemSubject(example, icon.slot, language)
    return <a key={icon.id} href={icon.src} target="_blank" rel="noreferrer" title={text(`${subject} · ${formatIconSize(iconSizeKey(icon))}`, `${subject} · ${formatIconSize(iconSizeKey(icon))}`)} onContextMenu={(event) => onItemContextMenu?.(icon, event)} className={`pix-checkerboard grid aspect-square place-items-center overflow-hidden rounded-md border border-border bg-card transition hover:border-primary/60 ${compact ? 'p-0.5' : 'p-1'}`}><img src={icon.src} alt={text(`${label.theme} ${subject}`, `${label.theme} ${subject}`)} loading="lazy" decoding="async" draggable={false} className="h-full w-full object-contain [image-rendering:pixelated]" /></a>
  })}</div>
}

function IconSizeBadge({ sizeKey }: { sizeKey: string }) {
  return <span className={`rounded-full border px-2 py-0.5 font-mono text-[11px] font-semibold ${sizeToneClass(sizeKey)}`}>{formatIconSize(sizeKey)}</span>
}

function ExampleItemActionMenu({ target, onClose }: { target: ExampleItemActionTarget; onClose: () => void }) {
  const { language, text } = useI18n()
  const [copied, setCopied] = useState(false)
  const example = homepageExampleById.get(target.icon.exampleId)
  const label = example ? getHomepageExampleLabel(example, language) : null
  const subject = example ? getHomepageExampleItemSubject(example, target.icon.slot, language) : target.icon.file
  const subjectPrompt = example ? getHomepageExampleItemSubjectPrompt(example, target.icon.slot, language) : target.icon.file
  const sizeLabel = formatIconSize(iconSizeKey(target.icon))

  useEffect(() => {
    const closeOnPointerDown = () => onClose()
    const closeOnScroll = () => onClose()
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('pointerdown', closeOnPointerDown)
    window.addEventListener('scroll', closeOnScroll, true)
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      window.removeEventListener('pointerdown', closeOnPointerDown)
      window.removeEventListener('scroll', closeOnScroll, true)
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [onClose])

  const handleDownload = useCallback(() => {
    downloadStaticFile(target.icon.src, target.icon.file)
    onClose()
  }, [onClose, target.icon.file, target.icon.src])

  const handleCopy = useCallback(async () => {
    const ok = await copyTextToClipboard(subjectPrompt)
    setCopied(ok)
    if (ok) window.setTimeout(onClose, 650)
  }, [onClose, subjectPrompt])

  return (
    <div role="menu" aria-label={text('范例物品操作', 'Sample item actions')} className="fixed z-[110] w-72 max-w-[calc(100vw-24px)] rounded-lg border border-border bg-popover p-2 text-popover-foreground shadow-[0_16px_48px_-8px_rgba(15,15,15,0.16)]" style={{ left: target.x, top: target.y }} onPointerDown={(event) => event.stopPropagation()} onContextMenu={(event) => event.preventDefault()}>
      <div className="px-2 pb-2 pt-1">
        <p className="text-xs font-semibold uppercase tracking-[.12em] text-primary">{sizeLabel} · {target.icon.slotLabel}</p>
        <p className="mt-1 text-sm font-semibold">{label ? `${label.theme} / ${subject}` : subject}</p>
        <p className="mt-1 line-clamp-3 text-xs leading-5 text-muted-foreground">{subjectPrompt}</p>
        <p className="mt-1 text-[11px] leading-5 text-muted-foreground/80">{text('复制的是主体 Prompt；下载会保存当前新版后处理 PNG。', 'Copies the subject prompt; download saves the current processed PNG.')}</p>
      </div>
      <div className="grid gap-1">
        <Button type="button" variant="ghost" className="justify-start" onClick={handleDownload}><Download />{text('下载这张图', 'Download this image')}</Button>
        <Button type="button" variant="ghost" className="justify-start" onClick={handleCopy}>{copied ? <Check /> : <Copy />}{copied ? text('已复制主体 Prompt', 'Subject prompt copied') : text('复制主体 Prompt', 'Copy subject prompt')}</Button>
      </div>
    </div>
  )
}

function iconSizeKey(icon: Pick<HomepageExampleItemIcon, 'width' | 'height'>) {
  return `${icon.width}x${icon.height}`
}

function formatIconSize(sizeKey: string) {
  return sizeKey.replace('x', '×')
}

function filterChipClass(active: boolean) {
  const base = 'inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-primary/20'
  if (active) return `${base} border-primary bg-primary text-primary-foreground shadow-[0_8px_18px_-14px_rgba(0,0,0,0.5)]`
  return `${base} border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground dark:bg-white/7`
}

function sizeToneClass(sizeKey: string) {
  if (sizeKey === '24x24') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-300/20 dark:bg-amber-300/12 dark:text-amber-100'
  if (sizeKey === '32x32') return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-300/20 dark:bg-emerald-300/12 dark:text-emerald-100'
  if (sizeKey === '48x48') return 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-300/20 dark:bg-sky-300/12 dark:text-sky-100'
  if (sizeKey === '64x64') return 'border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-300/20 dark:bg-violet-300/12 dark:text-violet-100'
  if (sizeKey === '96x96') return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-300/20 dark:bg-rose-300/12 dark:text-rose-100'
  return 'border-stone-300 bg-stone-100 text-stone-800 dark:border-white/15 dark:bg-white/10 dark:text-white/80'
}

function PromptBox({ title, text: promptText, tone = 'default' }: { title: string; text: string; tone?: 'default' | 'light' | 'dark' }) {
  const { text } = useI18n()
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const boxClass = tone === 'dark'
    ? 'border-white/12 bg-white/7 text-white/70'
    : tone === 'light'
      ? 'border-[hsl(var(--pix-navy))]/15 bg-white/55 text-[hsl(var(--pix-slate))] dark:border-white/12 dark:bg-white/7 dark:text-white/68'
      : 'border-border bg-muted/40 text-muted-foreground'
  const titleClass = tone === 'dark' ? 'text-white/65' : tone === 'light' ? 'text-[hsl(var(--pix-steel))] dark:text-white/55' : 'text-muted-foreground'
  const handleCopy = useCallback(async () => {
    const copied = await copyTextToClipboard(promptText)
    setCopyState(copied ? 'copied' : 'failed')
    window.setTimeout(() => setCopyState('idle'), 1300)
  }, [promptText])
  const copyLabel = copyState === 'copied' ? text('已复制', 'Copied') : copyState === 'failed' ? text('复制失败', 'Copy failed') : text('复制', 'Copy')
  return <div className={`mt-4 rounded-lg border p-3 ${boxClass}`}><div className="flex items-center justify-between gap-3"><p className={`text-xs font-semibold uppercase tracking-[.12em] ${titleClass}`}>{title}</p><Button type="button" size="sm" variant="ghost" onClick={handleCopy} className="h-7 px-2 text-[11px]">{copyState === 'copied' ? <Check /> : <Copy />}{copyLabel}</Button></div><p className="mt-2 text-xs leading-6">{promptText}</p></div>
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

function downloadStaticFile(url: string, filename: string) {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

async function copyTextToClipboard(value: string) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
    const textArea = document.createElement('textarea')
    textArea.value = value
    textArea.setAttribute('readonly', '')
    textArea.style.position = 'fixed'
    textArea.style.left = '-9999px'
    textArea.style.top = '0'
    document.body.appendChild(textArea)
    textArea.select()
    const copied = document.execCommand('copy')
    textArea.remove()
    return copied
  } catch {
    return false
  }
}
