import { FormEvent, useEffect, useMemo, useState } from 'react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { GenerationJob, JobCreateRequest, JobOutput, PricingRule, TextureKind } from '../types'
import { buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, normalizeEdgeStyle, parsePixelSize, summarizePrompt, type EdgeStyleChoice } from '../pixelize'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Textarea } from './ui/textarea'
import { Badge } from './ui/badge'
import { PixPanel } from './pix/PixPanel'
import { PixStatusBadge } from './pix/PixStatusBadge'
import { PixelControls } from './PixelControls'
import { SpriteSequencePreview } from './SpriteSequencePreview'
import type { SpriteRowAction } from './GalleryGrid'

export function TuningPanel({ job, action, pricing, loading, onSubmit }: { job: GenerationJob | null; action?: SpriteRowAction | null; pricing: PricingRule[]; loading: boolean; onSubmit: (payload: JobCreateRequest) => Promise<void> }) {
  const { text } = useI18n()
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('outline')
  const [aiPrompt, setAiPrompt] = useState(() => text('保留主体，优化材质和颜色', 'Keep the subject, improve material and color'))
  const aiPrice = useMemo(() => pricing.find((item) => item.key === 'image_to_image')?.price_credits ?? 0, [pricing])

  useEffect(() => {
    if (!job) return
    const pixelize = asRecord(job.params_json?.pixelize)
    if (!pixelize) return
    const size = pixelize.output_size
    if (Array.isArray(size) && size.length >= 2) {
      setPixelSize(`${size[0]}x${size[1]}`)
    }
    if (Number.isFinite(pixelize.colors)) {
      setColors(Number(pixelize.colors))
    }
    if (typeof pixelize.remove_bg === 'boolean') {
      setRemoveBg(pixelize.remove_bg)
    }
    setEdgeStyle(normalizeEdgeStyle(pixelize.edge_style))
  }, [job?.id])

  if (!job) return <PixPanel eyebrow={text('微调工位', 'Tuning station')} title={text('选择作品进行微调', 'Select a work to tune')} description={text('选择作品后可重新像素化或 AI 微调。', 'After selecting a work, you can repixelize it or run AI tuning.')} />

  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const isActive = job.status === 'pending' || job.status === 'running' || job.status === 'waiting'
  const previewUrl = isActive ? null : signedFileUrl(output?.pixelized_url || output?.preview_url || output?.source_url || job.input_image_url || '')
  const spriteSheetUrl = isActive ? null : signedFileUrl(output?.sprite_sheet_url || undefined)
  const spriteFps = spriteFpsFromJob(job)

  if (job.job_type === 'sprite_sheet') {
    const sheetInfo = buildSpriteSheetInfo(job, output)
    // 选中某个动作时，右侧预览改为展示该动作的序列（优先动图 GIF，回退该行 sheet），并同步帧数/网格/动作标签。
    const activeAction = action ?? null
    const actionPreviewUrl = !isActive && activeAction ? signedFileUrl(activeAction.gifUrl || activeAction.sheetUrl || undefined) : null
    const mosaicUrl = isActive ? null : signedFileUrl(output?.sprite_mosaic_url || undefined)
    const gridUrl = isActive ? null : signedFileUrl(output?.sprite_sheet_grid_url || undefined)
    const gifUrl = isActive ? null : signedFileUrl(output?.sprite_gif_url || undefined)
    const sequenceUrl = isActive ? null : signedFileUrl(output?.sequence_json_url || undefined)
    return (
      <div className="sticky top-24 grid gap-4">
        <PixPanel eyebrow={text('精灵表信息', 'Sprite sheet info')} title={`#${job.id}`} description={summarizePrompt(job.prompt || text('序列帧作品', 'Sprite sequence work'))} action={<PixStatusBadge status={job.status} />}>
          <div className="grid gap-5">
            <div className="grid gap-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold">{text('横向精灵表', 'Horizontal sprite sheet')}</p>
                {activeAction ? <Badge variant="outline">{activeAction.label}</Badge> : sheetInfo.sheetSize ? <Badge variant="outline">{sheetInfo.sheetSize}</Badge> : null}
              </div>
              <div className="pix-checkerboard overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
                {(actionPreviewUrl || spriteSheetUrl)
                  ? <img src={actionPreviewUrl || spriteSheetUrl || undefined} alt={activeAction ? activeAction.label : text('横向精灵表', 'Horizontal sprite sheet')} className="block h-auto w-full [image-rendering:pixelated]" />
                  : <div className="grid min-h-28 place-items-center text-sm text-muted-foreground">{isActive ? text('作品生成中…', 'Work is generating…') : text('暂无精灵表文件', 'No sprite sheet file')}</div>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <SpriteInfoCell label={text('单帧', 'Frame')} value={sheetInfo.frameSize} />
              <SpriteInfoCell label={text('帧数', 'Frames')} value={activeAction ? String(activeAction.frameIndices.length) : sheetInfo.frameCount} />
              <SpriteInfoCell label={text('网格', 'Grid')} value={activeAction ? `1×${activeAction.frameIndices.length}` : sheetInfo.grid} />
              <SpriteInfoCell label="FPS" value={sheetInfo.fps} />
              <SpriteInfoCell label={text('动作', 'Actions')} value={activeAction ? activeAction.label : sheetInfo.actions} />
              <SpriteInfoCell label={text('颜色', 'Colors')} value={sheetInfo.colors} />
            </div>
            <div className="flex flex-wrap gap-2">
              {spriteSheetUrl && <SpriteResourceLink href={spriteSheetUrl} label={text('打开 Sheet', 'Open sheet')} />}
              {mosaicUrl && <SpriteResourceLink href={mosaicUrl} label={text('原始 Mosaic', 'Source mosaic')} />}
              {gridUrl && <SpriteResourceLink href={gridUrl} label={text('二维网格', 'Grid sheet')} />}
              {gifUrl && <SpriteResourceLink href={gifUrl} label="GIF" />}
              {sequenceUrl && <SpriteResourceLink href={sequenceUrl} label="sequence.json" />}
            </div>
          </div>
        </PixPanel>
      </div>
    )
  }

  const sourcePath = output?.source_path || output?.pixelized_path || job.input_image_path || ''
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)

  async function submitLocal(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({ job_type: 'repixelize', prompt: null, input_image_path: sourcePath, client_request_id: crypto.randomUUID(), skip_vl: true, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edgeStylePixelize(edgeStyle) }), grid: buildGridDesign() })
  }

  async function submitAi(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    // 复用原作品的素材类型：参考图微调本质是“按原素材规则重绘”，不带类型会让 UI 组件 / Logo / 平铺纹理都被当成物品图标。
    const sourceAsset = asRecord(job?.params_json?.asset)
    const rawKind = typeof sourceAsset?.asset_kind === 'string' ? sourceAsset.asset_kind : ''
    const assetKind = (['item_icon', 'ui_component', 'tile_texture', 'game_logo'] as const).find((kind) => kind === rawKind) ?? 'item_icon'
    const rawTextureKind = typeof sourceAsset?.texture_kind === 'string' ? sourceAsset.texture_kind : 'auto'
    const textureKind = (['auto', 'generic_texture', 'terrain_ground', 'path_floor', 'wall_surface', 'wood_planks', 'water_liquid', 'foliage_canopy', 'roof_tile', 'metal_panel', 'fabric_carpet'] as const).find((kind) => kind === rawTextureKind) ?? 'auto'
    const subjectKind = assetKind === 'ui_component' ? 'single_ui' : assetKind === 'tile_texture' ? 'tileable_pattern' : assetKind === 'game_logo' ? 'logo_mark' : 'single_prop'
    await onSubmit({ job_type: 'image_to_image', prompt: aiPrompt, input_image_path: sourcePath, client_request_id: crypto.randomUUID(), skip_vl: false, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edgeStylePixelize(edgeStyle) }), grid: buildGridDesign(), asset: { name: '', asset_kind: assetKind, subject_kind: subjectKind, texture_kind: assetKind === 'tile_texture' ? textureKind as TextureKind : undefined } })
  }

  return (
    <div className="sticky top-24 grid gap-4">
      <PixPanel eyebrow={text('微调工位', 'Tuning station')} title={`#${job.id}`} description={summarizePrompt(job.prompt || text('上传图片作品', 'Uploaded image work'))} action={<PixStatusBadge status={job.status} />}>
        <SpriteSequencePreview sheetUrl={spriteSheetUrl} frames={output?.sprite_frames ?? []} fps={spriteFps} fallbackUrl={previewUrl} loading={isActive} label={isActive ? text('作品生成中…', 'Work is generating…') : text('暂无可预览源图', 'No source preview available')} className="min-h-44" />
      </PixPanel>
      {invalidSubAssetSize && <Alert variant="destructive">{text('素材最低支持 16×16。', 'Minimum asset size is 16×16.')}</Alert>}
      <form className="grid gap-4 rounded-lg border border-border bg-[hsl(var(--pix-mint)/.46)] p-5" onSubmit={submitLocal}>
        <div className="flex items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">{text('本地像素化', 'Local pixelize')}</h3><p className="text-sm text-muted-foreground">{text('免费 · 不消耗点数', 'Free · no credits used')}</p></div><Badge variant="secondary">FREE</Badge></div>
        <PixelControls compact pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={!removeBg} />
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={removeBg} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{text('透明背景', 'Transparent background')}</label>
        <Button type="submit" disabled={loading || !sourcePath || invalidSubAssetSize}>{text('重新像素化', 'Repixelize')}</Button>
      </form>
      <form className="grid gap-4 rounded-lg border border-border bg-[hsl(var(--pix-lavender)/.54)] p-5" onSubmit={submitAi}>
        <div className="flex items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">{text('AI 微调', 'AI tuning')}</h3><p className="text-sm text-muted-foreground">{text(`消耗 ${aiPrice} 点`, `Uses ${aiPrice} credits`)}</p></div><Badge variant="outline">{text(`${aiPrice} 点`, `${aiPrice} credits`)}</Badge></div>
        {!sourcePath && <Alert variant="warning">{text('当前作品没有可用源图，暂时无法微调。', 'This work has no source image available, so tuning is unavailable for now.')}</Alert>}
        <Textarea value={aiPrompt} rows={3} onChange={(event) => setAiPrompt(event.target.value)} />
        <p className="text-xs text-muted-foreground">{text('会按素材直出规则重绘成像素风;可在提示词里用「图1」指代原参考图,例如「把图1重绘成…」。', 'Redrawn into pixel art with the asset-output rules; in the prompt use “图1” (image 1) to refer to the source reference, e.g. “redraw 图1 as…”.')}</p>
        <Button type="submit" variant="outline" disabled={loading || !sourcePath || invalidSubAssetSize}>{text('AI 微调并入队', 'Queue AI tuning')}</Button>
      </form>
    </div>
  )
}

function spriteFpsFromJob(job: GenerationJob) {
  const sprite = asRecord(job.params_json?.sprite)
  const fps = Number(sprite?.fps)
  return Number.isFinite(fps) && fps > 0 ? fps : 8
}

function buildSpriteSheetInfo(job: GenerationJob, output?: JobOutput) {
  const sprite = asRecord(job.params_json?.sprite)
  const pixelize = asRecord(job.params_json?.pixelize)
  const frames = Array.isArray(output?.sprite_frames) ? output.sprite_frames : []
  const firstRect = frames.find((frame) => frame.sheet_rect)?.sheet_rect
  const frameSize = firstRect
    ? `${Math.round(firstRect.w)}×${Math.round(firstRect.h)}`
    : pairLabel(asNumberPair(pixelize?.output_size))
  const sheetPixelSize = sheetSizeFromFrames(frames)
  const sheetSize = sheetPixelSize ? `${sheetPixelSize.width}×${sheetPixelSize.height}` : null
  // 网格按真实横向精灵表推导（列=表宽/帧宽，行=表高/帧高），回退到生成请求的 mosaic rows/cols。
  // 旧逻辑直接用 mosaic 参数（如 9×4），与最终「9 帧 / 720×64 单行」对不上，容易误会。
  const gridFromSheet = sheetPixelSize && firstRect && firstRect.w > 0 && firstRect.h > 0
    ? { rows: Math.max(1, Math.round(sheetPixelSize.height / firstRect.h)), cols: Math.max(1, Math.round(sheetPixelSize.width / firstRect.w)) }
    : null
  const rows = gridFromSheet ? gridFromSheet.rows : Number(output?.sprite_grid?.rows ?? sprite?.rows)
  const cols = gridFromSheet ? gridFromSheet.cols : Number(output?.sprite_grid?.cols ?? sprite?.cols)
  const frameCount = Number(sprite?.frame_count) || frames.length
  const fps = spriteFpsFromJob(job)
  const rowOutputs = Array.isArray(output?.sprite_rows_outputs) ? output.sprite_rows_outputs : []
  const colors = Number(pixelize?.colors)
  return {
    frameSize,
    sheetSize,
    sheetPixelSize,
    frameCount: frameCount > 0 ? String(Math.round(frameCount)) : '—',
    grid: Number.isFinite(rows) && rows > 0 && Number.isFinite(cols) && cols > 0 ? `${Math.round(rows)}×${Math.round(cols)}` : '—',
    fps: `${Math.round(fps)}`,
    actions: rowOutputs.length > 0 ? String(rowOutputs.length) : '—',
    colors: Number.isFinite(colors) && colors > 0 ? String(Math.round(colors)) : '—',
  }
}

function SpriteInfoCell({ label, value }: { label: string; value: string | null }) {
  return <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]"><p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">{label}</p><p className="mt-1 font-semibold text-foreground">{value || '—'}</p></div>
}

function SpriteResourceLink({ href, label }: { href: string; label: string }) {
  return <a className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition hover:border-primary/50 hover:text-primary dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]" href={href} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>{label}</a>
}

function sheetSizeFromFrames(frames: NonNullable<JobOutput['sprite_frames']>) {
  const rects = frames.map((frame) => frame.sheet_rect).filter(Boolean)
  if (rects.length === 0) return null
  const width = Math.max(...rects.map((rect) => (rect?.x ?? 0) + (rect?.w ?? 0)))
  const height = Math.max(...rects.map((rect) => (rect?.y ?? 0) + (rect?.h ?? 0)))
  return width > 0 && height > 0 ? { width: Math.round(width), height: Math.round(height) } : null
}

function pairLabel(pair: [number, number] | null) {
  return pair ? `${pair[0]}×${pair[1]}` : '—'
}

function asNumberPair(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) return null
  const width = Number(value[0])
  const height = Number(value[1])
  return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0 ? [Math.round(width), Math.round(height)] : null
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}
