import type { GenerationJob, GridDesignParams, PixelizeParams } from './types'

export type EdgeStyleChoice = 'hard' | 'feather' | 'outline'

export function normalizeEdgeStyle(value: unknown): EdgeStyleChoice {
  return value === 'feather' || value === 'outline' ? value : 'hard'
}

export function edgeStylePixelize(edgeStyle: EdgeStyleChoice): Pick<PixelizeParams, 'edge_style' | 'bg_feather'> {
  if (edgeStyle === 'outline') return { edge_style: 'outline', bg_feather: 1 }
  if (edgeStyle === 'feather') return { edge_style: 'feather', bg_feather: 2 }
  return { edge_style: 'hard', bg_feather: 0 }
}

export const defaultPixelize: PixelizeParams = {
  output_size: [128, 128],
  colors: 16,
  dither: 'floyd_steinberg',
  preset: 'auto',
  preview_scale: 4,
  edge_enhance: 0.1,
  saturation: 1,
  resample: 'smart',
  snap_to_grid: true,
  remove_bg: false,
  bg_tolerance: 12,
  bg_feather: 0,
  edge_style: 'hard',
  auto_crop: false,
  crop_padding: 0.12,
  crop_square: true,
  palette_mode: 'auto',
  generated_preprocess_method: 'perfect_pixel',
}

export const defaultAssetPixelize: PixelizeParams = {
  ...defaultPixelize,
  output_size: [16, 16],
  colors: 8,
  dither: 'none',
  preview_scale: 12,
  remove_bg: true,
  bg_tolerance: 26,
  bg_feather: 0,
  edge_style: 'hard',
  auto_crop: true,
  crop_padding: 0.12,
  crop_square: true,
  palette_mode: 'auto',
}

export function parsePixelSize(value: string): [number, number] {
  const [w, h] = value.toLowerCase().split('x').map((v) => Number(v.trim()))
  return [Number.isFinite(w) && w > 0 ? w : 128, Number.isFinite(h) && h > 0 ? h : 128]
}

export function buildPixelize(overrides: Partial<PixelizeParams> = {}): PixelizeParams {
  return { ...defaultPixelize, ...overrides }
}

export function buildAssetPixelize(overrides: Partial<PixelizeParams> = {}): PixelizeParams {
  return { ...defaultAssetPixelize, ...overrides }
}

export function hasInvalidSubAssetSize(size: [number, number]): boolean {
  return size[0] < 16 || size[1] < 16
}

export function buildGridDesign(): GridDesignParams {
  return { mode: 'extract' }
}

export function summarizePrompt(value: string | null | undefined, fallback = '无输入摘要'): string {
  const text = (value ?? '').trim()
  if (!text) return fallback
  return text.length > 92 ? `${text.slice(0, 92)}…` : text
}

export function jobInputSummary(job: GenerationJob, fallback = '无输入摘要'): string {
  const asset = job.params_json?.asset
  if (job.job_type === 'asset' && asset && typeof asset === 'object') {
    const name = (asset as { name?: unknown }).name
    if (typeof name === 'string' && name.trim()) return summarizePrompt(name, fallback)
  }
  return summarizePrompt(job.prompt, fallback)
}
