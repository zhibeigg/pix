import { describe, expect, it } from 'vitest'

import type { GenerationJob, JobOutput, SpriteFrameOutput } from '../types'
import { spriteFpsFromJob, spriteFrameCountFromJob, spriteSheetUrlFromJob } from './spritePreview'

function job(input: Partial<GenerationJob>) {
  return input as GenerationJob
}

function output(input: Partial<JobOutput>) {
  return { sprite_frames: [], ...input } as JobOutput
}

function positionedFrames(count: number): SpriteFrameOutput[] {
  return Array.from({ length: count }, (_, index) => ({
    index: index + 1,
    row: 0,
    col: index,
    path: '',
    url: null,
    sheet_rect: { x: index * 128, y: 0, w: 128, h: 128 },
  }))
}

describe('sprite preview compatibility', () => {
  it('uses the legacy pixelized URL and requested frame count for old sprite jobs', () => {
    const legacyJob = job({
      job_type: 'sprite_sheet',
      params_json: { sprite: { frame_count: 16, rows: 2, cols: 8, fps: 8 } },
    })
    const legacyOutput = output({
      sprite_sheet_url: null,
      pixelized_url: '/files?path=sprite_sheet.png',
      sprite_frames: [],
    })

    expect(spriteSheetUrlFromJob(legacyJob, legacyOutput)).toBe('/files?path=sprite_sheet.png')
    expect(spriteFrameCountFromJob(legacyJob, legacyOutput)).toBe(16)
    expect(spriteFpsFromJob(legacyJob)).toBe(8)
  })

  it('prefers positioned output frames for modern sprite jobs', () => {
    const modernJob = job({
      job_type: 'sprite_sheet',
      params_json: { sprite: { frame_count: 16, fps: 12 } },
    })
    const modernOutput = output({
      sprite_sheet_url: '/files?path=modern_sprite_sheet.png',
      pixelized_url: '/files?path=fallback.png',
      sprite_frames: positionedFrames(16),
    })

    expect(spriteSheetUrlFromJob(modernJob, modernOutput)).toBe('/files?path=modern_sprite_sheet.png')
    expect(spriteFrameCountFromJob(modernJob, modernOutput)).toBe(16)
    expect(spriteFpsFromJob(modernJob)).toBe(12)
  })

  it('does not reinterpret an asset image with default sprite parameters as a sprite sheet', () => {
    const assetJob = job({
      job_type: 'asset',
      params_json: {
        request_fields: ['asset', 'job_type', 'pixelize', 'prompt'],
        sprite: { mode: 'mosaic', frame_count: 8, rows: 1, cols: 8, fps: 8 },
      },
    })
    const assetOutput = output({ pixelized_url: '/files?path=item.png' })

    expect(spriteSheetUrlFromJob(assetJob, assetOutput)).toBeNull()
    expect(spriteFrameCountFromJob(assetJob, assetOutput)).toBe(0)
  })

  it('still recognizes explicit sprite output metadata on migrated non-sprite jobs', () => {
    const migratedJob = job({ job_type: 'asset', params_json: {} })
    const migratedOutput = output({
      sprite_sheet_url: '/files?path=migrated_sprite_sheet.png',
      sprite_frames: positionedFrames(8),
    })

    expect(spriteSheetUrlFromJob(migratedJob, migratedOutput)).toBe('/files?path=migrated_sprite_sheet.png')
    expect(spriteFrameCountFromJob(migratedJob, migratedOutput)).toBe(8)
  })
})
