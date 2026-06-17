import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { GenerationJob, ImageModelInfo, ImageModelsResponse, JobCreateRequest, JobType, PricingDiscount, PricingRule, TextureKind } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, parsePixelSize, type EdgeStyleChoice } from '../pixelize'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Input } from './ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { EstimateBadge } from './EstimateBadge'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixelControls } from './PixelControls'

type Props = { pricing: PricingRule[]; discount?: PricingDiscount | null; loading: boolean; token: string; imageModels: ImageModelsResponse; reuseJobSeed?: { revision: number; job: GenerationJob } | null; onSubmit: (payload: JobCreateRequest) => Promise<void> }
type AssetKindChoice = 'item_icon' | 'ui_component' | 'tile_texture' | 'game_logo'

type TextureKindOption = { value: TextureKind; zh: string; en: string }

const PROMPT_MAX_LENGTH = 3000
const ROW_PROMPT_MAX_LENGTH = 600
const MAX_GRID_AXIS = 8
const LOGO_SIZE_OPTIONS = ['64x32', '96x48', '128x64', '192x96', '256x128']
const UI_COMPONENT_IMAGE_SIZE = 'auto'
const TEXTURE_KIND_OPTIONS: TextureKindOption[] = [
  { value: 'auto', zh: '自动识别', en: 'Auto detect' },
  { value: 'generic_texture', zh: '通用纹理', en: 'Generic texture' },
  { value: 'terrain_ground', zh: '地表 / 地形', en: 'Terrain ground' },
  { value: 'path_floor', zh: '道路 / 地砖', en: 'Path / floor' },
  { value: 'wall_surface', zh: '墙壁 / 岩壁', en: 'Wall surface' },
  { value: 'wood_planks', zh: '木板 / 树皮', en: 'Wood planks' },
  { value: 'water_liquid', zh: '水面 / 液体', en: 'Water / liquid' },
  { value: 'foliage_canopy', zh: '树叶 / 草丛', en: 'Foliage canopy' },
  { value: 'roof_tile', zh: '屋顶瓦片', en: 'Roof tile' },
  { value: 'metal_panel', zh: '金属面板', en: 'Metal panel' },
  { value: 'fabric_carpet', zh: '布料 / 地毯', en: 'Fabric / carpet' },
]

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

function modelItems(imageModels: ImageModelsResponse): ImageModelInfo[] {
  const byId = new Map((imageModels.items ?? []).map((item) => [item.id, item]))
  return imageModels.models.map((id) => byId.get(id) ?? {
    id,
    label: id,
    providers: [],
    operations: ['text_to_image', 'image_to_image'],
    sizes: [],
    qualities: [],
    output_formats: [],
    protocols: [],
    provider_count: 0,
  })
}

function supportsImageToImage(model: ImageModelInfo | undefined) {
  return !model || model.operations.length === 0 || model.operations.includes('image_to_image')
}

function modelOptionLabel(model: ImageModelInfo) {
  const providers = model.provider_count || model.providers.length
  return providers > 1 ? `${model.label || model.id} · ${providers} providers` : (model.label || model.id)
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function numberValue(value: unknown): number | null {
  const next = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
  return Number.isFinite(next) ? next : null
}

function booleanValue(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function pixelSizeValue(value: unknown): string | null {
  if (!Array.isArray(value) || value.length !== 2) return null
  const width = numberValue(value[0])
  const height = numberValue(value[1])
  return width && height ? `${Math.round(width)}x${Math.round(height)}` : null
}

function assetKindValue(value: unknown): AssetKindChoice | null {
  return value === 'item_icon' || value === 'ui_component' || value === 'tile_texture' || value === 'game_logo' ? value : null
}

function textureKindValue(value: unknown): TextureKind | null {
  return TEXTURE_KIND_OPTIONS.some((item) => item.value === value) ? value as TextureKind : null
}

function edgeStyleValue(value: unknown): EdgeStyleChoice | null {
  return value === 'hard' || value === 'outline' || value === 'feather' ? value : null
}

function rowPromptValues(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => stringValue(item)) : []
}

function reusableWorkbenchType(job: GenerationJob): JobType {
  if (job.job_type === 'sprite_sheet') return 'sprite_sheet'
  if (job.job_type === 'local_pixelize' || job.job_type === 'repixelize') return 'local_pixelize'
  return 'asset'
}

export function SingleGeneratePanel({ pricing, discount, loading, token, imageModels, reuseJobSeed, onSubmit }: Props) {
  const { text } = useI18n()
  const [jobType, setJobType] = useState<JobType>('asset')
  const [imageModel, setImageModel] = useState(imageModels.default)
  const availableImageModels = useMemo(() => modelItems(imageModels), [imageModels])
  const selectedModelInfo = useMemo(() => availableImageModels.find((item) => item.id === imageModel), [availableImageModels, imageModel])
  const selectedModelSupportsI2I = supportsImageToImage(selectedModelInfo)
  const skipNextModeResetRef = useRef(false)
  const skipNextAssetResetRef = useRef(false)
  const lastAppliedReuseRevisionRef = useRef<number | null>(null)
  const [assetName, setAssetName] = useState(() => text('冰霜之心', 'Frost Heart'))
  const [assetKind, setAssetKind] = useState<AssetKindChoice>('item_icon')
  const [textureKind, setTextureKind] = useState<TextureKind>('auto')
  const [assetExtraPrompt, setAssetExtraPrompt] = useState('')
  const [prompt, setPrompt] = useState(() => text('一枚幻想 RPG 魔法药水图标，居中构图，轮廓清晰，透明背景', 'A fantasy RPG magic potion icon, centered composition, clear silhouette, transparent background'))
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  // 素材直出可选参考图
  const [assetRefPath, setAssetRefPath] = useState('')
  const [assetRefUrl, setAssetRefUrl] = useState('')
  const [assetRefUploading, setAssetRefUploading] = useState(false)
  const [assetRefMessage, setAssetRefMessage] = useState('')
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(8)
  const [removeBg, setRemoveBg] = useState(true)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('hard')
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
  const isLocalPixelize = jobType === 'local_pixelize'
  const isTileAsset = isAsset && assetKind === 'tile_texture'
  const isLogoAsset = isAsset && assetKind === 'game_logo'
  // 平铺纹理不走参考图模式；普通素材参考图仍保留 asset job_type，以便继续使用素材直出 prompt。
  const assetSupportsReference = isAsset && (assetKind === 'item_icon' || assetKind === 'ui_component' || assetKind === 'game_logo')
  const hasAssetReference = assetSupportsReference && !!assetRefPath
  const basePrice = useMemo(() => {
    // 素材直出 + 参考图 时，按图生图价位计费；Logo 会保留 asset job_type，但后端同样按 image_to_image 取价。
    const billingKey = hasAssetReference ? 'image_to_image' : jobType
    return pricing.find((item) => item.key === billingKey)?.price_credits ?? 0
  }, [pricing, jobType, hasAssetReference])
  const safeRows = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(rows || 1)))
  const safeCols = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(cols || 1)))
  const totalFrames = safeRows * safeCols
  const billingUnits = Math.max(1, Math.ceil(totalFrames / 9))
  const price = isSprite ? basePrice * billingUnits : basePrice
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const subjectKind = assetKind === 'ui_component' ? 'single_ui' : assetKind === 'tile_texture' ? 'tileable_pattern' : assetKind === 'game_logo' ? 'logo_mark' : 'single_prop'
  const uiComponentImageSize = assetKind === 'ui_component' ? UI_COMPONENT_IMAGE_SIZE : undefined
  const assetNameLabel = isLogoAsset ? text('Logo 标题 / 品牌名', 'Logo title / brand name') : isTileAsset ? text('纹理主题 / 题材', 'Texture theme') : text('主体', 'Subject')
  const assetNamePlaceholder = isLogoAsset
    ? text('例如：星尘纪元、PIX FORGE、龙焰', 'e.g. Starfall Age, PIX FORGE, Dragonflame')
    : isTileAsset
      ? text('例如：苔藓砖石路面、木板地、像素草地', 'e.g. mossy cobblestone, wood planks, grass field')
      : text('例如：冰霜之心', 'e.g. Frost Heart')
  const assetExtraPlaceholder = isLogoAsset
    ? text('可补充字体气质、徽章形状、配色、题材氛围。文字只会使用上方标题。', 'Optional: lettering mood, emblem shape, palette, genre atmosphere. Text should only use the title above.')
    : isTileAsset
      ? text('可补充配色、细节密度、年代感等。无需提"无缝平铺"，模板已内置。', 'Optional: palette, detail density, era. "Seamless / tileable" is already enforced by template.')
      : text('可留空；如需补充材质、颜色或题材风格再填写。', 'Optional; add material, color, or theme notes if needed.')
  const assetReferenceHint = isLogoAsset
    ? text('提供后会保留参考图的徽章轮廓、主色调和字形气质，但最终文字只使用上方 Logo 标题。', 'When provided, it preserves the reference emblem silhouette, main color mood, and lettering attitude, while final text only uses the logo title above.')
    : text('提供后会先把参考图理解为像素风参考，再按素材直出 Prompt 重绘；不是简单处理上传图。留空走默认文生图素材直出。', 'When provided, the reference is first interpreted as pixel-art inspiration, then redrawn with the asset-output prompt. It is not merely processed as the uploaded image. Leave empty for text-to-image asset output.')
  const assetReferenceAttachedMessage = isLogoAsset
    ? text('已附带参考图：将保留参考图的 Logo 轮廓、主色调和字形气质，并按上方标题生成。', 'With a reference image attached, the logo keeps the reference silhouette, color mood, and lettering attitude while using the title above.')
    : text('已附带参考图：将按素材直出规则重绘为像素风，参考图只作为构图、轮廓和配色灵感。', 'With a reference image attached, the job redraws it as pixel art using asset-output rules; the reference only guides composition, silhouette, and color mood.')
  const invalidGrid = isSprite && (safeRows < 1 || safeCols < 1 || safeRows > MAX_GRID_AXIS || safeCols > MAX_GRID_AXIS)
  const missingRowPrompts = isSprite && safeRows >= 2 && rowPrompts.slice(0, safeRows).some((value) => !value.trim())
  const submitBlocked = invalidSubAssetSize
    || invalidGrid
    || missingRowPrompts
    || (isAsset && !assetName.trim())
    || (isSprite && !prompt.trim())
    || ((hasAssetReference || (isSprite && !!refImagePath)) && !selectedModelSupportsI2I)
    || (isLocalPixelize && !inputImagePath.trim())

  useEffect(() => {
    if (!availableImageModels.some((item) => item.id === imageModel)) {
      setImageModel(imageModels.default || availableImageModels[0]?.id || 'image2')
    }
  }, [availableImageModels, imageModel, imageModels.default])

  // 模式切换时重置默认参数；作品复用会一次性回填旧参数，跳过对应的自动默认值覆盖。
  useEffect(() => {
    if (skipNextModeResetRef.current) { skipNextModeResetRef.current = false; return }
    if (jobType === 'asset') { setPixelSize('16x16'); setColors(8); setRemoveBg(true); setEdgeStyle('hard') }
    else if (jobType === 'sprite_sheet') { setPixelSize('64x64'); setColors(16); setRemoveBg(false); setFps(8); setSpritePreset('horizontal'); setRows(1); setCols(8); setRowPrompts(['']) }
    else { setPixelSize('128x128'); setColors(16); setRemoveBg(true) }
  }, [jobType])

  // asset_kind 切换时重置常用默认：平铺纹理铺满画布；Logo 走宽幅透明 PNG，不额外描边。
  useEffect(() => {
    if (jobType !== 'asset') return
    if (skipNextAssetResetRef.current) { skipNextAssetResetRef.current = false; return }
    if (assetKind === 'tile_texture') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(false); setEdgeStyle('hard'); setTextureKind('auto')
      // 切到平铺纹理时清掉之前的参考图（不支持）
      setAssetRefPath(''); setAssetRefUrl(''); setAssetRefMessage('')
    } else if (assetKind === 'game_logo') {
      setPixelSize('128x64'); setColors(24); setRemoveBg(true); setEdgeStyle('hard')
    } else if (assetKind === 'item_icon') {
      setPixelSize('16x16'); setColors(8); setRemoveBg(true); setEdgeStyle('hard')
    } else if (assetKind === 'ui_component') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(true); setEdgeStyle('outline')
    }
  }, [assetKind, jobType])

  useEffect(() => {
    if (!reuseJobSeed || lastAppliedReuseRevisionRef.current === reuseJobSeed.revision) return
    lastAppliedReuseRevisionRef.current = reuseJobSeed.revision
    const job = reuseJobSeed.job
    const params = asRecord(job.params_json)
    const pixelize = asRecord(params?.pixelize)
    const sprite = asRecord(params?.sprite)
    const asset = asRecord(params?.asset)
    const nextJobType = reusableWorkbenchType(job)
    const nextAssetKind = assetKindValue(asset?.asset_kind) ?? 'item_icon'
    const nextTextureKind = textureKindValue(asset?.texture_kind) ?? 'auto'

    if (nextJobType !== jobType) skipNextModeResetRef.current = true
    if (nextJobType === 'asset' && nextAssetKind !== assetKind) skipNextAssetResetRef.current = true
    setJobType(nextJobType)

    const model = stringValue(params?.image_model)
    if (model && availableImageModels.some((item) => item.id === model)) setImageModel(model)
    else if (!model) setImageModel(imageModels.default || availableImageModels[0]?.id || 'image2')

    const reusedPixelSize = pixelSizeValue(pixelize?.output_size)
    if (reusedPixelSize) setPixelSize(reusedPixelSize)
    const reusedColors = numberValue(pixelize?.colors)
    if (reusedColors !== null) setColors(Math.max(1, Math.round(reusedColors)))
    const reusedRemoveBg = booleanValue(pixelize?.remove_bg)
    if (reusedRemoveBg !== null) setRemoveBg(reusedRemoveBg)
    const reusedEdgeStyle = edgeStyleValue(pixelize?.edge_style)
    if (reusedEdgeStyle) setEdgeStyle(reusedEdgeStyle)
    setSkipVl(Boolean(params?.skip_vl))

    if (nextJobType === 'sprite_sheet') {
      const nextRows = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(numberValue(sprite?.rows) ?? 1)))
      const nextCols = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(numberValue(sprite?.cols) ?? 8)))
      const nextFps = Math.max(1, Math.min(60, Math.round(numberValue(sprite?.fps) ?? 8)))
      const nextRowPrompts = ensureRowPromptsLength(rowPromptValues(sprite?.row_prompts), nextRows)
      setPrompt(job.prompt?.trim() || '')
      setRows(nextRows)
      setCols(nextCols)
      setFps(nextFps)
      setRowPrompts(nextRowPrompts)
      setSpritePreset('custom')
      const referencePath = stringValue(sprite?.reference_image_path)
      setRefImagePath(referencePath)
      setRefImageUrl('')
      setRefUploadMessage(referencePath ? text('已复用原任务的参考图路径。', 'Reused the original job reference image path.') : '')
      setAssetRefPath(''); setAssetRefUrl(''); setAssetRefMessage('')
      setInputImagePath(''); setUploadUrl(''); setUploadMessage('')
      setRemoveBg(false)
      return
    }

    if (nextJobType === 'local_pixelize') {
      setInputImagePath(job.input_image_path ?? '')
      setUploadUrl(signedFileUrl(job.input_image_url ?? undefined))
      setUploadMessage(job.input_image_path ? text('已复用原任务的输入图片。', 'Reused the original input image.') : '')
      setAssetRefPath(''); setAssetRefUrl(''); setAssetRefMessage('')
      setRefImagePath(''); setRefImageUrl(''); setRefUploadMessage('')
      return
    }

    setAssetKind(nextAssetKind)
    setTextureKind(nextAssetKind === 'tile_texture' ? nextTextureKind : 'auto')
    const assetSubject = stringValue(asset?.name) || job.prompt?.trim() || ''
    setAssetName(assetSubject)
    setAssetExtraPrompt(stringValue(asset?.extra_prompt))
    setPrompt(job.prompt?.trim() || assetSubject)
    const referencePath = job.input_image_path ?? ''
    setAssetRefPath(referencePath)
    setAssetRefUrl(signedFileUrl(job.input_image_url ?? undefined))
    setAssetRefMessage(referencePath ? text('已复用原任务的参考图。', 'Reused the original reference image.') : '')
    setRefImagePath(''); setRefImageUrl(''); setRefUploadMessage('')
    setInputImagePath(''); setUploadUrl(''); setUploadMessage('')
  }, [availableImageModels, assetKind, imageModels.default, jobType, reuseJobSeed, text])

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

  async function uploadAssetReferenceFile(file: File | undefined) {
    if (!file) return
    setAssetRefUploading(true); setAssetRefMessage(text('上传参考图…', 'Uploading reference…'))
    try {
      const uploaded = await api.uploadImage(token, file)
      const readyMessage = isLogoAsset
        ? text('参考图已就绪，提交后将保留其 Logo 气质并按上方标题生成。', 'Reference ready. The logo will keep its visual attitude while using the title above.')
        : text('参考图已就绪，提交后将按素材直出规则重绘为像素风。', 'Reference ready. The job will redraw it as pixel art using the asset-output rules.')
      setAssetRefPath(uploaded.path); setAssetRefUrl(signedFileUrl(uploaded.url)); setAssetRefMessage(readyMessage)
    } catch (error) {
      setAssetRefMessage(error instanceof Error ? error.message : text('参考图上传失败', 'Reference upload failed'))
    } finally { setAssetRefUploading(false) }
  }

  function clearAssetReference() {
    setAssetRefPath(''); setAssetRefUrl(''); setAssetRefMessage('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (submitBlocked) return
    const edge = edgeStylePixelize(edgeStyle)
    // 仅在用户选了非默认模型时传 image_model，避免覆盖后端配置
    const modelOverride = imageModel !== imageModels.default ? imageModel : undefined
    if (isAsset) {
      const assetExtra = assetExtraPrompt.trim()
      const subject = assetName.trim()
      // 素材 + 参考图仍提交 asset，让后端使用素材直出 prompt 模板；参考图只作为重绘依据。
      if (hasAssetReference) {
        await onSubmit({
          job_type: 'asset',
          prompt: subject,
          input_image_path: assetRefPath,
          client_request_id: crypto.randomUUID(),
          image_size: uiComponentImageSize,
          image_model: modelOverride,
          skip_vl: skipVl,
          pixelize: buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }),
          grid: buildGridDesign(),
          asset: { name: subject, extra_prompt: assetExtra, asset_kind: assetKind, subject_kind: subjectKind, texture_kind: isTileAsset ? textureKind : undefined, no_preview: false },
        })
        return
      }
      await onSubmit({
        job_type: 'asset',
        prompt: subject,
        input_image_path: null,
        client_request_id: crypto.randomUUID(),
        image_size: uiComponentImageSize,
        image_model: modelOverride,
        pixelize: buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }),
        grid: buildGridDesign(),
        asset: { name: subject, extra_prompt: assetExtra, asset_kind: assetKind, subject_kind: subjectKind, no_preview: false },
      })
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
        image_model: modelOverride,
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
    // 本地像素化：上传图 + 像素化参数
    await onSubmit({
      job_type: jobType,
      prompt: null,
      input_image_path: inputImagePath,
      client_request_id: crypto.randomUUID(),
      image_model: modelOverride,
      skip_vl: skipVl,
      pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }),
      grid: buildGridDesign(),
    })
  }

  return (
      <PixPanel eyebrow={text('单张试做', 'Single test')} title={text('任务配方', 'Job recipe')} action={<EstimateBadge price={price} discount={discount} sprite={isSprite ? { billingUnits, basePrice, totalFrames } : null} />}>
      <form className="grid gap-5" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <PixField label={text('模式', 'Mode')}>
            <Select value={jobType} onValueChange={(value) => setJobType(value as JobType)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="asset">{text('游戏素材直出', 'Game asset output')}</SelectItem>
                <SelectItem value="sprite_sheet">{text('序列帧', 'Sprite sequence')}</SelectItem>
                <SelectItem value="local_pixelize">{text('本地像素化', 'Local pixelize')}</SelectItem>
              </SelectContent>
            </Select>
          </PixField>
          <PixField label={text('生图模型', 'Image model')}>
            <Select value={imageModel} onValueChange={setImageModel}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {availableImageModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>{modelOptionLabel(m)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </PixField>
        </div>
        {!selectedModelSupportsI2I && (hasAssetReference || (isSprite && refImagePath)) && <Alert variant="warning">{text('当前模型不支持参考图 / 图生图，请切换支持 image-to-image 的模型或移除参考图。', 'The selected model does not support reference images / image-to-image. Switch to a model with image-to-image support or remove the reference.')}</Alert>}

        {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
          <PixField label={text('素材类型', 'Asset type')}>
            <Select value={assetKind} onValueChange={(value) => setAssetKind(value as AssetKindChoice)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="item_icon">{text('物品图标', 'Item icon')}</SelectItem>
                <SelectItem value="ui_component">{text('UI 组件', 'UI component')}</SelectItem>
                <SelectItem value="tile_texture">{text('平铺纹理', 'Tileable texture')}</SelectItem>
                <SelectItem value="game_logo">{text('游戏 Logo', 'Game logo')}</SelectItem>
              </SelectContent>
            </Select>
          </PixField>
          {isTileAsset && (
            <PixField label={text('纹理类型', 'Texture type')} hint={text('选择常见游戏地图纹理类型；自动识别会按主题关键词推断，并把对应规则写入 Prompt。', 'Choose a common game-map texture type. Auto detect infers from keywords and injects matching prompt rules.')}>
              <Select value={textureKind} onValueChange={(value) => setTextureKind(value as TextureKind)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TEXTURE_KIND_OPTIONS.map((item) => <SelectItem key={item.value} value={item.value}>{text(item.zh, item.en)}</SelectItem>)}
                </SelectContent>
              </Select>
            </PixField>
          )}
          <PixField label={assetNameLabel}><Input value={assetName} placeholder={assetNamePlaceholder} onChange={(e) => setAssetName(e.target.value)} /></PixField>
          <PixField label={text('额外风格描述（可选）', 'Extra style notes (optional)')}><Textarea value={assetExtraPrompt} rows={3} maxLength={PROMPT_MAX_LENGTH} placeholder={assetExtraPlaceholder} onChange={(e) => setAssetExtraPrompt(e.target.value)} /></PixField>
          {assetSupportsReference && (
            <PixField label={text('参考图（可选）', 'Reference image (optional)')} hint={assetReferenceHint}>
              <div className="grid gap-3">
                <Button type="button" variant="outline" asChild>
                  <label className="cursor-pointer">
                    <Upload />{assetRefUploading ? text('上传参考图…', 'Uploading reference…') : assetRefPath ? text('替换参考图', 'Replace reference') : text('上传参考图', 'Upload reference')}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label={text('上传参考图', 'Upload reference')} onChange={(event) => void uploadAssetReferenceFile(event.currentTarget.files?.[0])} />
                  </label>
                </Button>
                {assetRefMessage && <Alert variant={assetRefMessage.includes('失败') || assetRefMessage.toLowerCase().includes('failed') ? 'destructive' : 'info'}>{assetRefMessage}</Alert>}
                {assetRefPath && (
                  <div className="grid gap-2">
                    <PixPreviewFrame url={assetRefUrl} loading={assetRefUploading} label={text('参考图预览', 'Reference preview')} />
                    <Button type="button" variant="ghost" size="sm" onClick={clearAssetReference}>{text('移除参考图', 'Remove reference')}</Button>
                  </div>
                )}
              </div>
            </PixField>
          )}
          {hasAssetReference && <Alert variant="info">{assetReferenceAttachedMessage}</Alert>}
        </div>}

        {isSprite && <PixField label={text('主体 / 角色描述', 'Subject / character brief')} hint={text('描述角色身份、服装、配色与风格；逐行动作下面单独写。', 'Describe identity, costume, palette and style. Per-row actions go below.')}><Textarea value={prompt} rows={4} maxLength={PROMPT_MAX_LENGTH} onChange={(e) => setPrompt(e.target.value)} /></PixField>}

        {isSprite && (
          <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
            <PixField label={text('参考角色立绘（可选）', 'Reference character art (optional)')} hint={text('提供后将使用图生图，让每个单元格保留同一角色设计。', 'Image-to-image keeps the same character design across all cells.')}>
              <div className="grid gap-3">
                <Button type="button" variant="outline" asChild>
                  <label className="cursor-pointer">
                    <Upload />{refUploading ? text('上传参考图…', 'Uploading reference…') : refImagePath ? text('替换参考图', 'Replace reference') : text('上传参考图', 'Upload reference')}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label={text('上传参考图', 'Upload reference')} onChange={(event) => void uploadReferenceFile(event.currentTarget.files?.[0])} />
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

        {isLocalPixelize && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? text('上传中…', 'Uploading…') : text('上传图片', 'Upload image')}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label={text('上传图片', 'Upload image')} onChange={(event) => void uploadFile(event.currentTarget.files?.[0])} /></label></Button>{uploadMessage && <Alert variant={uploadMessage.includes('失败') ? 'destructive' : 'info'}>{uploadMessage}</Alert>}<PixPreviewFrame url={uploadUrl} loading={uploading} label={uploading ? text('上传中…', 'Uploading…') : text('等待上传预览', 'Waiting for upload preview')} /></div>}

        <PixelControls pixelLabel={isSprite ? text('单帧尺寸', 'Frame size') : text('像素尺寸', 'Pixel size')} pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} sizeOptions={isLogoAsset ? LOGO_SIZE_OPTIONS : undefined} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={isTileAsset || (!isSprite && !removeBg)} sizeHidden={isLocalPixelize} />

        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={isTileAsset ? false : removeBg} disabled={isSprite || isTileAsset} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{text('透明背景', 'Transparent background')}</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={isSprite || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? text('素材直出默认视觉理解策略', 'Default vision policy for asset output') : text('跳过参考图理解', 'Skip reference understanding')}</label></div>

        {invalidSubAssetSize && <Alert variant="destructive">{text('素材最低支持 16×16。', 'Minimum asset size is 16×16.')}</Alert>}
        {invalidGrid && <Alert variant="destructive">{text('序列帧每行/每列最多 8。', 'Sprite sequence rows and cols are capped at 8.')}</Alert>}
        {missingRowPrompts && <Alert variant="destructive">{text('多行序列帧需要为每一行填写动作描述。', 'Multi-row sequences require an action description for each row.')}</Alert>}
        <Button type="submit" size="lg" disabled={loading || submitBlocked}>{loading ? text('提交中…', 'Submitting…') : isSprite ? text('生成序列帧', 'Generate sprite sequence') : isAsset ? (isTileAsset ? text('生成平铺纹理', 'Generate tile texture') : isLogoAsset && hasAssetReference ? text('参考图生成 Logo', 'Generate logo from reference') : isLogoAsset ? text('生成游戏 Logo', 'Generate game logo') : hasAssetReference ? text('参考图重绘', 'Redraw from reference') : text('生成游戏素材', 'Generate game asset')) : text('生成单张素材', 'Generate single asset')}</Button>
      </form>
    </PixPanel>
  )
}
