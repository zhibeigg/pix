import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { CharacterItem, GenerationJob, ImageModelInfo, ImageModelsResponse, JobCreateRequest, PricingDiscount, PricingRule, StyleProfile, TextureKind, VideoBridgeModel } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, parsePixelSize, type BgRemovalAlgorithmChoice, type EdgeStyleChoice } from '../pixelize'
import { assetKindDefaults, jobTypeDefaults, mergeReusedPixelize, normalizeWorkbenchJobType, parseAssetKind, resolveReusableAssetKind, reusablePixelControlsFromJob, reusableWorkbenchType, sizeRetryStateFromJob, type AssetKindChoice, type DualGridTransitionStyle, type WorkbenchJobType } from '../lib/jobReuse'
import { promptLimitsFromModels } from '../lib/promptLimits'
import { DEFAULT_VIDEO_BRIDGE_MODEL, VIDEO_BRIDGE_MODELS, deriveVideoBridgeDurationSeconds, normalizeVideoBridgeModel, rawVideoBridgeDurationSeconds, videoBridgePriceCredits } from '../lib/pricing'
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
import { PromptPreviewDialog } from './PromptPreviewDialog'
import { SizeRetryControls, DEFAULT_SIZE_RETRY, type SizeRetryState } from './SizeRetryControls'
import { StyleProfileControls, compactStyleProfile } from './StyleProfileControls'

type AssetPresetSeed = { revision: number; assetKind: AssetKindChoice; assetName?: string }
type Props = { pricing: PricingRule[]; discount?: PricingDiscount | null; loading: boolean; token: string; imageModels: ImageModelsResponse; characters: CharacterItem[]; reuseJobSeed?: { revision: number; job: GenerationJob } | null; assetPresetSeed?: AssetPresetSeed | null; onSubmit: (payload: JobCreateRequest) => Promise<void> }

type TextureKindOption = { value: TextureKind; zh: string; en: string }

const MAX_GRID_AXIS = 8
const LOGO_SIZE_OPTIONS = ['64x32', '96x48', '128x64', '192x96', '256x128']
const DUAL_GRID_SIZE_OPTIONS = ['16x16', '24x24', '32x32', '48x48', '64x64', '96x96']
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
type SpriteMode = 'mosaic' | 'video_bridge'
type SpriteReferenceSource = 'upload' | 'character'

// video_bridge 专用「动画预设」：用帧数（流畅度）× fps（速度）表达，自动映射 rows×cols 与合法视频档位。
type VideoAnimPresetKey = 'light_loop' | 'standard' | 'fluid' | 'silky' | 'showcase' | 'custom'
type VideoAnimPresetSpec = { key: Exclude<VideoAnimPresetKey, 'custom'>; zh: string; en: string; rows: number; cols: number; fps: number }
const VIDEO_ANIM_PRESETS: VideoAnimPresetSpec[] = [
  { key: 'light_loop', zh: '轻量循环', en: 'Light loop', rows: 1, cols: 8, fps: 8 },
  { key: 'standard', zh: '标准动作', en: 'Standard action', rows: 1, cols: 8, fps: 6 },
  { key: 'fluid', zh: '流畅动作', en: 'Fluid action', rows: 2, cols: 8, fps: 10 },
  { key: 'silky', zh: '丝滑动作', en: 'Silky action', rows: 2, cols: 8, fps: 8 },
  { key: 'showcase', zh: '长演出', en: 'Long showcase', rows: 3, cols: 8, fps: 8 },
]
const DEFAULT_VIDEO_ANIM_PRESET: VideoAnimPresetKey = 'silky'
const DEFAULT_VIDEO_ANIM_SPEC: VideoAnimPresetSpec = VIDEO_ANIM_PRESETS.find((item) => item.key === DEFAULT_VIDEO_ANIM_PRESET) ?? {
  key: 'silky', zh: '丝滑动作', en: 'Silky action', rows: 2, cols: 8, fps: 8,
}

function matchVideoAnimPreset(rows: number, cols: number, fps: number): VideoAnimPresetKey {
  const found = VIDEO_ANIM_PRESETS.find((preset) => preset.rows === rows && preset.cols === cols && preset.fps === fps)
  return found ? found.key : 'custom'
}

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
  return model.label || model.id
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

function assetKindLabel(value: AssetKindChoice, text: (zh: string, en: string) => string): string {
  if (value === 'ui_component') return text('UI 组件', 'UI component')
  if (value === 'tile_texture') return text('平铺纹理', 'Tileable texture')
  if (value === 'game_logo') return text('游戏 Logo', 'Game logo')
  if (value === 'dual_grid') return text('双瓦片', 'Dual-grid tileset')
  if (value === 'character') return text('角色', 'Character')
  return text('物品图标', 'Item icon')
}

function transitionStyleValue(value: unknown): DualGridTransitionStyle {
  return value === 'hard' || value === 'outline' ? value : 'rounded'
}

function transitionStyleLabel(value: DualGridTransitionStyle, text: (zh: string, en: string) => string): string {
  if (value === 'hard') return text('硬边过渡', 'Hard edge')
  if (value === 'outline') return text('描边过渡', 'Outline')
  return text('圆滑过渡', 'Rounded')
}

function textureKindValue(value: unknown): TextureKind | null {
  return TEXTURE_KIND_OPTIONS.some((item) => item.value === value) ? value as TextureKind : null
}

function edgeStyleValue(value: unknown): EdgeStyleChoice | null {
  return value === 'hard' || value === 'outline' || value === 'feather' ? value : null
}

function bgRemovalAlgorithmValue(value: unknown): BgRemovalAlgorithmChoice {
  return value === 'color_to_alpha' ? 'color_to_alpha' : 'pixel_bg'
}

function rowPromptValues(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => stringValue(item)) : []
}

function styleProfileValue(value: unknown): StyleProfile {
  const record = asRecord(value)
  if (!record) return {}
  return {
    project_name: stringValue(record.project_name),
    palette: stringValue(record.palette),
    line_style: stringValue(record.line_style),
    lighting: stringValue(record.lighting),
    view_rule: stringValue(record.view_rule),
    avoid_elements: stringValue(record.avoid_elements),
  }
}

export function SingleGeneratePanel({ pricing, discount, loading, token, imageModels, characters, reuseJobSeed, assetPresetSeed, onSubmit }: Props) {
  const { text } = useI18n()
  const [jobType, setJobType] = useState<WorkbenchJobType>('sprite_sheet')
  const [imageModel, setImageModel] = useState(imageModels.default)
  const promptLimits = useMemo(() => promptLimitsFromModels(imageModels), [imageModels])
  const availableImageModels = useMemo(() => modelItems(imageModels), [imageModels])
  const selectedModelInfo = useMemo(() => availableImageModels.find((item) => item.id === imageModel), [availableImageModels, imageModel])
  const selectedModelSupportsI2I = supportsImageToImage(selectedModelInfo)
  const lastAppliedReuseRevisionRef = useRef<number | null>(null)
  const lastAppliedAssetPresetRevisionRef = useRef<number | null>(null)
  // 复用时缓存原作品完整 pixelize，提交时与界面字段合并，避免丢失界面未暴露的高级参数。
  const reusedPixelizeRef = useRef<Record<string, unknown> | null>(null)
  const [reuseModelMissing, setReuseModelMissing] = useState(false)
  const [assetName, setAssetName] = useState(() => text('冰霜之心', 'Frost Heart'))
  const [assetKind, setAssetKind] = useState<AssetKindChoice>('item_icon')
  const [textureKind, setTextureKind] = useState<TextureKind>('auto')
  const [dualMaterialA, setDualMaterialA] = useState(() => text('草地', 'Grass'))
  const [dualMaterialB, setDualMaterialB] = useState(() => text('泥土', 'Dirt'))
  const [dualMaterialATextureKind, setDualMaterialATextureKind] = useState<TextureKind>('auto')
  const [dualMaterialBTextureKind, setDualMaterialBTextureKind] = useState<TextureKind>('auto')
  const [dualTransitionStyle, setDualTransitionStyle] = useState<DualGridTransitionStyle>('rounded')
  const [prompt, setPrompt] = useState(() => text('蓝色斗篷骑士，侧视角像素风，身份和配色稳定', 'Blue-cape knight, side-view pixel art, stable identity and palette'))
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [uploadFilePreview, setUploadFilePreview] = useState<File | null>(null)
  // 素材直出可选参考图
  const [assetRefPath, setAssetRefPath] = useState('')
  const [assetRefUrl, setAssetRefUrl] = useState('')
  const [assetRefFile, setAssetRefFile] = useState<File | null>(null)
  const [assetRefUploading, setAssetRefUploading] = useState(false)
  const [assetRefMessage, setAssetRefMessage] = useState('')
  const [pixelSize, setPixelSize] = useState('64x64')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(false)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('hard')
  const [bgRemovalAlgorithm, setBgRemovalAlgorithm] = useState<BgRemovalAlgorithmChoice>('pixel_bg')
  const [skipVl, setSkipVl] = useState(false)
  const [sizeRetry, setSizeRetry] = useState<SizeRetryState>(DEFAULT_SIZE_RETRY)
  const [styleProfile, setStyleProfile] = useState<StyleProfile>({})
  // 序列帧专用状态（mosaic / 首尾帧视频补间）
  const [spriteMode, setSpriteMode] = useState<SpriteMode>('video_bridge')
  const [spritePreset, setSpritePreset] = useState<SpritePreset>('horizontal')
  const [videoAnimPreset, setVideoAnimPreset] = useState<VideoAnimPresetKey>(DEFAULT_VIDEO_ANIM_PRESET)
  const [videoModel, setVideoModel] = useState<VideoBridgeModel>(DEFAULT_VIDEO_BRIDGE_MODEL)
  const [rows, setRows] = useState(DEFAULT_VIDEO_ANIM_SPEC.rows)
  const [cols, setCols] = useState(DEFAULT_VIDEO_ANIM_SPEC.cols)
  const [rowPrompts, setRowPrompts] = useState<string[]>([''])
  const [videoActionPrompt, setVideoActionPrompt] = useState('')
  const [videoReturnToFirstFrame, setVideoReturnToFirstFrame] = useState(false)
  const [fps, setFps] = useState(DEFAULT_VIDEO_ANIM_SPEC.fps)
  const [refSource, setRefSource] = useState<SpriteReferenceSource>('upload')
  const [selectedRefCharacterId, setSelectedRefCharacterId] = useState<number | null>(null)
  const [refImagePath, setRefImagePath] = useState('')
  const [refImageUrl, setRefImageUrl] = useState('')
  const [refImageFile, setRefImageFile] = useState<File | null>(null)
  const [refUploading, setRefUploading] = useState(false)
  const [refUploadMessage, setRefUploadMessage] = useState('')

  const activeJobType = normalizeWorkbenchJobType(jobType)
  const isAsset = activeJobType === 'asset'
  const isSprite = activeJobType === 'sprite_sheet'
  const isSpriteVideoBridge = isSprite && spriteMode === 'video_bridge'
  const selectedRefCharacter = useMemo(() => characters.find((item) => item.id === selectedRefCharacterId) ?? null, [characters, selectedRefCharacterId])
  const isLocalPixelize = activeJobType === 'local_pixelize'
  const isLocalBgRemove = activeJobType === 'local_bg_remove'
  const showsImageModel = !isLocalPixelize && !isLocalBgRemove
  const isTileAsset = isAsset && assetKind === 'tile_texture'
  const isLogoAsset = isAsset && assetKind === 'game_logo'
  const isDualGridAsset = isAsset && assetKind === 'dual_grid'
  const isCharacterAsset = isAsset && assetKind === 'character'
  const dualMaterialBTransparent = dualMaterialB.trim() === '' || dualMaterialB.trim().toLocaleLowerCase() === 'transparent'
  // 平铺纹理 / 双瓦片不走参考图模式；普通素材参考图仍保留 asset job_type，以便继续使用素材直出 prompt。
  const assetSupportsReference = isAsset && (assetKind === 'item_icon' || assetKind === 'ui_component' || assetKind === 'game_logo' || assetKind === 'character')
  const hasAssetReference = assetSupportsReference && !!assetRefPath
  const basePrice = useMemo(() => {
    // 素材直出 + 参考图 时，按图生图价位计费；Logo 会保留 asset job_type，但后端同样按 image_to_image 取价。
    const billingKey = hasAssetReference ? 'image_to_image' : activeJobType
    return pricing.find((item) => item.key === billingKey)?.price_credits ?? 0
  }, [pricing, activeJobType, hasAssetReference])
  const safeRows = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(rows || 1)))
  const safeCols = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(cols || 1)))
  const totalFrames = safeRows * safeCols
  const playbackFps = Math.max(1, Math.min(60, Math.round(fps || 8)))
  const playbackSeconds = (totalFrames * Math.max(1, Math.round(1000 / playbackFps))) / 1000
  const billingUnits = Math.max(1, Math.ceil(totalFrames / 9))
  const videoBridgeRawDurationSeconds = rawVideoBridgeDurationSeconds(totalFrames, playbackFps)
  const videoBridgeDurationSeconds = deriveVideoBridgeDurationSeconds(totalFrames, playbackFps)
  const videoBridgePrice = videoBridgePriceCredits(videoModel, pricing, videoBridgeDurationSeconds)
  const videoBridgeUsesMinimumDuration = videoBridgeDurationSeconds > videoBridgeRawDurationSeconds
  const price = isSpriteVideoBridge ? videoBridgePrice : isSprite ? basePrice * billingUnits : basePrice
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const subjectKind = assetKind === 'ui_component' ? 'single_ui' : (assetKind === 'tile_texture' || assetKind === 'dual_grid') ? 'tileable_pattern' : assetKind === 'game_logo' ? 'logo_mark' : assetKind === 'character' ? 'single_character' : 'single_prop'
  const uiComponentImageSize = assetKind === 'ui_component' ? UI_COMPONENT_IMAGE_SIZE : undefined
  const assetSubjectMaxLength = promptLimits.asset_subject_max_chars
  const spriteSubjectMaxLength = promptLimits.sprite_subject_max_chars
  const spriteRowPromptMaxLength = promptLimits.sprite_row_prompt_max_chars
  const assetNameTooLong = isAsset && assetName.trim().length > assetSubjectMaxLength
  const dualMaterialATooLong = isDualGridAsset && dualMaterialA.trim().length > assetSubjectMaxLength
  const dualMaterialBTooLong = isDualGridAsset && dualMaterialB.trim().length > assetSubjectMaxLength
  const spriteSubjectTooLong = prompt.length > spriteSubjectMaxLength
  const rowPromptTooLong = isSprite && (ensureRowPromptsLength(rowPrompts, safeRows).some((value) => value.length > spriteRowPromptMaxLength) || videoActionPrompt.length > spriteRowPromptMaxLength)
  const assetNameLabel = isLogoAsset ? text('Logo 标题 / 品牌名', 'Logo title / brand name') : isDualGridAsset ? text('图集名称（可选）', 'Atlas name (optional)') : isTileAsset ? text('纹理主题 / 题材', 'Texture theme') : isCharacterAsset ? text('角色描述', 'Character brief') : text('主体', 'Subject')
  const assetNamePlaceholder = isLogoAsset
    ? text('例如：星尘纪元、PIX FORGE、龙焰', 'e.g. Starfall Age, PIX FORGE, Dragonflame')
    : isDualGridAsset
      ? text('例如：草地泥土过渡；留空会按 A/B 材质自动命名', 'e.g. Grass dirt transition; leave blank to name from A/B materials')
      : isTileAsset
        ? text('例如：苔藓砖石路面、木板地、像素草地', 'e.g. mossy cobblestone, wood planks, grass field')
        : isCharacterAsset
          ? text('例如：蓝袍骑士、红发法师、像素风商人 NPC', 'e.g. Blue-cloak knight, red-haired mage, pixel merchant NPC')
          : text('例如：冰霜之心', 'e.g. Frost Heart')
  const invalidGrid = isSprite && (safeRows < 1 || safeCols < 1 || safeRows > MAX_GRID_AXIS || safeCols > MAX_GRID_AXIS)
  const missingRowPrompts = isSprite && spriteMode === 'mosaic' && safeRows >= 2 && rowPrompts.slice(0, safeRows).some((value) => !value.trim())
  const submitBlocked = invalidSubAssetSize
    || invalidGrid
    || missingRowPrompts
    || assetNameTooLong
    || (isDualGridAsset && (dualMaterialATooLong || dualMaterialBTooLong))
    || (isSprite && (spriteSubjectTooLong || rowPromptTooLong))
    || (isAsset && !isDualGridAsset && !assetName.trim())
    || (isDualGridAsset && !dualMaterialA.trim())
    || (isSprite && !prompt.trim())
    || ((hasAssetReference || (isSprite && !!refImagePath)) && !selectedModelSupportsI2I)
    || ((isLocalPixelize || isLocalBgRemove) && !inputImagePath.trim())

  useEffect(() => {
    if (!availableImageModels.some((item) => item.id === imageModel)) {
      setImageModel(imageModels.default || availableImageModels[0]?.id || 'image2')
    }
  }, [availableImageModels, imageModel, imageModels.default])

  // 默认值在「用户手动切换模式/素材类型」时应用（取代原先依赖 effect 时序 + skip-ref 的脆弱机制，
  // 该机制在 React StrictMode 下会被双调用提前消费 skip-ref，导致复用回填的参数被默认值覆盖）。
  function applyAssetKindDefaults(kind: AssetKindChoice) {
    const d = assetKindDefaults(kind)
    setPixelSize(d.pixelSize); setColors(d.colors); setRemoveBg(d.removeBg); setEdgeStyle(d.edgeStyle)
    if (d.textureKind !== undefined) setTextureKind(d.textureKind)
    if (d.dualMaterialATextureKind !== undefined) setDualMaterialATextureKind(d.dualMaterialATextureKind)
    if (d.dualMaterialBTextureKind !== undefined) setDualMaterialBTextureKind(d.dualMaterialBTextureKind)
    if (d.dualTransitionStyle !== undefined) setDualTransitionStyle(d.dualTransitionStyle)
    if (d.clearAssetRef) { setAssetRefPath(''); setAssetRefUrl(''); setAssetRefMessage('') }
  }

  function selectAssetKind(kind: AssetKindChoice) {
    reusedPixelizeRef.current = null
    setReuseModelMissing(false)
    setSizeRetry(DEFAULT_SIZE_RETRY)
    setAssetKind(kind)
    applyAssetKindDefaults(kind)
  }

  function selectJobType(value: WorkbenchJobType) {
    const next = normalizeWorkbenchJobType(value)
    reusedPixelizeRef.current = null
    setReuseModelMissing(false)
    setSizeRetry(DEFAULT_SIZE_RETRY)
    setJobType(next)
    if (next === 'asset') { applyAssetKindDefaults(assetKind); return }
    const d = jobTypeDefaults(next)
    setPixelSize(d.pixelSize); setColors(d.colors); setRemoveBg(d.removeBg)
    if (d.edgeStyle !== undefined) setEdgeStyle(d.edgeStyle)
    if (d.bgRemovalAlgorithm !== undefined) setBgRemovalAlgorithm(d.bgRemovalAlgorithm)
    if (next === 'sprite_sheet') {
      setSpriteMode('video_bridge')
      setVideoActionPrompt('')
      setVideoReturnToFirstFrame(false)
      setVideoModel(DEFAULT_VIDEO_BRIDGE_MODEL)
      applyVideoAnimPreset(DEFAULT_VIDEO_ANIM_PRESET)
      if (d.spritePreset !== undefined) setSpritePreset(d.spritePreset)
      if (d.rowPrompts !== undefined) setRowPrompts(ensureRowPromptsLength(d.rowPrompts, 1))
    }
  }

  useEffect(() => {
    if (!assetPresetSeed || lastAppliedAssetPresetRevisionRef.current === assetPresetSeed.revision) return
    lastAppliedAssetPresetRevisionRef.current = assetPresetSeed.revision
    reusedPixelizeRef.current = null
    setReuseModelMissing(false)
    setSizeRetry(DEFAULT_SIZE_RETRY)
    setJobType('asset')
    setAssetKind(assetPresetSeed.assetKind)
    applyAssetKindDefaults(assetPresetSeed.assetKind)
    if (assetPresetSeed.assetName !== undefined) setAssetName(assetPresetSeed.assetName)
    setAssetRefPath(''); setAssetRefFile(null); setAssetRefUrl(''); setAssetRefMessage('')
    setInputImagePath(''); setUploadFilePreview(null); setUploadUrl(''); setUploadMessage('')
    setRefSource('upload'); setSelectedRefCharacterId(null); setRefImagePath(''); setRefImageFile(null); setRefImageUrl(''); setRefUploadMessage('')
  }, [assetPresetSeed])

  useEffect(() => {
    if (!reuseJobSeed || lastAppliedReuseRevisionRef.current === reuseJobSeed.revision) return
    lastAppliedReuseRevisionRef.current = reuseJobSeed.revision
    const job = reuseJobSeed.job
    const params = asRecord(job.params_json)
    const pixelize = asRecord(params?.pixelize)
    const sprite = asRecord(params?.sprite)
    const asset = asRecord(params?.asset)
    const nextJobType = reusableWorkbenchType(job)
    const nextAssetKind = resolveReusableAssetKind(asset) ?? 'item_icon'
    const nextTextureKind = textureKindValue(asset?.texture_kind) ?? 'auto'
    const nextDualMaterialATextureKind = textureKindValue(asset?.material_a_texture_kind) ?? 'auto'
    const nextDualMaterialBTextureKind = textureKindValue(asset?.material_b_texture_kind) ?? 'auto'

    // 直接回填，不再依赖 reset 副作用 / skip-ref；缓存原 pixelize 供提交时合并界面未暴露的高级参数。
    reusedPixelizeRef.current = pixelize
    setJobType(nextJobType)

    const model = stringValue(params?.image_model)
    if (model && availableImageModels.some((item) => item.id === model)) { setImageModel(model); setReuseModelMissing(false) }
    else if (model) setReuseModelMissing(true)
    else { setImageModel(imageModels.default || availableImageModels[0]?.id || 'image2'); setReuseModelMissing(false) }

    const defaultControls = nextJobType === 'asset' ? assetKindDefaults(nextAssetKind) : jobTypeDefaults(nextJobType)
    const reusedControls = reusablePixelControlsFromJob(job, defaultControls)
    setPixelSize(reusedControls.pixelSize)
    setColors(reusedControls.colors)
    const reusedRemoveBg = booleanValue(pixelize?.remove_bg)
    if (reusedRemoveBg !== null) setRemoveBg(reusedRemoveBg)
    const reusedEdgeStyle = edgeStyleValue(pixelize?.edge_style)
    if (reusedEdgeStyle) setEdgeStyle(reusedEdgeStyle)
    setBgRemovalAlgorithm(bgRemovalAlgorithmValue(pixelize?.bg_removal_algorithm))
    setSkipVl(Boolean(params?.skip_vl))
    setSizeRetry(sizeRetryStateFromJob(job) as SizeRetryState)
    setStyleProfile(styleProfileValue(params?.style_profile))

    if (nextJobType === 'sprite_sheet') {
      const nextRows = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(numberValue(sprite?.rows) ?? 1)))
      const nextCols = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(numberValue(sprite?.cols) ?? 8)))
      const nextFps = Math.max(1, Math.min(60, Math.round(numberValue(sprite?.fps) ?? 8)))
      const nextRowPrompts = ensureRowPromptsLength(rowPromptValues(sprite?.row_prompts), nextRows)
      setPrompt(job.prompt?.trim() || '')
      const nextSpriteMode = stringValue(sprite?.mode) === 'video_bridge' ? 'video_bridge' : 'mosaic'
      setSpriteMode(nextSpriteMode)
      setRows(nextRows)
      setCols(nextCols)
      setFps(nextFps)
      setRowPrompts(nextRowPrompts)
      setVideoActionPrompt(stringValue(sprite?.video_action_prompt))
      setVideoReturnToFirstFrame(Boolean(sprite?.video_return_to_first_frame))
      setVideoModel(normalizeVideoBridgeModel(sprite?.video_model))
      setSpritePreset('custom')
      // video_bridge：若 rows/cols/fps 命中某动画预设则选中它，否则标记自定义。
      setVideoAnimPreset(nextSpriteMode === 'video_bridge' ? matchVideoAnimPreset(nextRows, nextCols, nextFps) : DEFAULT_VIDEO_ANIM_PRESET)
      const referencePath = stringValue(sprite?.reference_image_path)
      setRefSource('upload')
      setSelectedRefCharacterId(null)
      setRefImagePath(referencePath)
      setRefImageFile(null)
      setRefImageUrl(signedFileUrl(job.sprite_reference_image_url ?? undefined, undefined, true))
      setRefUploadMessage('')
      setAssetRefPath(''); setAssetRefFile(null); setAssetRefUrl(''); setAssetRefMessage('')
      setInputImagePath(''); setUploadFilePreview(null); setUploadUrl(''); setUploadMessage('')
      setRemoveBg(false)
      return
    }

    if (nextJobType === 'local_pixelize' || nextJobType === 'local_bg_remove') {
      setInputImagePath(job.input_image_path ?? '')
      setUploadFilePreview(null)
      setUploadUrl(signedFileUrl(job.input_image_url ?? undefined, token, true))
      setUploadMessage(job.input_image_path ? text('已复用原任务的输入图片。', 'Reused the original input image.') : '')
      setAssetRefPath(''); setAssetRefFile(null); setAssetRefUrl(''); setAssetRefMessage('')
      setRefSource('upload'); setSelectedRefCharacterId(null); setRefImagePath(''); setRefImageFile(null); setRefImageUrl(''); setRefUploadMessage('')
      return
    }

    setAssetKind(nextAssetKind)
    setTextureKind(nextAssetKind === 'tile_texture' ? nextTextureKind : 'auto')
    setDualMaterialA(stringValue(asset?.material_a))
    setDualMaterialB(stringValue(asset?.material_b))
    setDualMaterialATextureKind(nextDualMaterialATextureKind)
    setDualMaterialBTextureKind(nextDualMaterialBTextureKind)
    setDualTransitionStyle(transitionStyleValue(asset?.transition_style))
    const assetSubject = stringValue(asset?.name) || job.prompt?.trim() || ''
    setAssetName(assetSubject)
    setPrompt(job.prompt?.trim() || assetSubject)
    const referencePath = job.input_image_path ?? ''
    setAssetRefPath(referencePath)
    setAssetRefFile(null)
    setAssetRefUrl(signedFileUrl(job.input_image_url ?? undefined, token, true))
    setAssetRefMessage('')
    setRefImagePath(''); setRefImageFile(null); setRefImageUrl(''); setRefUploadMessage('')
    setInputImagePath(''); setUploadFilePreview(null); setUploadUrl(''); setUploadMessage('')
  }, [availableImageModels, imageModels.default, reuseJobSeed, text, token])

  function selectSpriteMode(next: SpriteMode) {
    setSpriteMode(next)
    if (next === 'video_bridge') {
      const firstAction = videoActionPrompt.trim() || rowPrompts.find((value) => value.trim())?.trim() || ''
      setVideoActionPrompt(firstAction)
      setVideoModel(DEFAULT_VIDEO_BRIDGE_MODEL)
      // 切到视频补间：应用默认动画预设（丝滑动作 16帧@8fps），并把 rowPrompts 收敛到 1 条（视频补间只用单条动作描述）。
      applyVideoAnimPreset(DEFAULT_VIDEO_ANIM_PRESET)
      setRowPrompts((prev) => ensureRowPromptsLength(prev, 1))
    }
  }

  // 应用 video_bridge 动画预设（帧数×fps 组合）
  function applyVideoAnimPreset(preset: VideoAnimPresetKey) {
    setVideoAnimPreset(preset)
    if (preset === 'custom') return
    const spec = VIDEO_ANIM_PRESETS.find((item) => item.key === preset)
    if (!spec) return
    setRows(spec.rows)
    setCols(spec.cols)
    setFps(spec.fps)
    setRowPrompts((prev) => ensureRowPromptsLength(prev, 1))
  }

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
    setVideoAnimPreset('custom')
  }

  function updateCols(value: number) {
    const next = Math.max(1, Math.min(MAX_GRID_AXIS, Math.round(value || 1)))
    setCols(next)
    setSpritePreset('custom')
    setVideoAnimPreset('custom')
  }

  function updateFps(value: number) {
    const next = Math.max(1, Math.min(60, Math.round(value || 1)))
    setFps(next)
    if (isSpriteVideoBridge) setVideoAnimPreset('custom')
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
    setInputImagePath('')
    setUploadUrl('')
    setUploadFilePreview(file)
    setUploading(true); setUploadMessage(text('上传中…', 'Uploading…'))
    try {
      const uploaded = await api.uploadImage(token, file)
      setInputImagePath(uploaded.path); setUploadMessage(text('图片已上传，可继续提交任务。', 'Image uploaded. You can submit the job now.'))
    } catch (error) {
      setUploadFilePreview(null)
      setUploadMessage(error instanceof Error ? error.message : text('上传失败', 'Upload failed'))
    } finally { setUploading(false) }
  }

  async function uploadReferenceFile(file: File | undefined) {
    if (!file) return
    setRefSource('upload')
    setSelectedRefCharacterId(null)
    setRefImagePath('')
    setRefImageUrl('')
    setRefImageFile(file)
    setRefUploading(true); setRefUploadMessage('')
    try {
      const uploaded = await api.uploadImage(token, file)
      setRefImagePath(uploaded.path); setRefUploadMessage('')
    } catch (error) {
      setRefImageFile(null)
      setRefUploadMessage(error instanceof Error ? error.message : text('参考图上传失败', 'Reference upload failed'))
    } finally { setRefUploading(false) }
  }

  function selectReferenceSource(next: SpriteReferenceSource) {
    setRefSource(next)
    if (next === 'upload') {
      setSelectedRefCharacterId(null)
      setRefImagePath('')
      setRefImageUrl('')
      setRefImageFile(null)
      setRefUploadMessage('')
      return
    }
    if (selectedRefCharacter) {
      selectCharacterReference(selectedRefCharacter.id)
      return
    }
    const first = characters[0]
    if (first) selectCharacterReference(first.id)
  }

  function selectCharacterReference(rawId: number | string) {
    const id = Number(rawId)
    const item = characters.find((candidate) => candidate.id === id)
    if (!item) {
      clearReference()
      setRefSource('character')
      return
    }
    setRefSource('character')
    setSelectedRefCharacterId(item.id)
    setRefImagePath(item.image_path)
    setRefImageUrl(signedFileUrl(item.preview_url || item.image_url || undefined))
    setRefImageFile(null)
    setRefUploadMessage('')
  }

  function clearReference() {
    setRefImagePath(''); setRefImageUrl(''); setRefImageFile(null); setSelectedRefCharacterId(null); setRefUploadMessage('')
  }

  async function uploadAssetReferenceFile(file: File | undefined) {
    if (!file) return
    setAssetRefPath('')
    setAssetRefUrl('')
    setAssetRefFile(file)
    setAssetRefUploading(true); setAssetRefMessage('')
    try {
      const uploaded = await api.uploadImage(token, file)
      setAssetRefPath(uploaded.path); setAssetRefMessage('')
    } catch (error) {
      setAssetRefFile(null)
      setAssetRefMessage(error instanceof Error ? error.message : text('参考图上传失败', 'Reference upload failed'))
    } finally { setAssetRefUploading(false) }
  }

  function clearAssetReference() {
    setAssetRefPath(''); setAssetRefUrl(''); setAssetRefFile(null); setAssetRefMessage('')
  }

  function buildCurrentPayload(clientRequestId: string = crypto.randomUUID()): JobCreateRequest | null {
    if (submitBlocked) return null
    const edge = edgeStylePixelize(edgeStyle)
    const modelOverride = imageModel !== imageModels.default ? imageModel : undefined
    const styleProfilePayload = compactStyleProfile(styleProfile)
    const styleProfileFields = styleProfilePayload ? { style_profile: styleProfilePayload } : {}

    if (isAsset) {
      const sizeRetryFields = sizeRetry.enabled
        ? {
            size_retry_enabled: true,
            size_retry_mode: sizeRetry.mode,
            size_retry_max_attempts: sizeRetry.maxAttempts,
            size_retry_max_credits: sizeRetry.maxCredits,
          }
        : {}
      const materialA = dualMaterialA.trim()
      const materialB = dualMaterialB.trim()
      const generatedDualName = dualMaterialBTransparent
        ? text(`${materialA}透明过渡`, `${materialA} transparent transition`)
        : text(`${materialA}${materialB}过渡`, `${materialA} ${materialB} transition`)
      const subject = isDualGridAsset ? (assetName.trim() || generatedDualName) : assetName.trim()
      const assetPixelize = buildAssetPixelize(mergeReusedPixelize(reusedPixelizeRef.current, { output_size: parsedPixelSize, colors, remove_bg: isDualGridAsset ? false : removeBg, ...edge }))
      if (hasAssetReference) {
        return {
          job_type: 'asset',
          prompt: subject,
          input_image_path: assetRefPath,
          client_request_id: clientRequestId,
          image_size: uiComponentImageSize,
          image_model: modelOverride,
          skip_vl: skipVl,
          ...sizeRetryFields,
          ...styleProfileFields,
          pixelize: assetPixelize,
          grid: buildGridDesign(),
          asset: { name: subject, asset_kind: assetKind, subject_kind: subjectKind, texture_kind: isTileAsset ? textureKind : undefined, no_preview: false },
        }
      }
      return {
        job_type: 'asset',
        prompt: subject,
        input_image_path: null,
        client_request_id: clientRequestId,
        image_size: uiComponentImageSize,
        image_model: modelOverride,
        ...sizeRetryFields,
        ...styleProfileFields,
        pixelize: assetPixelize,
        grid: buildGridDesign(),
        asset: isDualGridAsset
          ? { name: subject, asset_kind: 'dual_grid', subject_kind: 'tileable_pattern', material_a: materialA, material_b: materialB, material_a_texture_kind: dualMaterialATextureKind, material_b_texture_kind: dualMaterialBTextureKind, transition_style: dualTransitionStyle, no_preview: false }
          : { name: subject, asset_kind: assetKind, subject_kind: subjectKind, texture_kind: isTileAsset ? textureKind : undefined, no_preview: false },
      }
    }

    if (isSprite) {
      const safeFps = Math.max(1, Math.min(60, Math.round(fps || 8)))
      const cleanRowPrompts = ensureRowPromptsLength(rowPrompts, safeRows).map((value) => value.trim())
      return {
        job_type: 'sprite_sheet',
        prompt: prompt.trim(),
        input_image_path: null,
        client_request_id: clientRequestId,
        image_model: modelOverride,
        skip_vl: false,
        ...styleProfileFields,
        pixelize: buildPixelize(mergeReusedPixelize(reusedPixelizeRef.current, { output_size: parsedPixelSize, colors, remove_bg: false, ...edge })),
        grid: buildGridDesign(),
        sprite: {
          mode: spriteMode,
          rows: safeRows,
          cols: safeCols,
          row_prompts: spriteMode === 'video_bridge' ? cleanRowPrompts.slice(0, 1) : cleanRowPrompts,
          reference_image_path: refImagePath || null,
          frame_count: totalFrames,
          fps: safeFps,
          gif_export: false,
          duration_ms: Math.max(20, Math.round(1000 / safeFps)),
          loop: 0,
          video_action_prompt: spriteMode === 'video_bridge' ? videoActionPrompt.trim() : '',
          video_return_to_first_frame: spriteMode === 'video_bridge' ? videoReturnToFirstFrame : false,
          video_model: spriteMode === 'video_bridge' ? videoModel : undefined,
        },
      }
    }

    if (isLocalBgRemove) {
      return {
        job_type: 'local_bg_remove',
        prompt: null,
        input_image_path: inputImagePath,
        client_request_id: clientRequestId,
        skip_vl: true,
        pixelize: buildPixelize(mergeReusedPixelize(reusedPixelizeRef.current, { output_size: parsedPixelSize, colors, remove_bg: true, bg_removal_algorithm: bgRemovalAlgorithm, ...edge })),
        grid: { mode: 'off' },
      }
    }

    return {
      job_type: activeJobType,
      prompt: null,
      input_image_path: inputImagePath,
      client_request_id: clientRequestId,
      skip_vl: skipVl,
      pixelize: buildPixelize(mergeReusedPixelize(reusedPixelizeRef.current, { output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge })),
      grid: buildGridDesign(),
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const payload = buildCurrentPayload()
    if (!payload) return
    await onSubmit(payload)
  }

  return (
      <PixPanel eyebrow={text('单张试做', 'Single test')} title={text('任务配方', 'Job recipe')} action={<EstimateBadge price={price} discount={discount} sprite={isSprite && !isSpriteVideoBridge ? { billingUnits, basePrice, totalFrames } : null} videoBridge={isSpriteVideoBridge ? { durationSeconds: videoBridgeDurationSeconds, totalFrames, fps: playbackFps } : null} />}>
      <form className="grid gap-5" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <PixField label={text('模式', 'Mode')}>
            <Select value={activeJobType} onValueChange={(value) => selectJobType(value as WorkbenchJobType)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="asset">{text('游戏素材直出', 'Game asset output')}</SelectItem>
                <SelectItem value="sprite_sheet">{text('序列帧', 'Sprite sequence')}</SelectItem>
                <SelectItem value="local_pixelize">{text('本地像素化', 'Local pixelize')}</SelectItem>
                <SelectItem value="local_bg_remove">{text('本地去背景', 'Local background removal')}</SelectItem>
              </SelectContent>
            </Select>
          </PixField>
          {showsImageModel && (
            <PixField label={text('生图模型', 'Image model')}>
              <Select value={imageModel} onValueChange={(value) => { setImageModel(value); setReuseModelMissing(false) }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {availableImageModels.map((m) => (
                    <SelectItem key={m.id} value={m.id}>{modelOptionLabel(m)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </PixField>
          )}
        </div>
        {!selectedModelSupportsI2I && (hasAssetReference || (isSprite && refImagePath)) && <Alert variant="warning">{text('当前模型不支持参考图 / 图生图，请切换支持 image-to-image 的模型或移除参考图。', 'The selected model does not support reference images / image-to-image. Switch to a model with image-to-image support or remove the reference.')}</Alert>}
        {showsImageModel && reuseModelMissing && <Alert variant="warning">{text('复用作品使用的生图模型当前不可用，已改用默认模型，可手动重新选择。', 'The image model used by the reused job is no longer available; the default model is used instead — pick one manually if needed.')}</Alert>}

        {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
          <PixField label={text('素材类型', 'Asset type')}>
            <Select value={assetKind} onValueChange={(value) => selectAssetKind(parseAssetKind(value) ?? 'item_icon')}>
              <SelectTrigger><SelectValue>{assetKindLabel(assetKind, text)}</SelectValue></SelectTrigger>
              <SelectContent>
                <SelectItem value="item_icon">{text('物品图标', 'Item icon')}</SelectItem>
                <SelectItem value="ui_component">{text('UI 组件', 'UI component')}</SelectItem>
                <SelectItem value="tile_texture">{text('平铺纹理', 'Tileable texture')}</SelectItem>
                <SelectItem value="game_logo">{text('游戏 Logo', 'Game logo')}</SelectItem>
                <SelectItem value="dual_grid">{text('双瓦片', 'Dual-grid tileset')}</SelectItem>
                <SelectItem value="character">{text('角色', 'Character')}</SelectItem>
              </SelectContent>
            </Select>
          </PixField>
          {isCharacterAsset && <Alert variant="info">{text('角色素材完成后会自动保存到角色库，之后可直接作为序列帧参考来源。', 'Character assets are saved to the character library automatically, ready to reuse as sprite references later.')}</Alert>}
          {isDualGridAsset && <Alert variant="info">{text('一次生成 4×4 / 16 张过渡瓦片图集：先生成材质 A、B，再按 dual-grid 角掩码合成。B 留空或填 transparent 会生成透明边缘。', 'Generates a 4×4 / 16-tile transition atlas: material A and B are generated first, then composed with dual-grid corner masks. Leave B empty or use transparent for transparent edges.')}</Alert>}
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
          {isDualGridAsset && (
            <div className="grid gap-4 rounded-lg border border-border bg-background/45 p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
              <div className="grid gap-3 sm:grid-cols-2">
                <PixField label={text('材质 A（主体地形）', 'Material A (primary terrain)')} hint={text('必填，例如草地、雪地、石砖。', 'Required, e.g. grass, snow, stone brick.')}>
                  <Input value={dualMaterialA} maxLength={assetSubjectMaxLength} placeholder={text('例如：草地', 'e.g. Grass')} onChange={(event) => setDualMaterialA(event.target.value)} />
                </PixField>
                <PixField label={text('A 纹理类型', 'A texture type')}>
                  <Select value={dualMaterialATextureKind} onValueChange={(value) => setDualMaterialATextureKind(value as TextureKind)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{TEXTURE_KIND_OPTIONS.map((item) => <SelectItem key={`a-${item.value}`} value={item.value}>{text(item.zh, item.en)}</SelectItem>)}</SelectContent>
                  </Select>
                </PixField>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <PixField label={text('材质 B / 透明', 'Material B / transparent')} hint={text('填泥土、水面等；留空或填 transparent 表示透明边缘。', 'Use dirt, water, etc.; leave empty or enter transparent for transparent edges.')}>
                  <Input value={dualMaterialB} maxLength={assetSubjectMaxLength} placeholder={text('例如：泥土；留空 = 透明', 'e.g. Dirt; empty = transparent')} onChange={(event) => setDualMaterialB(event.target.value)} />
                </PixField>
                <PixField label={text('B 纹理类型', 'B texture type')} hint={dualMaterialBTransparent ? text('透明模式会跳过材质 B 生成。', 'Transparent mode skips material B generation.') : undefined}>
                  <Select value={dualMaterialBTextureKind} onValueChange={(value) => setDualMaterialBTextureKind(value as TextureKind)} disabled={dualMaterialBTransparent}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{TEXTURE_KIND_OPTIONS.map((item) => <SelectItem key={`b-${item.value}`} value={item.value}>{text(item.zh, item.en)}</SelectItem>)}</SelectContent>
                  </Select>
                </PixField>
              </div>
              <PixField label={text('过渡风格', 'Transition style')} hint={text('圆滑适合自然地形；硬边适合机械/地砖；描边适合透明孤岛边缘。', 'Rounded fits natural terrain; hard fits mechanical/floor tiles; outline helps transparent island edges.')}>
                <Select value={dualTransitionStyle} onValueChange={(value) => setDualTransitionStyle(transitionStyleValue(value))}>
                  <SelectTrigger><SelectValue>{transitionStyleLabel(dualTransitionStyle, text)}</SelectValue></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="rounded">{text('圆滑过渡', 'Rounded')}</SelectItem>
                    <SelectItem value="hard">{text('硬边过渡', 'Hard edge')}</SelectItem>
                    <SelectItem value="outline">{text('描边过渡', 'Outline')}</SelectItem>
                  </SelectContent>
                </Select>
              </PixField>
            </div>
          )}
          <PixField label={assetNameLabel} hint={text(`最多 ${assetSubjectMaxLength} 字`, `Max ${assetSubjectMaxLength} characters`)}>
            {isLogoAsset ? (
              <Input value={assetName} maxLength={assetSubjectMaxLength} placeholder={assetNamePlaceholder} onChange={(e) => setAssetName(e.target.value)} />
            ) : (
              <Textarea value={assetName} rows={3} maxLength={assetSubjectMaxLength} placeholder={assetNamePlaceholder} onChange={(e) => setAssetName(e.target.value)} />
            )}
          </PixField>
          {assetSupportsReference && (
            <PixField label={text('参考图（可选）', 'Reference image (optional)')}>
              <div className="grid gap-3">
                <Button type="button" variant="outline" asChild>
                  <label className="cursor-pointer">
                    <Upload />{assetRefUploading ? text('上传参考图…', 'Uploading reference…') : assetRefPath ? text('替换参考图', 'Replace reference') : text('上传参考图', 'Upload reference')}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label={text('上传参考图', 'Upload reference')} onChange={(event) => void uploadAssetReferenceFile(event.currentTarget.files?.[0])} />
                  </label>
                </Button>
                {assetRefMessage && <Alert variant="destructive">{assetRefMessage}</Alert>}
                {(assetRefUrl || assetRefFile) && (
                  <div className="grid gap-2">
                    <PixPreviewFrame url={assetRefUrl} file={assetRefFile} label={text('参考图预览', 'Reference preview')} />
                    <Button type="button" variant="ghost" size="sm" onClick={clearAssetReference}>{text('移除参考图', 'Remove reference')}</Button>
                  </div>
                )}
              </div>
            </PixField>
          )}
        </div>}

        {isSprite && <PixField label={text('主体 / 角色描述', 'Subject / character brief')} hint={text(`描述角色身份、服装、配色与风格；逐行动作下面单独写。${prompt.length}/${spriteSubjectMaxLength} 字`, `Describe identity, costume, palette and style. Per-row actions go below. ${prompt.length}/${spriteSubjectMaxLength} characters`)}><Textarea value={prompt} rows={4} maxLength={spriteSubjectMaxLength} onChange={(e) => setPrompt(e.target.value)} /></PixField>}

        {isSprite && (
          <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
            <PixField label={text('生成方式', 'Generation mode')} hint={text('默认适合快速生成整张序列帧；连贯动作适合走路、攻击、施法等更顺滑的角色动作。', 'Default is best for quick sprite sheets; smooth action is best for walks, attacks, casts, and other more fluid character motions.') }>
              <Select value={spriteMode} onValueChange={(value) => selectSpriteMode(value as SpriteMode)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="video_bridge">{text('连贯动作序列帧（默认）', 'Smooth action sequence (default)')}</SelectItem>
                  <SelectItem value="mosaic">{text('快速序列帧', 'Quick sprite sheet')}</SelectItem>
                </SelectContent>
              </Select>
            </PixField>
            {isSpriteVideoBridge && <Alert variant="info">{text('想要更顺滑的角色动作时，选择下方动画预设即可。完成后会得到可预览、可下载、可导出的序列帧，适合走路、攻击、施法和待机循环。', 'For smoother character motion, choose an animation preset below. You’ll get previewable and downloadable sprite frames ready for walks, attacks, casts, and idle loops.')}</Alert>}
            <PixField label={text('参考来源（可选）', 'Reference source (optional)')} hint={text('可从角色库复用已保存角色，也可以继续直接上传临时参考图。', 'Reuse a saved character from the library, or keep uploading a one-off reference image.') }>
              <div className="grid gap-3">
                <Select value={refSource} onValueChange={(value) => selectReferenceSource(value as SpriteReferenceSource)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="character">{text('从角色库选择', 'Choose from character library')}</SelectItem>
                    <SelectItem value="upload">{text('直接上传参考图', 'Upload reference directly')}</SelectItem>
                  </SelectContent>
                </Select>

                {refSource === 'character' ? (
                  <div className="grid gap-3">
                    {characters.length > 0 ? (
                      <Select value={selectedRefCharacterId ? String(selectedRefCharacterId) : ''} onValueChange={selectCharacterReference}>
                        <SelectTrigger><SelectValue placeholder={text('选择角色', 'Choose a character')} /></SelectTrigger>
                        <SelectContent>
                          {characters.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    ) : <Alert variant="info">{text('角色库还是空的。可以先从作品库保存角色，或切换为直接上传。', 'Your character library is empty. Save a character from the gallery first, or switch to direct upload.')}</Alert>}
                    {selectedRefCharacter && <div className="text-xs text-muted-foreground">{text('已选择角色库资源：', 'Selected library character: ')}<span className="font-semibold text-foreground">{selectedRefCharacter.name}</span></div>}
                  </div>
                ) : (
                  <Button type="button" variant="outline" asChild>
                    <label className="cursor-pointer">
                      <Upload />{refUploading ? text('上传参考图…', 'Uploading reference…') : refImagePath ? text('替换参考图', 'Replace reference') : text('上传参考图', 'Upload reference')}
                      <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label={text('上传参考图', 'Upload reference')} onChange={(event) => void uploadReferenceFile(event.currentTarget.files?.[0])} />
                    </label>
                  </Button>
                )}

                {refUploadMessage && <Alert variant="destructive">{refUploadMessage}</Alert>}
                {(refImageUrl || refImageFile) && (
                  <div className="grid gap-2">
                    <PixPreviewFrame url={refImageUrl} file={refImageFile} label={text('参考角色预览', 'Reference preview')} />
                    <Button type="button" variant="ghost" size="sm" onClick={clearReference}>{text('移除参考图', 'Remove reference')}</Button>
                  </div>
                )}
              </div>
            </PixField>

            {isSpriteVideoBridge ? (
              <>
                <PixField label={text('视频模型', 'Video model')} hint={text('按 480p / 4–15 秒 / 输入不含视频价格表 ×20，再加 10 点关键帧生图价。', 'Credits use the 480p / 4–15s no-input-video price table ×20, plus 10 keyframe credits.')}>
                  <Select value={videoModel} onValueChange={(value) => setVideoModel(normalizeVideoBridgeModel(value))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {VIDEO_BRIDGE_MODELS.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                          {model.value} · {text(model.label, model.label)} · {videoBridgePriceCredits(model.value, pricing, videoBridgeDurationSeconds)} {text('点', 'credits')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </PixField>
                <PixField label={text('动画预设', 'Animation preset')} hint={text('按你想要的流畅度和速度选择：帧数越多越顺滑，FPS 越高播放越快。', 'Choose the smoothness and speed you want: more frames feel smoother, and higher FPS plays faster.')}>
                  <Select value={videoAnimPreset} onValueChange={(value) => applyVideoAnimPreset(value as VideoAnimPresetKey)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {VIDEO_ANIM_PRESETS.map((preset) => {
                        const frames = preset.rows * preset.cols
                        const playSeconds = (frames * Math.max(1, Math.round(1000 / preset.fps))) / 1000
                        const billedSeconds = deriveVideoBridgeDurationSeconds(frames, preset.fps)
                        const billedPrice = videoBridgePriceCredits(videoModel, pricing, billedSeconds)
                        return (
                          <SelectItem key={preset.key} value={preset.key}>
                            {text(preset.zh, preset.en)} · {frames} {text('帧', 'frames')} @ {preset.fps}fps · {text(`播放约 ${playSeconds.toFixed(1)} 秒`, `plays ~${playSeconds.toFixed(1)}s`)} · {text(`计费 ${billedSeconds}s / ${billedPrice} 点`, `billed ${billedSeconds}s / ${billedPrice} credits`)}
                          </SelectItem>
                        )
                      })}
                      <SelectItem value="custom">
                        {text(`自定义 · 当前 ${totalFrames} 帧 @ ${playbackFps}fps · 计费 ${videoBridgeDurationSeconds}s / ${videoBridgePrice} 点`, `Custom · current ${totalFrames} frames @ ${playbackFps}fps · billed ${videoBridgeDurationSeconds}s / ${videoBridgePrice} credits`)}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </PixField>
                {videoAnimPreset === 'custom' && (
                  <div className="grid gap-3 sm:grid-cols-4">
                    <PixField label={text('行 rows（1~8）', 'Rows (1–8)')}>
                      <Input type="number" min={1} max={MAX_GRID_AXIS} value={safeRows} onChange={(e) => updateRows(Number(e.target.value))} />
                    </PixField>
                    <PixField label={text('列 cols（1~8）', 'Cols (1–8)')}>
                      <Input type="number" min={1} max={MAX_GRID_AXIS} value={safeCols} onChange={(e) => updateCols(Number(e.target.value))} />
                    </PixField>
                    <PixField label={text('播放 FPS', 'Playback FPS')} hint={text('改动后会立即重新计算计费秒数和价格。', 'Changes recalculate billing duration and price immediately.')}>
                      <Input type="number" min={1} max={60} value={playbackFps} onChange={(e) => updateFps(Number(e.target.value))} />
                    </PixField>
                    <PixField label={text('总帧数', 'Total frames')}>
                      <Input value={`${totalFrames}`} readOnly />
                    </PixField>
                  </div>
                )}
                <Alert variant="info">
                  {text(
                    `预计成品：${totalFrames} 帧动画 · 播放约 ${playbackSeconds.toFixed(1)} 秒 · ${playbackFps}fps · 计费 ${videoBridgeDurationSeconds}s 视频补间 · 预计 ${videoBridgePrice} 点${videoBridgeUsesMinimumDuration ? `（当前播放时长约 ${videoBridgeRawDurationSeconds}s，不足 4s 按官方 4s 最低档计费）` : ''}`,
                    `Expected output: ${totalFrames}-frame animation · plays ~${playbackSeconds.toFixed(1)}s · ${playbackFps}fps · billed as a ${videoBridgeDurationSeconds}s video bridge · estimated ${videoBridgePrice} credits${videoBridgeUsesMinimumDuration ? ` (current playback rounds to ${videoBridgeRawDurationSeconds}s, below the official 4s minimum tier)` : ''}`,
                  )}
                </Alert>
              </>
            ) : (
              <>
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
              </>
            )}

            {isSpriteVideoBridge && (
              <div className="grid gap-3">
                <PixField label={text('视频动作描述（可选）', 'Video motion description (optional)')} hint={text(`${videoActionPrompt.length}/${spriteRowPromptMaxLength} 字；留空时使用主体描述。`, `${videoActionPrompt.length}/${spriteRowPromptMaxLength} characters; falls back to the subject brief when empty.`)}>
                  <Textarea
                    value={videoActionPrompt}
                    rows={2}
                    maxLength={spriteRowPromptMaxLength}
                    placeholder={text('例如：从站立蓄力到挥剑释放一道火焰斩', 'e.g. from charging stance to a sword swing releasing a flame slash')}
                    onChange={(e) => setVideoActionPrompt(e.target.value)}
                  />
                </PixField>
                <label className="flex items-start gap-2 rounded-lg border border-border bg-background/45 p-3 text-sm">
                  <Checkbox checked={videoReturnToFirstFrame} onCheckedChange={(value) => setVideoReturnToFirstFrame(Boolean(value))} />
                  <span className="grid gap-1">
                    <span className="font-medium">{text('回到初始帧（循环动作）', 'Return to first frame (loop)')}</span>
                    <span className="text-xs text-muted-foreground">{text('适合待机、走路等循环动作；成品会自然接回第一帧。', 'Best for idle, walk, and other looping motions; the result returns naturally to the first frame.')}</span>
                  </span>
                </label>
              </div>
            )}

            {!isSpriteVideoBridge && safeRows >= 2 && (
              <div className="grid gap-3 rounded-lg border border-border bg-background/40 p-3">
                <div className="text-xs text-muted-foreground">{text(`为每一行写一段动作描述（共 ${safeRows} 行，每行 ${safeCols} 帧）`, `Describe the action for each row (${safeRows} rows × ${safeCols} frames)`)}</div>
                {Array.from({ length: safeRows }, (_, index) => (
                  <PixField key={`row-${index}`} label={text(`第 ${index + 1} 行动作`, `Row ${index + 1} action`)} hint={text(`${(rowPrompts[index] ?? '').length}/${spriteRowPromptMaxLength} 字`, `${(rowPrompts[index] ?? '').length}/${spriteRowPromptMaxLength} characters`)}>
                    <Textarea
                      value={rowPrompts[index] ?? ''}
                      rows={2}
                      maxLength={spriteRowPromptMaxLength}
                      placeholder={text('例如：朝东行走的 8 帧循环', 'e.g. 8-frame walk cycle facing east')}
                      onChange={(e) => updateRowPrompt(index, e.target.value)}
                    />
                  </PixField>
                ))}
              </div>
            )}

            {!isSpriteVideoBridge && safeRows === 1 && (
              <PixField label={text('动作描述（可选，留空使用主体描述）', 'Action description (optional)')} hint={text(`${(rowPrompts[0] ?? '').length}/${spriteRowPromptMaxLength} 字`, `${(rowPrompts[0] ?? '').length}/${spriteRowPromptMaxLength} characters`)}>
                <Textarea
                  value={rowPrompts[0] ?? ''}
                  rows={2}
                  maxLength={spriteRowPromptMaxLength}
                  placeholder={text('例如：火焰法师挥杖释放火球的 8 帧动作', 'e.g. 8-frame fire mage casting a fireball')}
                  onChange={(e) => updateRowPrompt(0, e.target.value)}
                />
              </PixField>
            )}

            {!isSpriteVideoBridge && (
              <PixField label={text('播放 FPS', 'Playback FPS')}>
                <Input type="number" min={1} max={60} value={fps} onChange={(e) => updateFps(Number(e.target.value))} />
              </PixField>
            )}
          </div>
        )}

        {(isAsset || isSprite) && <StyleProfileControls value={styleProfile} onChange={setStyleProfile} />}

        {(isLocalPixelize || isLocalBgRemove) && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? text('上传中…', 'Uploading…') : text('上传图片', 'Upload image')}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label={text('上传图片', 'Upload image')} onChange={(event) => void uploadFile(event.currentTarget.files?.[0])} /></label></Button>{uploadMessage && <Alert variant={uploadMessage.includes('失败') ? 'destructive' : 'info'}>{uploadMessage}</Alert>}<PixPreviewFrame url={uploadUrl} file={uploadFilePreview} loading={uploading && !uploadFilePreview && !uploadUrl} label={uploading && !uploadFilePreview && !uploadUrl ? text('上传中…', 'Uploading…') : text('等待上传预览', 'Waiting for upload preview')} /></div>}

        {isLocalBgRemove && (
          <PixField label={text('去背景算法', 'Background removal algorithm')} hint={text('像素适合纯色 key 背景与像素直出；高清使用 Color-to-Alpha，保留抗锯齿软边。', 'Pixel is best for solid key backgrounds and pixel output; HD uses Color-to-Alpha to preserve anti-aliased edges.')}>
            <Select value={bgRemovalAlgorithm} onValueChange={(value) => setBgRemovalAlgorithm(bgRemovalAlgorithmValue(value))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="pixel_bg">{text('像素', 'Pixel')}</SelectItem>
                <SelectItem value="color_to_alpha">{text('高清', 'HD')}</SelectItem>
              </SelectContent>
            </Select>
          </PixField>
        )}

        {!isLocalBgRemove && <PixelControls pixelLabel={isSprite ? text('单帧尺寸', 'Frame size') : isDualGridAsset ? text('单张瓦片尺寸', 'Single tile size') : text('像素尺寸', 'Pixel size')} pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} sizeOptions={isLogoAsset ? LOGO_SIZE_OPTIONS : isDualGridAsset ? DUAL_GRID_SIZE_OPTIONS : undefined} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={isTileAsset || isDualGridAsset || (!isSprite && !removeBg)} sizeHidden={isLocalPixelize} colorDescription={isSpriteVideoBridge ? text('默认保留视频抽帧原色；该数值仅写入关键帧 / motion prompt，显式选择限色策略时才作为上限。', 'Video bridge preserves sampled source colors by default; this value is used in keyframe / motion prompts and only caps colors when an explicit palette strategy is chosen.') : undefined} />}

        {isAsset && !isDualGridAsset && !isTileAsset && <SizeRetryControls value={sizeRetry} onChange={setSizeRetry} basePrice={price} discount={discount} imageSize={pixelSize} />}

        {!isLocalBgRemove && <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={(isTileAsset || isDualGridAsset) ? false : removeBg} disabled={isSprite || isTileAsset || isDualGridAsset} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{text('透明背景', 'Transparent background')}</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={isSprite || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? text('素材直出默认视觉理解策略', 'Default vision policy for asset output') : text('跳过参考图理解', 'Skip reference understanding')}</label></div>}

        {invalidSubAssetSize && <Alert variant="destructive">{text('素材最低支持 16×16。', 'Minimum asset size is 16×16.')}</Alert>}
        {assetNameTooLong && <Alert variant="destructive">{text(`主体最多 ${assetSubjectMaxLength} 字。`, `Subject max ${assetSubjectMaxLength} characters.`)}</Alert>}
        {(dualMaterialATooLong || dualMaterialBTooLong) && <Alert variant="destructive">{text(`双瓦片材质描述最多 ${assetSubjectMaxLength} 字。`, `Dual-grid material descriptions max ${assetSubjectMaxLength} characters.`)}</Alert>}
        {isSprite && spriteSubjectTooLong && <Alert variant="destructive">{text(`序列帧主体描述最多 ${spriteSubjectMaxLength} 字。`, `Sprite subject max ${spriteSubjectMaxLength} characters.`)}</Alert>}
        {rowPromptTooLong && <Alert variant="destructive">{text(`逐行动作描述最多 ${spriteRowPromptMaxLength} 字。`, `Row action descriptions max ${spriteRowPromptMaxLength} characters.`)}</Alert>}
        {invalidGrid && <Alert variant="destructive">{text('序列帧每行/每列最多 8。', 'Sprite sequence rows and cols are capped at 8.')}</Alert>}
        {missingRowPrompts && <Alert variant="destructive">{text('多行序列帧需要为每一行填写动作描述。', 'Multi-row sequences require an action description for each row.')}</Alert>}
        <div className="flex flex-wrap items-center gap-3">
          {(isAsset || isSprite) && <PromptPreviewDialog token={token} buildPayload={() => buildCurrentPayload('prompt-preview')} disabled={submitBlocked} />}
          <Button type="submit" size="lg" disabled={loading || submitBlocked}>{loading ? text('提交中…', 'Submitting…') : isSprite ? text('生成序列帧', 'Generate sprite sequence') : isAsset ? (isDualGridAsset ? text('生成双瓦片图集', 'Generate dual-grid atlas') : isTileAsset ? text('生成平铺纹理', 'Generate tile texture') : isLogoAsset && hasAssetReference ? text('参考图生成 Logo', 'Generate logo from reference') : isLogoAsset ? text('生成游戏 Logo', 'Generate game logo') : hasAssetReference ? text('参考图重绘', 'Redraw from reference') : text('生成游戏素材', 'Generate game asset')) : isLocalBgRemove ? text('去除背景', 'Remove background') : text('生成单张素材', 'Generate single asset')}</Button>
        </div>
      </form>
    </PixPanel>
  )
}
