import { describe, expect, test } from 'vitest'
import type { GenerationJob } from '../types'
import {
  assetKindDefaults,
  computeRawReuse,
  isRawImageJob,
  jobTypeDefaults,
  mergeReusedPixelize,
  normalizeWorkbenchJobType,
  parseAssetKind,
  reusablePixelControlsFromJob,
  resolveReusableAssetKind,
  reusableWorkbenchType,
  sizeRetryStateFromJob,
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
  test('accepts the canonical kinds', () => {
    expect(parseAssetKind('item_icon')).toBe('item_icon')
    expect(parseAssetKind('ui_component')).toBe('ui_component')
    expect(parseAssetKind('tile_texture')).toBe('tile_texture')
    expect(parseAssetKind('game_logo')).toBe('game_logo')
    expect(parseAssetKind('dual_grid')).toBe('dual_grid')
    expect(parseAssetKind('character')).toBe('character')
  })

  test('normalizes spacing/case and localized labels', () => {
    expect(parseAssetKind('Dual Grid')).toBe('dual_grid')
    expect(parseAssetKind('双瓦片')).toBe('dual_grid')
    expect(parseAssetKind('平铺纹理')).toBe('tile_texture')
    expect(parseAssetKind('角色参考图')).toBe('character')
  })

  test('returns null for unknown values', () => {
    expect(parseAssetKind('')).toBeNull()
    expect(parseAssetKind(undefined)).toBeNull()
    expect(parseAssetKind('nonsense')).toBeNull()
  })
})

describe('resolveReusableAssetKind', () => {
  test('uses explicit canonical asset_kind when present', () => {
    expect(resolveReusableAssetKind({ asset_kind: 'game_logo', subject_kind: 'single_prop' })).toBe('game_logo')
    expect(resolveReusableAssetKind({ asset_kind: 'tile_texture' })).toBe('tile_texture')
  })

  test('recovers legacy asset type from subject/material fields when asset_kind stayed default', () => {
    expect(resolveReusableAssetKind({ asset_kind: 'item_icon', subject_kind: 'single_ui' })).toBe('ui_component')
    expect(resolveReusableAssetKind({ asset_kind: 'item_icon', subject_kind: 'logo_mark' })).toBe('game_logo')
    expect(resolveReusableAssetKind({ asset_kind: 'item_icon', subject_kind: 'tileable_pattern' })).toBe('tile_texture')
    expect(resolveReusableAssetKind({ asset_kind: 'item_icon', subject_kind: 'single_character' })).toBe('character')
    expect(resolveReusableAssetKind({ asset_kind: 'item_icon', material_a: '草地', material_b: '泥土' })).toBe('dual_grid')
  })

  test('falls back to item icon for empty/default asset data', () => {
    expect(resolveReusableAssetKind({})).toBe('item_icon')
    expect(resolveReusableAssetKind(null)).toBeNull()
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

  test('item_icon / game_logo / ui_component / character keep their own defaults', () => {
    expect(assetKindDefaults('item_icon')).toMatchObject({ pixelSize: '16x16', colors: 8, removeBg: true, edgeStyle: 'hard' })
    expect(assetKindDefaults('game_logo')).toMatchObject({ pixelSize: '128x64', colors: 24, removeBg: true, edgeStyle: 'hard' })
    expect(assetKindDefaults('ui_component')).toMatchObject({ pixelSize: '32x32', colors: 12, removeBg: true, edgeStyle: 'outline' })
    expect(assetKindDefaults('character')).toMatchObject({ pixelSize: '64x64', colors: 32, removeBg: true, edgeStyle: 'hard' })
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

describe('sizeRetryStateFromJob', () => {
  test('returns disabled defaults when the job has no size retry metadata', () => {
    expect(sizeRetryStateFromJob(makeJob({ params_json: {} }))).toEqual({ enabled: false, mode: 'attempts', maxAttempts: 3, maxCredits: 0 })
  })

  test('restores attempts mode from saved retry plan', () => {
    const job = makeJob({ params_json: { size_retry: { enabled: true, mode: 'attempts', max_attempts: 5, per_attempt: 4 } } })
    expect(sizeRetryStateFromJob(job)).toEqual({ enabled: true, mode: 'attempts', maxAttempts: 5, maxCredits: 0 })
  })

  test('restores credits mode and estimates legacy max credits when only per_attempt is saved', () => {
    const job = makeJob({ params_json: { size_retry: { enabled: true, mode: 'credits', max_attempts: 4, per_attempt: 6 } } })
    expect(sizeRetryStateFromJob(job)).toEqual({ enabled: true, mode: 'credits', maxAttempts: 4, maxCredits: 24 })
  })

  test('uses explicit max credits saved by newer jobs', () => {
    const job = makeJob({ params_json: { size_retry_max_credits: 80, size_retry: { enabled: true, mode: 'credits', max_attempts: 8, per_attempt: 6 } } })
    expect(sizeRetryStateFromJob(job).maxCredits).toBe(80)
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

describe('reusablePixelControlsFromJob', () => {
  test('restores pixel size and color count from saved request parameters', () => {
    const job = makeJob({
      params_json: { pixelize: { output_size: [24, 24], colors: 8 } },
      outputs: [{ pixelized_size: [48, 48], grid_readability: { color_count: 12 } }] as any,
    })
    expect(reusablePixelControlsFromJob(job, { pixelSize: '16x16', colors: 4 })).toEqual({ pixelSize: '24x24', colors: 8 })
  })

  test('keeps the requested size and never adopts the larger produced size (three-view / padded output)', () => {
    // 三视图/补边会把成品放大成用户从未选过的尺寸，复用时尺寸必须回落到调用方默认值而非产物尺寸；
    // 颜色数仍允许用产物实际可读色数兜底。
    const job = makeJob({
      params_json: { pixelize: {} },
      outputs: [{ pixelized_size: [192, 64], grid_readability: { color_count: 12 } }] as any,
    })
    expect(reusablePixelControlsFromJob(job, { pixelSize: '64x64', colors: 8 })).toEqual({ pixelSize: '64x64', colors: 12 })
  })

  test('falls back to caller defaults instead of keeping stale form state', () => {
    const job = makeJob({ params_json: {} })
    expect(reusablePixelControlsFromJob(job, { pixelSize: '64x64', colors: 32 })).toEqual({ pixelSize: '64x64', colors: 32 })
  })
})

describe('normalizeWorkbenchJobType', () => {
  test('keeps selectable single-workbench modes', () => {
    expect(normalizeWorkbenchJobType('asset')).toBe('asset')
    expect(normalizeWorkbenchJobType('sprite_sheet')).toBe('sprite_sheet')
    expect(normalizeWorkbenchJobType('local_pixelize')).toBe('local_pixelize')
    expect(normalizeWorkbenchJobType('local_bg_remove')).toBe('local_bg_remove')
  })

  test('maps history/API-only modes to selectable workbench modes', () => {
    expect(normalizeWorkbenchJobType('repixelize')).toBe('local_pixelize')
    expect(normalizeWorkbenchJobType('image_to_image')).toBe('asset')
    expect(normalizeWorkbenchJobType('text_to_image')).toBe('asset')
    expect(normalizeWorkbenchJobType('')).toBe('asset')
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

  test('maps reference-image generation jobs back to asset output', () => {
    expect(reusableWorkbenchType(makeJob({ job_type: 'image_to_image', input_image_path: 'uploads/ref.png' }))).toBe('asset')
    expect(reusableWorkbenchType(makeJob({ job_type: 'text_to_image' }))).toBe('asset')
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
