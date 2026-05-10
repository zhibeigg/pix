import type { PixelizeParams } from './types'

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
  return { ...defaultPixelize, ...overrides }
}

export function summarizePrompt(value: string | null | undefined, fallback = '无输入摘要'): string {
  const text = (value ?? '').trim()
  if (!text) return fallback
  return text.length > 92 ? `${text.slice(0, 92)}…` : text
}
