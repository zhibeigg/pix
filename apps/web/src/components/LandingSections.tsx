import { memo, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { Check, Copy, Download, Pause, Play } from 'lucide-react'
import { useI18n } from '../i18n'
import { homepageExampleIconSizes, homepageExampleItemIcons, getHomepageIconsForExample, type HomepageExampleItemIcon } from '../homepageIconExamples'
import { homepageExampleCategories, homepageExamples, getHomepageExampleItemSubject, getHomepageExampleItemSubjectPrompt, getHomepageExampleLabel, type HomepageExample } from '../homepageExamples'
import { homepageTextureExamples, homepageTextureCategoriesInUse, getHomepageTextureLabel, type HomepageTextureExample, type HomepageTextureCategory } from '../homepageTextureExamples'
import { homepageSpriteExamples, homepageSpriteCategoriesInUse, getHomepageSpriteLabel, type HomepageSpriteExample, type HomepageSpriteCategory } from '../homepageSpriteExamples'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

const homepageExampleById = new Map(homepageExamples.map((example) => [example.id, example]))

type LandingSectionsProps = { authSlot: ReactNode }
type IconSizeFilter = 'all' | string
type CategoryFilter = 'all' | string
type ThemeFilter = 'all' | string
type AssetTypeTab = 'item_icon' | 'tile_texture' | 'sprite_sheet'
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
      <SectionFrame id="examples" eyebrow={text('范例图鉴', 'Sample atlas')} title={text('按资产类型分类浏览：物品图标 + 平铺纹理 + 序列帧', 'Browse by asset type: item icons + tileable textures + sprite sheets')} description={text('物品图标按尺寸 / 大类 / 风格筛选 608 张全流程重生成 PNG；平铺纹理一次出图、铺满画布、四边无缝拼接；序列帧用单图 mosaic 模式一次性产出 N 帧动画 sprite sheet，前端用 CSS 切帧实时播放。', 'Item icons cover 608 fully regenerated PNGs filtered by size / category / theme. Tileable textures fill the whole canvas with seamless tiling in one API call. Sprite sheets use the single-image mosaic mode to produce all frames in one shot, then play live in the browser via CSS frame stepping.')}>
        <ExampleAtlas />
      </SectionFrame>

      <AuthSection authSlot={authSlot} />
    </>
  )
}

function ExampleAtlas() {
  const { text } = useI18n()
  const [assetType, setAssetType] = useState<AssetTypeTab>('item_icon')
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-2 dark:bg-[hsl(var(--pix-dark-card))]">
        <span className="px-2 text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('资产类型', 'Asset type')}</span>
        <AssetTypeChip active={assetType === 'item_icon'} onClick={() => setAssetType('item_icon')}>{text('物品图标', 'Item icons')}<span className="ml-2 opacity-60">{homepageExampleItemIcons.length}</span></AssetTypeChip>
        <AssetTypeChip active={assetType === 'tile_texture'} onClick={() => setAssetType('tile_texture')}>{text('平铺纹理', 'Tile textures')}<span className="ml-2 opacity-60">{homepageTextureExamples.length}</span></AssetTypeChip>
        <AssetTypeChip active={assetType === 'sprite_sheet'} onClick={() => setAssetType('sprite_sheet')}>{text('序列帧', 'Sprite sheets')}<span className="ml-2 opacity-60">{homepageSpriteExamples.length}</span></AssetTypeChip>
      </div>

      {assetType === 'item_icon' ? <IconAtlas /> : assetType === 'tile_texture' ? <TextureAtlas /> : <SpriteAtlas />}
    </div>
  )
}

function AssetTypeChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button type="button" onClick={onClick} aria-pressed={active} className={`inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-primary/20 ${active ? 'border-primary bg-primary text-primary-foreground shadow-[0_4px_10px_-6px_rgba(0,0,0,0.4)]' : 'border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground dark:bg-white/7'}`}>{children}</button>
}

function IconAtlas() {
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

type TextureCategoryFilter = 'all' | HomepageTextureCategory

function TextureAtlas() {
  const { language, text } = useI18n()
  const [categoryFilter, setCategoryFilter] = useState<TextureCategoryFilter>('all')
  const filtered = useMemo(
    () => homepageTextureExamples.filter((ex) => categoryFilter === 'all' || ex.category === categoryFilter),
    [categoryFilter],
  )
  return (
    <div className="grid gap-6">
      <div className="rounded-lg border border-border bg-[hsl(var(--pix-cream))] p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] md:p-8">
        <div className="grid items-start gap-6 lg:grid-cols-[.86fr_1.14fr]">
          <div>
            <Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">{text('平铺纹理', 'Tileable texture')}</Badge>
            <h3 className="mt-5 text-3xl font-semibold md:text-5xl">{text('一次 API 出图，铺满画布、四边无缝拼接', 'One API call: fills the canvas, seams disappear')}</h3>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/66">{text('平铺纹理走专用最小后处理：1 次生图 + perfect_pixel 网格自动检测 + 直接落盘，输出尺寸由 perfectPixel 自动判定（多为 32×32 ~ 128×128）。不抠透明、不裁剪主体、不做 VL 评分。卡片左侧是原图，右侧是 4×4 拼接预览。', 'Tile textures use a minimal pipeline: one API call + perfectPixel grid detection + save. The output resolution is decided by perfectPixel itself (typically 32×32 ~ 128×128). No alpha cutout, no subject crop, no VL ranking. The left side of each card shows the raw PNG; the right side shows a 4×4 tiled preview.')}</p>
          </div>
          <div className="grid gap-3 rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/60 p-4 dark:border-white/10 dark:bg-white/7">
            <div className="grid grid-cols-3 gap-2 text-center">
              <AtlasStat label={text('当前命中', 'Showing')} value={filtered.length} />
              <AtlasStat label={text('全部纹理', 'Total textures')} value={homepageTextureExamples.length} />
              <AtlasStat label={text('题材分类', 'Categories')} value={homepageTextureCategoriesInUse.length} />
            </div>
          </div>
        </div>
        <div className="mt-6 grid gap-4">
          <FilterGroup label={text('题材分类', 'Category')}>
            <FilterChip active={categoryFilter === 'all'} onClick={() => setCategoryFilter('all')}>{text('全部分类', 'All categories')}</FilterChip>
            {homepageTextureCategoriesInUse.map((cat) => {
              const count = homepageTextureExamples.filter((ex) => ex.category === cat).length
              const sample = homepageTextureExamples.find((ex) => ex.category === cat)
              const label = sample ? getHomepageTextureLabel(sample, language).category : cat
              return <FilterChip key={cat} active={categoryFilter === cat} onClick={() => setCategoryFilter(cat)}>{label}<span className="ml-1 opacity-60">{count}</span></FilterChip>
            })}
          </FilterGroup>
        </div>
      </div>

      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((example) => <TextureCard key={example.id} example={example} />)}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center text-muted-foreground">
          <p className="text-base font-semibold text-foreground">{text('没有匹配的纹理', 'No matching textures')}</p>
          <Button type="button" variant="outline" onClick={() => setCategoryFilter('all')} className="mt-4">{text('查看全部', 'Show all')}</Button>
        </div>
      )}
    </div>
  )
}

const TextureCard = memo(function TextureCard({ example }: { example: HomepageTextureExample }) {
  const { language, text } = useI18n()
  const [copied, setCopied] = useState(false)
  const label = getHomepageTextureLabel(example, language)
  const sizeText = `${example.width}×${example.height}`

  async function handleCopy() {
    const ok = await copyTextToClipboard(example.prompt)
    setCopied(ok)
    if (ok) window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <article className="rounded-lg border border-border bg-card p-3 transition hover:-translate-y-0.5 hover:border-primary/55 hover:shadow-[0_10px_24px_-18px_rgba(15,15,15,0.45)] dark:bg-[hsl(var(--pix-dark-card))]">
      <div className="grid grid-cols-2 gap-3">
        <a href={example.src} target="_blank" rel="noreferrer" className="block" title={text(`打开 ${label.theme} 原图`, `Open source image for ${label.theme}`)}>
          <div className="pix-checkerboard grid aspect-square place-items-center overflow-hidden rounded-md border border-border bg-card p-2 dark:bg-[hsl(var(--pix-dark-band))]">
            <img src={example.src} alt={text(`${label.theme} 原图`, `${label.theme} raw`)} loading="lazy" decoding="async" draggable={false} className="h-full w-full object-contain [image-rendering:pixelated]" />
          </div>
          <p className="mt-1 text-center font-mono text-[10px] text-muted-foreground">{text(`原图 ${sizeText}`, `Raw ${sizeText}`)}</p>
        </a>
        <div className="grid">
          <div
            role="img"
            aria-label={text(`${label.theme} 4×4 平铺预览`, `${label.theme} 4×4 tiled preview`)}
            className="aspect-square overflow-hidden rounded-md border border-border bg-muted/40 [image-rendering:pixelated] dark:bg-[hsl(var(--pix-dark-band))]"
            title={text('4×4 拼接预览', '4×4 tiled preview')}
            style={{
              backgroundImage: `url(${example.src})`,
              backgroundRepeat: 'repeat',
              backgroundSize: '25% 25%',
            }}
          />
          <p className="mt-1 text-center font-mono text-[10px] text-muted-foreground">{text('4×4 平铺', '4×4 tiled')}</p>
        </div>
      </div>
      <div className="mt-3 min-w-0">
        <p className="truncate text-sm font-semibold">{label.subject}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">{label.category} · {example.number}</p>
        <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">{example.prompt}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => downloadStaticFile(example.src, `${example.id}.png`)}><Download />{text('下载', 'Download')}</Button>
          <Button type="button" size="sm" variant="outline" onClick={() => void handleCopy()}>{copied ? <Check /> : <Copy />}{copied ? text('已复制', 'Copied') : text('复制 Prompt', 'Copy prompt')}</Button>
        </div>
      </div>
    </article>
  )
})

type SpriteCategoryFilter = 'all' | HomepageSpriteCategory

function SpriteAtlas() {
  const { language, text } = useI18n()
  const [categoryFilter, setCategoryFilter] = useState<SpriteCategoryFilter>('all')
  const filtered = useMemo(
    () => homepageSpriteExamples.filter((ex) => categoryFilter === 'all' || ex.category === categoryFilter),
    [categoryFilter],
  )
  return (
    <div className="grid gap-6">
      <div className="rounded-lg border border-border bg-[hsl(var(--pix-cream))] p-6 text-[hsl(var(--pix-charcoal))] shadow-[0_4px_12px_rgba(15,15,15,0.08)] dark:border-white/10 dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_18px_60px_-34px_rgba(0,0,0,0.85)] md:p-8">
        <div className="grid items-start gap-6 lg:grid-cols-[.86fr_1.14fr]">
          <div>
            <Badge className="bg-[hsl(var(--pix-navy))] text-white dark:bg-white dark:text-[hsl(var(--pix-navy))]">{text('序列帧', 'Sprite sheet')}</Badge>
            <h3 className="mt-5 text-3xl font-semibold md:text-5xl">{text('一次 API 出图，rows×cols 全帧 mosaic 直出', 'One API call: every frame in a single rows×cols mosaic')}</h3>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[hsl(var(--pix-slate))] dark:text-white/66">{text('序列帧走 mosaic 单图模式：1 次生图就能拿到 rows×cols 网格上的所有动画帧，后处理切片、对齐、抠色、像素化一气呵成，落盘的是一条横向 sprite sheet。卡片左侧是产物原图，右侧是浏览器内 CSS background-position 切帧实时播放，不依赖 GIF。', 'Sprite sheets use the mosaic single-image mode: a single API call produces every frame of a rows×cols grid; post-processing slices, aligns, keys out the background, and pixelizes them into one horizontal sprite sheet. The left side of each card shows the raw sheet; the right side plays it live in the browser with CSS background-position frame stepping — no GIF needed.')}</p>
          </div>
          <div className="grid gap-3 rounded-lg border border-[hsl(var(--pix-navy))]/10 bg-white/60 p-4 dark:border-white/10 dark:bg-white/7">
            <div className="grid grid-cols-3 gap-2 text-center">
              <AtlasStat label={text('当前命中', 'Showing')} value={filtered.length} />
              <AtlasStat label={text('全部序列帧', 'Total sprites')} value={homepageSpriteExamples.length} />
              <AtlasStat label={text('题材分类', 'Categories')} value={homepageSpriteCategoriesInUse.length} />
            </div>
          </div>
        </div>
        <div className="mt-6 grid gap-4">
          <FilterGroup label={text('题材分类', 'Category')}>
            <FilterChip active={categoryFilter === 'all'} onClick={() => setCategoryFilter('all')}>{text('全部分类', 'All categories')}</FilterChip>
            {homepageSpriteCategoriesInUse.map((cat) => {
              const count = homepageSpriteExamples.filter((ex) => ex.category === cat).length
              const sample = homepageSpriteExamples.find((ex) => ex.category === cat)
              const label = sample ? getHomepageSpriteLabel(sample, language).category : cat
              return <FilterChip key={cat} active={categoryFilter === cat} onClick={() => setCategoryFilter(cat)}>{label}<span className="ml-1 opacity-60">{count}</span></FilterChip>
            })}
          </FilterGroup>
        </div>
      </div>

      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((example) => <SpriteCard key={example.id} example={example} />)}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center text-muted-foreground">
          <p className="text-base font-semibold text-foreground">{text('没有匹配的序列帧', 'No matching sprite sheets')}</p>
          <Button type="button" variant="outline" onClick={() => setCategoryFilter('all')} className="mt-4">{text('查看全部', 'Show all')}</Button>
        </div>
      )}
    </div>
  )
}

const SpriteCard = memo(function SpriteCard({ example }: { example: HomepageSpriteExample }) {
  const { language, text } = useI18n()
  const [copied, setCopied] = useState(false)
  const [playing, setPlaying] = useState(true)
  const [frameIndex, setFrameIndex] = useState(0)
  const previewRef = useRef<HTMLDivElement | null>(null)
  const [previewWidth, setPreviewWidth] = useState(0)
  const label = getHomepageSpriteLabel(example, language)
  const sheetSize = `${example.sheetWidth}×${example.sheetHeight}`
  const frameSize = `${example.frameWidth}×${example.frameHeight}`

  useEffect(() => {
    const node = previewRef.current
    if (!node) return
    const update = () => setPreviewWidth(node.clientWidth)
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!playing || example.frameCount <= 1) return
    const interval = window.setInterval(() => {
      setFrameIndex((current) => (current + 1) % example.frameCount)
    }, Math.max(40, Math.round(1000 / Math.max(1, example.fps))))
    return () => window.clearInterval(interval)
  }, [playing, example.frameCount, example.fps])

  // 单帧整数倍放大：以预览容器宽度为准，按整数倍缩放避免亚像素糊。
  const previewScale = previewWidth > 0 ? Math.max(1, Math.floor(previewWidth / example.frameWidth)) : 1
  const renderedFrame = example.frameWidth * previewScale
  const renderedSheetForPreview = example.sheetWidth * previewScale
  const offsetX = -frameIndex * renderedFrame

  async function handleCopy() {
    const ok = await copyTextToClipboard(label.prompt)
    setCopied(ok)
    if (ok) window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <article className="rounded-lg border border-border bg-card p-3 transition hover:-translate-y-0.5 hover:border-primary/55 hover:shadow-[0_10px_24px_-18px_rgba(15,15,15,0.45)] dark:bg-[hsl(var(--pix-dark-card))]">
      <a href={example.src} target="_blank" rel="noreferrer" className="block" title={text(`打开 ${label.theme} sprite sheet 原图`, `Open source sprite sheet for ${label.theme}`)}>
        <div className="pix-checkerboard grid h-24 place-items-center overflow-hidden rounded-md border border-border bg-card p-2 dark:bg-[hsl(var(--pix-dark-band))]">
          <img
            src={example.src}
            alt={text(`${label.theme} sprite sheet 原图，${example.frameCount} 帧`, `${label.theme} raw sprite sheet, ${example.frameCount} frames`)}
            loading="lazy"
            decoding="async"
            draggable={false}
            className="block max-h-full max-w-full [image-rendering:pixelated]"
          />
        </div>
      </a>
      <div className="mt-1.5 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
        <span>{text(`原图 ${sheetSize}`, `Sheet ${sheetSize}`)}</span>
        <span>{text(`${example.frameCount} 帧 · 单帧 ${frameSize}`, `${example.frameCount} frames · ${frameSize} each`)}</span>
      </div>

      <div className="mt-3 grid grid-cols-[140px_1fr] items-stretch gap-3">
        <div className="grid gap-1">
          <div className="pix-checkerboard relative aspect-square overflow-hidden rounded-md border border-border bg-muted/40 dark:bg-[hsl(var(--pix-dark-band))]">
            <div
              ref={previewRef}
              role="img"
              aria-label={text(`${label.theme} 序列帧预览，${example.frameCount} 帧 ${example.fps} fps`, `${label.theme} sprite preview, ${example.frameCount} frames at ${example.fps} fps`)}
              className="absolute inset-0 grid place-items-center"
            >
              <div
                className="bg-no-repeat [image-rendering:pixelated]"
                style={{
                  width: renderedFrame,
                  height: example.frameHeight * previewScale,
                  backgroundImage: `url(${example.src})`,
                  backgroundSize: `${renderedSheetForPreview}px ${example.sheetHeight * previewScale}px`,
                  backgroundPosition: `${offsetX}px 0px`,
                }}
              />
            </div>
            <button
              type="button"
              onClick={() => setPlaying((value) => !value)}
              className="absolute bottom-1.5 right-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card/90 text-foreground shadow-sm transition hover:bg-card dark:bg-[hsl(var(--pix-dark-card))]/90"
              aria-label={playing ? text('暂停', 'Pause') : text('播放', 'Play')}
              title={playing ? text('暂停播放', 'Pause playback') : text('开始播放', 'Start playback')}
            >
              {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            </button>
          </div>
          <p className="text-center font-mono text-[10px] text-muted-foreground">{text(`${example.fps} fps 实时预览`, `${example.fps} fps preview`)}</p>
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{label.subject}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{label.category} · {example.number}</p>
          <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">{label.prompt}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => downloadStaticFile(example.src, `${example.id}.png`)}><Download />{text('下载', 'Download')}</Button>
            <Button type="button" size="sm" variant="outline" onClick={() => void handleCopy()}>{copied ? <Check /> : <Copy />}{copied ? text('已复制', 'Copied') : text('复制 Prompt', 'Copy prompt')}</Button>
          </div>
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
