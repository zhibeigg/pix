import { useMemo, useState, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { Clipboard, ExternalLink, Settings2, X } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import { jobTypeLabel } from '../labels'
import type { GenerationJob, JobOutput } from '../types'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Dialog, DialogDescription, DialogHeader, DialogOverlay, DialogPortal, DialogTitle } from './ui/dialog'

export function JobParameterSnapshotDialog({ job }: { job: GenerationJob; output?: JobOutput }) {
  const { language, text } = useI18n()
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const params = asRecord(job.params_json)
  const pixelize = asRecord(params?.pixelize)
  const sprite = asRecord(params?.sprite)
  const asset = asRecord(params?.asset)
  const styleProfile = asRecord(params?.style_profile)
  const isRawImage = job.job_type === 'text_to_image' && params?.source_only === true
  const isLocalBgRemove = job.job_type === 'local_bg_remove'
  const userInputSnapshot = useMemo(() => buildUserInputSnapshot(job), [job])
  const inputImageUrl = signedFileUrl(job.input_image_url ?? undefined)

  const promptRows = compactRows([
    [text('模式', 'Mode'), jobTypeLabel(job.job_type, language)],
    [text('提示词', 'Prompt'), job.prompt?.trim() || '—'],
    [text('输入图片', 'Input image'), job.input_image_path ? <InputImagePreview url={inputImageUrl} label={text('已上传图片', 'Uploaded image')} openLabel={text('查看原图', 'Open original')} /> : '—'],
    [text('素材主体', 'Asset subject'), stringOrDash(asset?.name)],
    [text('额外风格描述', 'Extra style notes'), stringOrDash(asset?.extra_prompt)],
  ] as SnapshotRow[])

  const rawRows = isRawImage ? compactRows([
    [text('模型', 'Model'), stringOrDash(params?.image_model)],
    [text('图片尺寸', 'Image size'), stringOrDash(params?.image_size)],
    [text('质量', 'Quality'), stringOrDash(params?.image_quality)],
  ]) : []

  const pixelRows = !isRawImage ? compactRows(isLocalBgRemove ? [
    [text('去背景算法', 'Background removal algorithm'), bgRemovalAlgorithmLabel(pixelize?.bg_removal_algorithm, text)],
  ] : [
    [job.job_type === 'sprite_sheet' ? text('单帧尺寸', 'Frame size') : text('像素尺寸', 'Pixel size'), pairLabel(pixelize?.output_size)],
    [text('颜色数', 'Color count'), stringOrDash(pixelize?.colors)],
    [text('边缘处理', 'Edge treatment'), edgeStyleLabel(pixelize?.edge_style, text)],
    ...(job.job_type === 'sprite_sheet' ? [
      [text('像素预处理', 'Pixel preprocess'), stringOrDash(pixelize?.generated_preprocess_method)],
    ] as Array<[string, string]> : [
      [text('透明背景', 'Transparent background'), yesNo(pixelize?.remove_bg, text)],
      [text('去背景算法', 'Background removal algorithm'), bgRemovalAlgorithmLabel(pixelize?.bg_removal_algorithm, text)],
    ] as Array<[string, string]>),
  ]) : []

  const styleRows = compactRows([
    [text('项目 / 世界观', 'Project / world'), stringOrDash(styleProfile?.project_name)],
    [text('配色方案', 'Color palette'), stringOrDash(styleProfile?.palette)],
    [text('线条风格', 'Line style'), stringOrDash(styleProfile?.line_style)],
    [text('光照规则', 'Lighting rule'), stringOrDash(styleProfile?.lighting)],
    [text('视角规则', 'View rule'), stringOrDash(styleProfile?.view_rule)],
    [text('避免元素', 'Avoid elements'), stringOrDash(styleProfile?.avoid_elements)],
  ] as SnapshotRow[])

  const assetRows = job.job_type === 'asset' ? compactRows([
    [text('素材类型', 'Asset type'), assetKindLabel(asset?.asset_kind, text)],
    [text('主体类型', 'Subject type'), subjectKindLabel(asset?.subject_kind, text)],
    [text('纹理类型', 'Texture type'), asset?.asset_kind === 'tile_texture' ? textureKindLabel(asset?.texture_kind, text) : '—'],
    [text('材质 A', 'Material A'), asset?.asset_kind === 'dual_grid' ? stringOrDash(asset?.material_a) : '—'],
    [text('材质 B', 'Material B'), asset?.asset_kind === 'dual_grid' ? dualMaterialBLabel(asset?.material_b, text) : '—'],
    [text('A 纹理类型', 'A texture type'), asset?.asset_kind === 'dual_grid' ? textureKindLabel(asset?.material_a_texture_kind, text) : '—'],
    [text('B 纹理类型', 'B texture type'), asset?.asset_kind === 'dual_grid' ? textureKindLabel(asset?.material_b_texture_kind, text) : '—'],
    [text('过渡风格', 'Transition style'), asset?.asset_kind === 'dual_grid' ? transitionStyleLabel(asset?.transition_style, text) : '—'],
  ]) : []

  const spriteRows = job.job_type === 'sprite_sheet' ? compactRows([
    [text('生成方式', 'Generation mode'), spriteModeLabel(sprite?.mode, text)],
    [text('帧数', 'Frame count'), stringOrDash(sprite?.frame_count)],
    ['FPS', stringOrDash(sprite?.fps)],
    [text('视频动作描述', 'Video motion description'), sprite?.mode === 'video_bridge' ? stringOrDash(sprite?.video_action_prompt) : '—'],
    [text('回到初始帧', 'Return to first frame'), sprite?.mode === 'video_bridge' ? yesNo(sprite?.video_return_to_first_frame, text) : '—'],
  ]) : []

  async function copySnapshot() {
    await navigator.clipboard.writeText(JSON.stringify(userInputSnapshot, null, 2))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); setOpen(true) }}><Settings2 />{text('参数', 'Params')}</Button>
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          onClick={(event) => event.stopPropagation()}
          onCloseAutoFocus={(event) => event.preventDefault()}
          className="fixed z-50 grid gap-4 overflow-y-auto rounded-lg border border-border bg-card p-6 pix-shadow-overlay focus:outline-none dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]"
          style={{
            left: '50%',
            maxHeight: 'calc(100dvh - 32px)',
            maxWidth: 'none',
            position: 'fixed',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 'min(760px, calc(100vw - 32px))',
          }}
        >
          <DialogHeader>
            <div className="flex flex-wrap items-start justify-between gap-3 pr-8">
              <div>
                <DialogTitle>{text('生成参数', 'Generation parameters')}</DialogTitle>
                <DialogDescription>{text('这里只显示你在创建作品时能填写或选择的参数，隐藏系统内部处理字段。', 'Only user-entered or user-selectable creation parameters are shown here; internal processing fields are hidden.')}</DialogDescription>
              </div>
              <Button type="button" variant="outline" onClick={() => void copySnapshot()}><Clipboard />{copied ? text('已复制', 'Copied') : text('复制参数', 'Copy params')}</Button>
            </div>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">#{job.id}</Badge>
              <Badge variant="secondary">{jobTypeLabel(job.job_type, language)}</Badge>
            </div>

            <SnapshotSection title={text('用户输入', 'User input')}>
              <KeyValueGrid rows={promptRows} multilineKeys={new Set([text('提示词', 'Prompt'), text('额外风格描述', 'Extra style notes')])} />
            </SnapshotSection>

            {rawRows.length > 0 && <SnapshotSection title={text('原生生图设置', 'Raw image settings')}><KeyValueGrid rows={rawRows} /></SnapshotSection>}
            {pixelRows.length > 0 && <SnapshotSection title={isLocalBgRemove ? text('去背景设置', 'Background removal settings') : text('像素设置', 'Pixel settings')}><KeyValueGrid rows={pixelRows} /></SnapshotSection>}
            {styleRows.length > 0 && <SnapshotSection title={text('项目风格档案', 'Project style profile')}><KeyValueGrid rows={styleRows} multilineKeys={new Set([text('避免元素', 'Avoid elements')])} /></SnapshotSection>}
            {assetRows.length > 0 && <SnapshotSection title={text('素材设置', 'Asset settings')}><KeyValueGrid rows={assetRows} /></SnapshotSection>}
            {spriteRows.length > 0 && <SnapshotSection title={text('序列帧设置', 'Sequence settings')}><KeyValueGrid rows={spriteRows} /></SnapshotSection>}
          </div>

          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring">
            <X className="h-4 w-4" />
            <span className="sr-only">{text('关闭', 'Close')}</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  )
}

type SnapshotRow = [string, ReactNode]

function SnapshotSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="grid gap-3 rounded-xl border border-border bg-card p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]"><h3 className="text-sm font-bold">{title}</h3>{children}</section>
}

function KeyValueGrid({ rows, multilineKeys }: { rows: SnapshotRow[]; multilineKeys?: Set<string> }) {
  return <dl className="grid gap-2 text-sm">{rows.map(([key, value]) => <div key={key} className="grid gap-1 rounded-lg bg-muted/32 p-2.5 sm:grid-cols-[150px_minmax(0,1fr)] dark:bg-[hsl(var(--pix-dark-band-soft))]"><dt className="text-xs font-semibold text-muted-foreground">{key}</dt><dd className={`min-w-0 break-words font-medium ${multilineKeys?.has(key) ? 'whitespace-pre-wrap leading-6' : ''}`}>{value}</dd></div>)}</dl>
}

function InputImagePreview({ url, label, openLabel }: { url: string; label: string; openLabel: string }) {
  if (!url) return <span>{label}</span>
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-center gap-3 rounded-lg border border-border bg-card/70 p-2 pr-3 transition hover:border-primary/50 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
      <img src={url} alt={label} className="h-16 w-16 shrink-0 rounded-md border border-border bg-muted object-contain [image-rendering:pixelated] dark:border-[hsl(var(--pix-dark-hairline))]" />
      <span className="min-w-0">
        <span className="block truncate">{label}</span>
        <span className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-primary"><ExternalLink className="h-3.5 w-3.5" />{openLabel}</span>
      </span>
    </a>
  )
}

function buildUserInputSnapshot(job: GenerationJob) {
  const params = asRecord(job.params_json)
  const pixelize = asRecord(params?.pixelize)
  const sprite = asRecord(params?.sprite)
  const asset = asRecord(params?.asset)
  const styleProfile = asRecord(params?.style_profile)
  const isRawImage = job.job_type === 'text_to_image' && params?.source_only === true
  return stripEmpty({
    mode: job.job_type,
    prompt: job.prompt?.trim() || undefined,
    input_image: job.input_image_path ? 'uploaded' : undefined,
    style_profile: stripEmpty({
      project_name: styleProfile?.project_name,
      palette: styleProfile?.palette,
      line_style: styleProfile?.line_style,
      lighting: styleProfile?.lighting,
      view_rule: styleProfile?.view_rule,
      avoid_elements: styleProfile?.avoid_elements,
    }),
    raw_image: isRawImage ? stripEmpty({
      model: params?.image_model,
      image_size: params?.image_size,
      quality: params?.image_quality,
    }) : undefined,
    pixel: !isRawImage ? stripEmpty({
      output_size: pixelize?.output_size,
      colors: pixelize?.colors,
      remove_bg: job.job_type === 'sprite_sheet' ? undefined : pixelize?.remove_bg,
      edge_style: job.job_type === 'local_bg_remove' ? undefined : pixelize?.edge_style,
      generated_preprocess_method: job.job_type === 'sprite_sheet' ? pixelize?.generated_preprocess_method : undefined,
      bg_removal_algorithm: job.job_type === 'sprite_sheet' ? undefined : pixelize?.bg_removal_algorithm,
    }) : undefined,
    asset: job.job_type === 'asset' ? stripEmpty({
      name: asset?.name,
      extra_prompt: asset?.extra_prompt,
      asset_kind: asset?.asset_kind,
      subject_kind: asset?.subject_kind,
      texture_kind: asset?.texture_kind,
      material_a: asset?.material_a,
      material_b: asset?.material_b,
      material_a_texture_kind: asset?.material_a_texture_kind,
      material_b_texture_kind: asset?.material_b_texture_kind,
      transition_style: asset?.transition_style,
    }) : undefined,
    sequence: job.job_type === 'sprite_sheet' ? stripEmpty({
      mode: sprite?.mode,
      frame_count: sprite?.frame_count,
      fps: sprite?.fps,
      video_action_prompt: sprite?.mode === 'video_bridge' ? sprite?.video_action_prompt : undefined,
      video_return_to_first_frame: sprite?.mode === 'video_bridge' ? sprite?.video_return_to_first_frame : undefined,
    }) : undefined,
  })
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function stringOrDash(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function pairLabel(value: unknown): string {
  return Array.isArray(value) && value.length === 2 ? `${value[0]}×${value[1]}` : stringOrDash(value)
}

function yesNo(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === null || value === undefined) return '—'
  return Boolean(value) ? text('是', 'Yes') : text('否', 'No')
}

function edgeStyleLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'outline') return text('描边', 'Outline')
  if (value === 'feather') return text('羽化边缘', 'Feather edge')
  if (value === 'hard') return text('不需要', 'None')
  return stringOrDash(value)
}

function bgRemovalAlgorithmLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'color_to_alpha') return text('高清（Color-to-Alpha）', 'HD (Color-to-Alpha)')
  if (value === 'pixel_bg' || value === 'auto' || value === 'imagemagick_fuzz_floodfill_alpha' || value === 'flood_fill' || value === 'hybrid') return text('像素（pixel_bg）', 'Pixel (pixel_bg)')
  return stringOrDash(value)
}

function spriteModeLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'video_bridge') return text('首尾帧视频补间', 'Start/end video bridge')
  if (value === 'mosaic' || value === undefined || value === null || value === '') return text('Mosaic 单图网格', 'Mosaic single image grid')
  return stringOrDash(value)
}

function assetKindLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'item_icon') return text('物品图标', 'Item icon')
  if (value === 'ui_component') return text('UI 组件', 'UI component')
  if (value === 'tile_texture') return text('平铺纹理', 'Tileable texture')
  if (value === 'game_logo') return text('游戏 Logo', 'Game logo')
  if (value === 'dual_grid') return text('双瓦片', 'Dual-grid tileset')
  return stringOrDash(value)
}

function dualMaterialBLabel(value: unknown, text: (zh: string, en: string) => string): string {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw || raw.toLocaleLowerCase() === 'transparent') return text('透明', 'Transparent')
  return raw
}

function subjectKindLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'single_prop') return text('单个物件', 'Single prop')
  if (value === 'single_ui') return text('单个 UI', 'Single UI')
  if (value === 'tileable_pattern') return text('无缝平铺图案', 'Seamlessly tileable pattern')
  if (value === 'logo_mark') return text('Logo 标题标识', 'Logo title mark')
  return stringOrDash(value)
}

function transitionStyleLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'hard') return text('硬边过渡', 'Hard edge')
  if (value === 'outline') return text('描边过渡', 'Outline')
  if (value === 'rounded') return text('圆滑过渡', 'Rounded')
  return stringOrDash(value)
}

function textureKindLabel(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === 'auto') return text('自动识别', 'Auto detect')
  if (value === 'generic_texture') return text('通用纹理', 'Generic texture')
  if (value === 'terrain_ground') return text('地表 / 地形', 'Terrain ground')
  if (value === 'path_floor') return text('道路 / 地砖', 'Path / floor')
  if (value === 'wall_surface') return text('墙壁 / 岩壁', 'Wall surface')
  if (value === 'wood_planks') return text('木板 / 树皮', 'Wood planks / bark')
  if (value === 'water_liquid') return text('水面 / 液体', 'Water / liquid')
  if (value === 'foliage_canopy') return text('树叶 / 草丛', 'Foliage canopy')
  if (value === 'roof_tile') return text('屋顶瓦片', 'Roof tile')
  if (value === 'metal_panel') return text('金属面板', 'Metal panel')
  if (value === 'fabric_carpet') return text('布料 / 地毯', 'Fabric / carpet')
  return stringOrDash(value)
}

function compactRows(rows: SnapshotRow[]): SnapshotRow[] {
  return rows.filter(([, value]) => value !== '—')
}

function stripEmpty<T extends Record<string, unknown>>(value: T): Partial<T> | undefined {
  const entries = Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== '')
  return entries.length > 0 ? Object.fromEntries(entries) as Partial<T> : undefined
}
