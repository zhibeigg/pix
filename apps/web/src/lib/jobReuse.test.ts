import { describe, expect, test } from 'vitest'
import type { GenerationJob } from '../types'
import {
  assetKindDefaults,
  computeRawReuse,
  isRawImageJob,
  jobTypeDefaults,
  mergeReusedPixelize,
  parseAssetKind,
  reusableWorkbenchType,
} from './jobReuse'

function makeJob(partial: Partial<GenerationJob> & { params_json?: Record<string, unknown> }): GenerationJob {
  return {
    id: 1,
    user_id: 1,
    batch_id: null,
    batch_name: null,
    job_type: 'asset',
    status: 'succeeded',
    prompt: null,
    input_image_path: null,
    input_image_url: null,
    params_json: {},
    price_credits: 0,
    reserved_credits: 0,
    error_message: '',
    failure_type: '',
    failure_source: '',
    failure_code: '',
    candidate_failure_count: 0,
    pipeline_warning_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    started_at: null,
    finished_at: null,
    outputs: [],
    ...partial,
  } as GenerationJob
}

describe('parseAssetKind', () => {
  test('accepts the five canonical kinds', () => {
    expect(parseAssetKind('item_icon')).toBe('item_icon')
    expect(parseAssetKind('ui_component')).toBe('ui_component')
    expect(parseAssetKind('tile_texture')).toBe('tile_texture')
    expect(parseAssetKind('game_logo')).toBe('game_logo')
    expect(parseAssetKind('dual_grid')).toBe('dual_grid')
  })

  test('normalizes spacing/case and localized labels', () => {
    expect(parseAssetKind('Dual Grid')).toBe('dual_grid')
    expect(parseAssetKind('双瓦片')).toBe('dual_grid')
    expect(parseAssetKind('平铺纹理')).toBe('tile_texture')
  })

  test('returns null for unknown values', () => {
    expect(parseAssetKind('')).toBeNull()
    expect(parseAssetKind(undefined)).toBeNull()
    expect(parseAssetKind('nonsense')).toBeNull()
  })
})

describe('assetKindDefaults', () => {
  test('tile_texture fills the canvas and drops transparent bg', () => {
    expect(assetKindDefaults('tile_texture')).toMatchObject({ pixelSize: '32x32', colors: 12, removeBg: false, edgeStyle: 'hard', clearAssetRef: true })
  })

  test('dual_grid resets material texture kinds and transition', () => {
    expect(assetKindDefaults('dual_grid')).toMatchObject({
      pixelSize: '32x32', colors: 12, removeBg: false, edgeStyle: 'hard',
      dualMaterialATextureKind: 'auto', dualMaterialBTextureKind: 'auto', dualTransitionStyle: 'rounded', clearAssetRef: true,
    })
  })

  test('item_icon / game_logo / ui_component keep their own defaults', () => {
    expect(assetKindDefaults('item_icon')).toMatchObject({ pixelSize: '16x16', colors: 8, removeBg: true, edgeStyle: 'hard' })
    expect(assetKindDefaults('game_logo')).toMatchObject({ pixelSize: '128x64', colors: 24, removeBg: true, edgeStyle: 'hard' })
    expect(assetKindDefaults('ui_component')).toMatchObject({ pixelSize: '32x32', colors: 12, removeBg: true, edgeStyle: 'outline' })
  })
})

describe('jobTypeDefaults', () => {
  test('sprite_sheet seeds the horizontal preset grid', () => {
    expect(jobTypeDefaults('sprite_sheet')).toMatchObject({ pixelSize: '64x64', colors: 16, removeBg: false, fps: 8, rows: 1, cols: 8 })
  })

  test('local_bg_remove defaults to color_to_alpha', () => {
    expect(jobTypeDefaults('local_bg_remove')).toMatchObject({ pixelSize: '128x128', colors: 16, removeBg: true, bgRemovalAlgorithm: 'color_to_alpha' })
  })

  test('local_pixelize uses pixel_bg', () => {
    expect(jobTypeDefaults('local_pixelize')).toMatchObject({ pixelSize: '128x128', colors: 16, removeBg: true, bgRemovalAlgorithm: 'pixel_bg' })
  })
})

describe('mergeReusedPixelize', () => {
  test('keeps advanced fields from the reused pixelize and applies overrides on top', () => {
    const reused = { output_size: [99, 99], colors: 99, dither: 'none', saturation: 2, palette_mode: 'kmeans', auto_crop: true }
    const merged = mergeReusedPixelize(reused, { output_size: [32, 32], colors: 12, remove_bg: false })
    expect(merged).toMatchObject({ dither: 'none', saturation: 2, palette_mode: 'kmeans', auto_crop: true, output_size: [32, 32], colors: 12, remove_bg: false })
  })

  test('returns just the overrides when there is no reused pixelize', () => {
    expect(mergeReusedPixelize(null, { output_size: [16, 16], colors: 8 })).toEqual({ output_size: [16, 16], colors: 8 })
    expect(mergeReusedPixelize(undefined, { colors: 8 })).toEqual({ colors: 8 })
  })
})

describe('isRawImageJob', () => {
  test('text_to_image with source_only is raw', () => {
    expect(isRawImageJob(makeJob({ job_type: 'text_to_image', params_json: { source_only: true } }))).toBe(true)
  })

  test('text_to_image with skip_vl + grid off is raw', () => {
    expect(isRawImageJob(makeJob({ job_type: 'text_to_image', params_json: { skip_vl: true, grid: { mode: 'off' } } }))).toBe(true)
  })

  test('image_to_image with source_only is raw', () => {
    expect(isRawImageJob(makeJob({ job_type: 'image_to_image', params_json: { source_only: true } }))).toBe(true)
  })

  test('image_to_image WITHOUT source_only (tuning job) is NOT raw', () => {
    expect(isRawImageJob(makeJob({ job_type: 'image_to_image', params_json: { grid: { mode: 'extract' } } }))).toBe(false)
  })

  test('asset and sprite jobs are not raw', () => {
    expect(isRawImageJob(makeJob({ job_type: 'asset', params_json: { asset: { asset_kind: 'tile_texture' } } }))).toBe(false)
    expect(isRawImageJob(makeJob({ job_type: 'sprite_sheet', params_json: {} }))).toBe(false)
  })
})

describe('reusableWorkbenchType', () => {
  test('maps concrete workbench types', () => {
    expect(reusableWorkbenchType(makeJob({ job_type: 'sprite_sheet' }))).toBe('sprite_sheet')
    expect(reusableWorkbenchType(makeJob({ job_type: 'local_bg_remove' }))).toBe('local_bg_remove')
    expect(reusableWorkbenchType(makeJob({ job_type: 'local_pixelize' }))).toBe('local_pixelize')
    expect(reusableWorkbenchType(makeJob({ job_type: 'repixelize' }))).toBe('local_pixelize')
    expect(reusableWorkbenchType(makeJob({ job_type: 'asset' }))).toBe('asset')
  })
})

describe('computeRawReuse', () => {
  const opts = { availableModelIds: ['image2', 'image3'], defaultModel: 'image2' }

  test('restores prompt, model, size and quality from a raw text_to_image job', () => {
    const job = makeJob({
      job_type: 'text_to_image',
      prompt: '  a knight  ',
      params_json: { source_only: true, image_model: 'image3', image_size: '1536x1024', image_quality: 'high' },
    })
    expect(computeRawReuse(job, opts)).toEqual({
      prompt: 'a knight',
      model: 'image3',
      imageSize: '1536x1024',
      quality: 'high',
      referenceImagePath: '',
    })
  })

  test('falls back to default model when stored model is unavailable, and to size/quality defaults when missing', () => {
    const job = makeJob({ job_type: 'text_to_image', prompt: 'x', params_json: { source_only: true, image_model: 'gone' } })
    expect(computeRawReuse(job, opts)).toMatchObject({ model: 'image2', imageSize: '1024x1024', quality: 'auto' })
  })

  test('keeps the reference image path for a raw image_to_image job', () => {
    const job = makeJob({ job_type: 'image_to_image', prompt: 'y', input_image_path: 'uploads/ref.png', params_json: { source_only: true, image_model: 'image2' } })
    expect(computeRawReuse(job, opts).referenceImagePath).toBe('uploads/ref.png')
  })
})
