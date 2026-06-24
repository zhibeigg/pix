import type { GenerationJob, JobType, PixelizeParams, TextureKind } from '../types'
import type { BgRemovalAlgorithmChoice, EdgeStyleChoice } from '../pixelize'

export type AssetKindChoice = 'item_icon' | 'ui_component' | 'tile_texture' | 'game_logo' | 'dual_grid'
export type DualGridTransitionStyle = 'rounded' | 'hard' | 'outline'

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : null
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/** 把任务里存的 asset_kind（含历史/本地化写法）归一到当前可选的素材类型。 */
export function parseAssetKind(value: unknown): AssetKindChoice | null {
  const raw = stringValue(value).trim()
  const normalized = raw.toLocaleLowerCase().replace(/[\s\-/]+/g, '_')
  if (normalized === 'item_icon' || normalized === 'itemicon' || raw === '物品图标') return 'item_icon'
  if (normalized === 'ui_component' || normalized === 'uicomponent' || raw === 'UI 组件' || raw === '界面组件') return 'ui_component'
  if (normalized === 'tile_texture' || normalized === 'tileable_texture' || normalized === 'tileabletexture' || raw === '平铺纹理' || raw === '无缝纹理') return 'tile_texture'
  if (normalized === 'game_logo' || normalized === 'gamelogo' || normalized === 'logo' || normalized === 'logo_mark' || normalized === '游戏_logo' || raw === '游戏 Logo' || raw === '游戏Logo') return 'game_logo'
  if (normalized === 'dual_grid' || normalized === 'dualgrid' || normalized === 'dual_grid_tileset' || raw === '双瓦片' || raw === '过渡瓦片') return 'dual_grid'
  return null
}

export type AssetKindDefaults = {
  pixelSize: string
  colors: number
  removeBg: boolean
  edgeStyle: EdgeStyleChoice
  textureKind?: TextureKind
  dualMaterialATextureKind?: TextureKind
  dualMaterialBTextureKind?: TextureKind
  dualTransitionStyle?: DualGridTransitionStyle
  clearAssetRef?: boolean
}

/** 用户手动切换素材类型时套用的常用默认值（取代原先脆弱的 assetKind-reset 副作用）。 */
export function assetKindDefaults(assetKind: AssetKindChoice): AssetKindDefaults {
  switch (assetKind) {
    case 'tile_texture':
      return { pixelSize: '32x32', colors: 12, removeBg: false, edgeStyle: 'hard', textureKind: 'auto', clearAssetRef: true }
    case 'dual_grid':
      return { pixelSize: '32x32', colors: 12, removeBg: false, edgeStyle: 'hard', dualMaterialATextureKind: 'auto', dualMaterialBTextureKind: 'auto', dualTransitionStyle: 'rounded', clearAssetRef: true }
    case 'game_logo':
      return { pixelSize: '128x64', colors: 24, removeBg: true, edgeStyle: 'hard' }
    case 'ui_component':
      return { pixelSize: '32x32', colors: 12, removeBg: true, edgeStyle: 'outline' }
    case 'item_icon':
    default:
      return { pixelSize: '16x16', colors: 8, removeBg: true, edgeStyle: 'hard' }
  }
}

export type JobTypeDefaults = {
  pixelSize: string
  colors: number
  removeBg: boolean
  edgeStyle?: EdgeStyleChoice
  bgRemovalAlgorithm?: BgRemovalAlgorithmChoice
  fps?: number
  rows?: number
  cols?: number
  spritePreset?: 'horizontal'
  rowPrompts?: string[]
}

/** 用户手动切换模式时套用的默认值（取代原先脆弱的 mode-reset 副作用）。 */
export function jobTypeDefaults(jobType: JobType): JobTypeDefaults {
  switch (jobType) {
    case 'sprite_sheet':
      return { pixelSize: '64x64', colors: 16, removeBg: false, fps: 8, rows: 1, cols: 8, spritePreset: 'horizontal', rowPrompts: [''] }
    case 'local_bg_remove':
      return { pixelSize: '128x128', colors: 16, removeBg: true, edgeStyle: 'hard', bgRemovalAlgorithm: 'color_to_alpha' }
    case 'local_pixelize':
    case 'repixelize':
      return { pixelSize: '128x128', colors: 16, removeBg: true, bgRemovalAlgorithm: 'pixel_bg' }
    case 'asset':
    default:
      return { pixelSize: '16x16', colors: 8, removeBg: true, edgeStyle: 'hard', bgRemovalAlgorithm: 'pixel_bg' }
  }
}

/**
 * 重新提交时合并复用作品的完整像素参数：以原作品 pixelize 为底，UI 可编辑字段覆盖在上。
 * 这样 dither/preset/saturation/auto_crop/palette_mode 等界面不暴露的参数不会被默认值冲掉。
 */
export function mergeReusedPixelize(
  reused: Record<string, unknown> | null | undefined,
  overrides: Partial<PixelizeParams>,
): Partial<PixelizeParams> {
  const base = asRecord(reused)
  if (!base) return { ...overrides }
  return { ...(base as Partial<PixelizeParams>), ...overrides }
}

/**
 * 原始生图判定（与原 RawImagePage 内联逻辑一致，抽出共享给复用路由）。
 * 文生图：source_only=true 或 (skip_vl + grid=off)；图生图：source_only=true。
 */
export function isRawImageJob(job: GenerationJob): boolean {
  const params = asRecord(job.params_json) ?? {}
  const grid = asRecord(params.grid)
  const gridMode = grid && 'mode' in grid ? grid.mode : null
  if (job.job_type === 'text_to_image' && (params.source_only === true || (params.skip_vl === true && gridMode === 'off'))) return true
  if (job.job_type === 'image_to_image' && params.source_only === true) return true
  return false
}

/** 把作品类型映射到单图工作台可复用的 job_type（原始生图由路由层另行分流，不会进这里）。 */
export function reusableWorkbenchType(job: GenerationJob): JobType {
  if (job.job_type === 'sprite_sheet') return 'sprite_sheet'
  if (job.job_type === 'local_bg_remove') return 'local_bg_remove'
  if (job.job_type === 'local_pixelize' || job.job_type === 'repixelize') return 'local_pixelize'
  return 'asset'
}

export type RawReuseState = {
  prompt: string
  model: string
  imageSize: string
  quality: string
  referenceImagePath: string
}

export type RawReuseOptions = {
  availableModelIds: string[]
  defaultModel: string
  fallbackSize?: string
  fallbackQuality?: string
}

/** 计算原始生图作品复用后应回填到 RawImagePage 的表单值。 */
export function computeRawReuse(job: GenerationJob, opts: RawReuseOptions): RawReuseState {
  const params = asRecord(job.params_json) ?? {}
  const storedModel = stringValue(params.image_model)
  const model = storedModel && opts.availableModelIds.includes(storedModel) ? storedModel : opts.defaultModel
  const storedSize = stringValue(params.image_size)
  const storedQuality = stringValue(params.image_quality)
  return {
    prompt: job.prompt?.trim() ?? '',
    model,
    imageSize: storedSize || (opts.fallbackSize ?? '1024x1024'),
    quality: storedQuality || (opts.fallbackQuality ?? 'auto'),
    referenceImagePath: job.input_image_path ?? '',
  }
}
