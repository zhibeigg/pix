import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { JobCreateRequest, JobType, PricingRule } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, parsePixelSize, type EdgeStyleChoice } from '../pixelize'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Input } from './ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { Badge } from './ui/badge'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixelControls } from './PixelControls'

type Props = { pricing: PricingRule[]; loading: boolean; token: string; onSubmit: (payload: JobCreateRequest) => Promise<void> }
type AssetKindChoice = 'item_icon' | 'ui_component' | 'tile_texture'

const PROMPT_MAX_LENGTH = 3000
const ROW_PROMPT_MAX_LENGTH = 600
const MAX_GRID_AXIS = 8

type SpritePreset = 'horizontal' | 'four_directions' | 'character_full' | 'custom'

type PresetSpec = {
  rows: number
  cols: number
  rowHints: (zh: boolean) => string[]
}

const SPRITE_PRESETS: Record<Exclude<SpritePreset, 'custom'>, PresetSpec> = {
  horizontal: {
    rows: 1,
    cols: 8,
    rowHints: () => [''],
  },
  four_directions: {
    rows: 4,
    cols: 8,
    rowHints: (zh) =>
      zh
        ? ['朝北行走的 8 帧循环', '朝东行走的 8 帧循环', '朝南行走的 8 帧循环', '朝西行走的 8 帧循环']
        : [
            '8-frame walk cycle facing north',
            '8-frame walk cycle facing east',
            '8-frame walk cycle facing south',
            '8-frame walk cycle facing west',
          ],
  },
  character_full: {
    rows: 8,
    cols: 8,
    rowHints: (zh) =>
      zh
        ? [
            '朝北 / 东北 行走的 8 帧循环',
            '朝东 / 东南 行走的 8 帧循环',
            '朝北方向的剑挥砍 8 帧',
            '朝东方向的弓箭射击 8 帧',
            '盾牌防守的 8 帧（覆盖各方向）',
            '朝南交互动作的 8 帧',
            '朝北受击 / 击退的 8 帧',
            '死亡序列的 8 帧',
          ]
        : [
            '8-frame walk cycle facing north / north-east',
            '8-frame walk cycle facing east / south-east',
            '8-frame north-facing sword swing',
            '8-frame east-facing bow shot',
            '8-frame shield-block stance covering multiple angles',
            '8-frame south-facing interaction (use object)',
            '8-frame north-facing hurt / knockback',
            '8-frame dying sequence',
          ],
  },
}

function ensureRowPromptsLength(values: string[], rows: number): string[] {
  const next = values.slice(0, rows)
  while (next.length < rows) next.push('')
  return next
}

export function SingleGeneratePanel({ pricing, loading, token, onSubmit }: Props) {
  const { text } = useI18n()
  const [jobType, setJobType] = useState<JobType>('asset')
  const [assetName, setAssetName] = useState(() => text('冰霜之心', 'Frost Heart'))
  const [assetKind, setAssetKind] = useState<AssetKindChoice>('item_icon')
  const [assetExtraPrompt, setAssetExtraPrompt] = useState('')
  const [prompt, setPrompt] = useState(() => text('一枚幻想 RPG 魔法药水图标，居中构图，轮廓清晰，透明背景', 'A fantasy RPG magic potion icon, centered composition, clear silhouette, transparent background'))
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(12)
  const [removeBg, setRemoveBg] = useState(true)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('outline')
  const [skipVl, setSkipVl] = useState(false)
  // 序列帧专用状态（仅 mosaic 单图模式）
  const [spritePreset, setSpritePreset] = useState<SpritePreset>('horizontal')
  const [rows, setRows] = useState(1)
  const [cols, setCols] = useState(8)
  const [rowPrompts, setRowPrompts] = useState<string[]>([''])
  const [fps, setFps] = useState(8)
  const [refImagePath, setRefImagePath] = useState('')
  const [refImageUrl, setRefImageUrl] = useState('')
  const [refUploading, setRefUploading] = useState(false)
  const [refUploadMessage, setRefUploadMessage] = useState('')

  const isAsset = jobType === 'asset'
  const isSprite = jobType === 'sprite_sheet'
  const isTileAsset = isAsset && assetKind === 'tile_texture'
  const basePrice = useMemo(() => pricing.find((item) => item.key === jobType)?.price_credits ?? 0, [pricing, jobType])
  const safeRows = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(rows || 1)))
  const safeCols = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(cols || 1)))
  const totalFrames = safeRows * safeCols
  const billingUnits = Math.max(1, Math.ceil(totalFrames / 9))
  const price = isSprite ? basePrice * billingUnits : basePrice
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const subjectKind = assetKind === 'ui_component' ? 'single_ui' : assetKind === 'tile_texture' ? 'tileable_pattern' : 'single_prop'
  const needsPrompt = jobType === 'text_to_image' || jobType === 'image_to_image' || isSprite
  const needsImage = jobType !== 'asset' && jobType !== 'text_to_image' && !isSprite
  const invalidGrid = isSprite && (safeRows < 1 || safeCols < 1 || safeRows > MAX_GRID_AXIS || safeCols > MAX_GRID_AXIS)
  const missingRowPrompts = isSprite && safeRows >= 2 && rowPrompts.slice(0, safeRows).some((value) => !value.trim())
  const submitBlocked = invalidSubAssetSize
    || invalidGrid
    || missingRowPrompts
    || (isAsset && !assetName.trim())
    || (needsPrompt && !prompt.trim())
    || (needsImage && !inputImagePath.trim())

  // 模式切换时重置默认参数
  useEffect(() => {
    if (jobType === 'asset') { setPixelSize('16x16'); setColors(12); setRemoveBg(true); setEdgeStyle('outline') }
    else if (jobType === 'sprite_sheet') { setPixelSize('64x64'); setColors(16); setRemoveBg(false); setFps(8); setSpritePreset('horizontal'); setRows(1); setCols(8); setRowPrompts(['']) }
    else { setPixelSize('128x128'); setColors(16); setRemoveBg(true) }
  }, [jobType])

  // asset_kind 切换时重置常用默认（平铺纹理：32×32 / 12 色 / 不抠透明 / hard 边缘）
  useEffect(() => {
    if (jobType !== 'asset') return
    if (assetKind === 'tile_texture') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(false); setEdgeStyle('hard')
    } else if (assetKind === 'item_icon') {
      setPixelSize('16x16'); setColors(12); setRemoveBg(true); setEdgeStyle('outline')
    } else if (assetKind === 'ui_component') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(true); setEdgeStyle('outline')
    }
  }, [assetKind, jobType])

  // 应用预设
  function applyPreset(preset: SpritePreset) {
    setSpritePreset(preset)
    if (preset === 'custom') return
    const spec = SPRITE_PRESETS[preset]
    setRows(spec.rows)
    setCols(spec.cols)
    const hints = spec.rowHints(true)
    const enHints = spec.rowHints(false)
    const localized = hints.map((zh, index) => text(zh, enHints[index] ?? ''))
    setRowPrompts(ensureRowPromptsLength(localized, spec.rows))
  }

  function updateRows(value: number) {
    const next = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(value || 1)))
    setRows(next)
    setRowPrompts((prev) => ensureRowPromptsLength(prev, next))
    setSpritePreset('custom')
  }

  function updateCols(value: number) {
    const next = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(value || 1)))
    setCols(next)
    setSpritePreset('custom')
  }

  function updateRowPrompt(index: number, value: string) {
    setRowPrompts((prev) => {
      const next = ensureRowPromptsLength(prev, safeRows).slice()
      next[index] = value
      return next
    })
    setSpritePreset('custom')
  }

  async function uploadFile(file: File | undefined) {
    if (!file) return
    setUploading(true); setUploadMessage(text('上传中…', 'Uploading…'))
    try {
      const uploaded = await api.uploadImage(token, file)
      setInputImagePath(uploaded.path); setUploadUrl(signedFileUrl(uploaded.url)); setUploadMessage(text('图片已上传，可继续提交任务。', 'Image uploaded. You can submit the job now.'))
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : text('上传失败', 'Upload failed'))
    } finally { setUploading(false) }
  }

  async function uploadReferenceFile(file: File | undefined) {
    if (!file) return
    setRefUploading(true); setRefUploadMessage(text('上传参考图…', 'Uploading reference…'))
    try {
      const uploaded = await api.uploadImage(token, file)
      setRefImagePath(uploaded.path); setRefImageUrl(signedFileUrl(uploaded.url)); setRefUploadMessage(text('参考图已就绪，将以图生图模式保留角色设计。', 'Reference ready. Image-to-image mode will preserve the character design.'))
    } catch (error) {
      setRefUploadMessage(error instanceof Error ? error.message : text('参考图上传失败', 'Reference upload failed'))
    } finally { setRefUploading(false) }
  }

  function clearReference() {
    setRefImagePath(''); setRefImageUrl(''); setRefUploadMessage('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const edge = edgeStylePixelize(edgeStyle)
    if (isAsset) {
      await onSubmit({ job_type: 'asset', prompt: assetName.trim(), input_image_path: null, client_request_id: crypto.randomUUID(), pixelize: buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }), grid: buildGridDesign(), asset: { name: assetName.trim(), extra_prompt: assetExtraPrompt.trim(), asset_kind: assetKind, subject_kind: subjectKind, no_preview: false } })
      return
    }
    if (isSprite) {
      const safeFps = Math.max(1, Math.min(60, Math.round(fps || 8)))
      const cleanRowPrompts = ensureRowPromptsLength(rowPrompts, safeRows).map((value) => value.trim())
      await onSubmit({
        job_type: 'sprite_sheet',
        prompt: prompt.trim(),
        input_image_path: null,
        client_request_id: crypto.randomUUID(),
        skip_vl: false,
        pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: false, ...edge }),
        grid: buildGridDesign(),
        sprite: {
          rows: safeRows,
          cols: safeCols,
          row_prompts: cleanRowPrompts,
          reference_image_path: refImagePath || null,
          frame_count: totalFrames,
          fps: safeFps,
          gif_export: false,
          duration_ms: Math.max(20, Math.round(1000 / safeFps)),
          loop: 0,
        },
      })
      return
    }
    await onSubmit({ job_type: jobType, prompt: needsPrompt ? prompt : null, input_image_path: needsImage ? inputImagePath : null, client_request_id: crypto.randomUUID(), skip_vl: skipVl, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }), grid: buildGridDesign() })
  }

  return (
      <PixPanel eyebrow={text('单张试做', 'Single test')} title={text('任务配方', 'Job recipe')} action={<Badge variant="info">{isSprite ? text(`预计 ${billingUnits} × ${basePrice} = ${price} 点（共 ${totalFrames} 帧）`, `Estimated ${billingUnits} × ${basePrice} = ${price} credits (${totalFrames} frames)`) : text(`预计 ${price} 点`, `Estimated ${price} credits`)}</Badge>}>
      <form className="grid gap-5" onSubmit={submit}>
        <PixField label={text('模式', 'Mode')}>
          <Select value={jobType} onValueChange={(value) => setJobType(value as JobType)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="asset">{text('游戏素材直出', 'Game asset output')}</SelectItem>
              <SelectItem value="text_to_image">{text('文生图', 'Text to image')}</SelectItem>
              <SelectItem value="image_to_image">{text('图生图 / AI 微调', 'Image to image / AI tune')}</SelectItem>
              <SelectItem value="sprite_sheet">{text('序列帧', 'Sprite sequence')}</SelectItem>
              <SelectItem value="local_pixelize">{text('本地像素化', 'Local pixelize')}</SelectItem>
            </SelectContent>
          </Select>
        </PixField>

        {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
          <PixField label={text('素材类型', 'Asset type')}>
            <Select value={assetKind} onValueChange={(value) => setAssetKind(value as AssetKindChoice)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="item_icon">{text('物品图标', 'Item icon')}</SelectItem>
                <SelectItem value="ui_component">{text('UI 组件', 'UI component')}</SelectItem>
                <SelectItem value="tile_texture">{text('平铺纹理', 'Tileable texture')}</SelectItem>
              </SelectContent>
            </Select>
          </PixField>
          <PixField label={isTileAsset ? text('纹理主题 / 题材', 'Texture theme') : text('主体', 'Subject')}><Input value={assetName} placeholder={isTileAsset ? text('例如：苔藓砖石路面、木板地、像素草地', 'e.g. mossy cobblestone, wood planks, grass field') : text('例如：冰霜之心', 'e.g. Frost Heart')} onChange={(e) => setAssetName(e.target.value)} /></PixField>
          <PixField label={text('额外风格描述（可选）', 'Extra style notes (optional)')}><Textarea value={assetExtraPrompt} rows={3} maxLength={PROMPT_MAX_LENGTH} placeholder={isTileAsset ? text('可补充配色、细节密度、年代感等。无需提"无缝平铺"，模板已内置。', 'Optional: palette, detail density, era. "Seamless / tileable" is already enforced by template.') : text('可留空；如需补充材质、颜色或题材风格再填写。', 'Optional; add material, color, or theme notes if needed.')} onChange={(e) => setAssetExtraPrompt(e.target.value)} /></PixField>
          {isTileAsset && <Alert variant="info">{text('平铺纹理：模型直接铺满画布，后端只做完美像素对齐，不做抠透明、不做主体裁剪、不做 VL 评分。', 'Tile texture: the model fills the entire canvas; the backend only runs perfect-pixel alignment — no transparency cutout, no subject crop, no VL ranking.')}</Alert>}
        </div>}

        {needsPrompt && <PixField label={isSprite ? text('主体 / 角色描述', 'Subject / character brief') : text('素材描述', 'Asset description')} hint={isSprite ? text('描述角色身份、服装、配色与风格；逐行动作下面单独写。', 'Describe identity, costume, palette and style. Per-row actions go below.') : text('写清主体、材质和用途。', 'Describe the subject, material, and use case clearly.')}><Textarea value={prompt} rows={isSprite ? 4 : 5} maxLength={PROMPT_MAX_LENGTH} onChange={(e) => setPrompt(e.target.value)} /></PixField>}

        {isSprite && (
          <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
            <PixField label={text('参考角色立绘（可选）', 'Reference character art (optional)')} hint={text('提供后将使用图生图，让每个单元格保留同一角色设计。', 'Image-to-image keeps the same character design across all cells.')}>
              <div className="grid gap-3">
                <Button type="button" variant="outline" asChild>
                  <label className="cursor-pointer">
                    <Upload />{refUploading ? text('上传参考图…', 'Uploading reference…') : refImagePath ? text('替换参考图', 'Replace reference') : text('上传参考图', 'Upload reference')}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => void uploadReferenceFile(event.currentTarget.files?.[0])} />
                  </label>
                </Button>
                {refUploadMessage && <Alert variant={refUploadMessage.includes('失败') || refUploadMessage.toLowerCase().includes('failed') ? 'destructive' : 'info'}>{refUploadMessage}</Alert>}
                {refImagePath && (
                  <div className="grid gap-2">
                    <PixPreviewFrame url={refImageUrl} loading={refUploading} label={text('参考角色预览', 'Reference preview')} />
                    <Button type="button" variant="ghost" size="sm" onClick={clearReference}>{text('移除参考图', 'Remove reference')}</Button>
                  </div>
                )}
              </div>
            </PixField>

            <PixField label={text('布局预设', 'Layout preset')}>
              <Select value={spritePreset} onValueChange={(value) => applyPreset(value as SpritePreset)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="horizontal">{text('1 行 × 8 帧（横排动作）', '1×8 horizontal action')}</SelectItem>
                  <SelectItem value="four_directions">{text('4 行 × 8 帧（四方向行走）', '4×8 four-direction walk')}</SelectItem>
                  <SelectItem value="character_full">{text('8 行 × 8 帧（角色全动作集）', '8×8 full character action set')}</SelectItem>
                  <SelectItem value="custom">{text('自定义网格', 'Custom grid')}</SelectItem>
                </SelectContent>
              </Select>
            </PixField>

            <div className="grid gap-3 sm:grid-cols-3">
              <PixField label={text('行 rows（1~8）', 'Rows (1–8)')}>
                <Input type="number" min={1} max={MAX_GRID_AXIS} value={safeRows} onChange={(e) => updateRows(Number(e.target.value))} />
              </PixField>
              <PixField label={text('列 cols（1~8）', 'Cols (1–8)')}>
                <Input type="number" min={1} max={MAX_GRID_AXIS} value={safeCols} onChange={(e) => updateCols(Number(e.target.value))} />
              </PixField>
              <PixField label={text('总帧数', 'Total frames')}>
                <Input value={`${totalFrames}`} readOnly />
              </PixField>
            </div>

            {safeRows >= 2 && (
              <div className="grid gap-3 rounded-lg border border-border bg-background/40 p-3">
                <div className="text-xs text-muted-foreground">{text(`为每一行写一段动作描述（共 ${safeRows} 行，每行 ${safeCols} 帧）`, `Describe the action for each row (${safeRows} rows × ${safeCols} frames)`)}</div>
                {Array.from({ length: safeRows }, (_, index) => (
                  <PixField key={`row-${index}`} label={text(`第 ${index + 1} 行动作`, `Row ${index + 1} action`)}>
                    <Textarea
                      value={rowPrompts[index] ?? ''}
                      rows={2}
                      maxLength={ROW_PROMPT_MAX_LENGTH}
                      placeholder={text('例如：朝东行走的 8 帧循环', 'e.g. 8-frame walk cycle facing east')}
                      onChange={(e) => updateRowPrompt(index, e.target.value)}
                    />
                  </PixField>
                ))}
              </div>
            )}

            {safeRows === 1 && (
              <PixField label={text('动作描述（可选，留空使用主体描述）', 'Action description (optional)')}>
                <Textarea
                  value={rowPrompts[0] ?? ''}
                  rows={2}
                  maxLength={ROW_PROMPT_MAX_LENGTH}
                  placeholder={text('例如：火焰法师挥杖释放火球的 8 帧动作', 'e.g. 8-frame fire mage casting a fireball')}
                  onChange={(e) => updateRowPrompt(0, e.target.value)}
                />
              </PixField>
            )}

            <PixField label={text('播放 FPS', 'Playback FPS')}>
              <Input type="number" min={1} max={60} value={fps} onChange={(e) => setFps(Number(e.target.value))} />
            </PixField>
          </div>
        )}

        {needsImage && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? text('上传中…', 'Uploading…') : text('上传图片', 'Upload image')}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => void uploadFile(event.currentTarget.files?.[0])} /></label></Button>{uploadMessage && <Alert variant={uploadMessage.includes('失败') ? 'destructive' : 'info'}>{uploadMessage}</Alert>}<PixPreviewFrame url={uploadUrl} loading={uploading} label={uploading ? text('上传中…', 'Uploading…') : text('等待上传预览', 'Waiting for upload preview')} /></div>}

        <PixelControls pixelLabel={isSprite ? text('单帧尺寸', 'Frame size') : text('像素尺寸', 'Pixel size')} pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={isSprite || isTileAsset || !removeBg} />

        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={isTileAsset ? false : removeBg} disabled={isSprite || isTileAsset} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{text('透明背景', 'Transparent background')}</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={isSprite || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? text('素材直出默认视觉理解策略', 'Default vision policy for asset output') : text('跳过参考图理解', 'Skip reference understanding')}</label></div>

        {invalidSubAssetSize && <Alert variant="destructive">{text('素材最低支持 16×16。', 'Minimum asset size is 16×16.')}</Alert>}
        {invalidGrid && <Alert variant="destructive">{text('序列帧每行/每列最多 8。', 'Sprite sequence rows and cols are capped at 8.')}</Alert>}
        {missingRowPrompts && <Alert variant="destructive">{text('多行序列帧需要为每一行填写动作描述。', 'Multi-row sequences require an action description for each row.')}</Alert>}
        <Button type="submit" size="lg" disabled={loading || submitBlocked}>{loading ? text('提交中…', 'Submitting…') : isSprite ? text('生成序列帧', 'Generate sprite sequence') : isAsset ? (isTileAsset ? text('生成平铺纹理', 'Generate tile texture') : text('生成游戏素材', 'Generate game asset')) : text('生成单张素材', 'Generate single asset')}</Button>
      </form>
    </PixPanel>
  )
}
