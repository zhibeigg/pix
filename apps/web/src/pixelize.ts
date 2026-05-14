import type { GridDesignParams, PixelizeParams } from './types'

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
}

export function parsePixelSize(value: string): [number, number] {
  const [w, h] = value.toLowerCase().split('x').map((v) => Number(v.trim()))
  return [Number.isFinite(w) && w > 0 ? w : 128, Number.isFinite(h) && h > 0 ? h : 128]
}

export function buildPixelize(overrides: Partial<PixelizeParams> = {}): PixelizeParams {
  const next = { ...defaultPixelize, ...overrides }
  const lowPixel = Math.max(next.output_size[0], next.output_size[1]) <= 32
  if (lowPixel && next.remove_bg) {
    next.edge_style = 'outline'
    next.bg_feather = Math.max(1, next.bg_feather || 0)
  }
  return next
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
