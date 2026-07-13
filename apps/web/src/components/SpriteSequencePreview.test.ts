import { describe, expect, it } from 'vitest'

import { fitSpriteFrame, inferHorizontalSpriteFrames, shouldAnimateSpriteSequence } from './SpriteSequencePreview'

describe('inferHorizontalSpriteFrames', () => {
  it('derives legacy horizontal sprite-strip coordinates from the loaded image size', () => {
    const frames = inferHorizontalSpriteFrames(16, 2048, 128)

    expect(frames).toHaveLength(16)
    expect(frames[0]?.sheet_rect).toEqual({ x: 0, y: 0, w: 128, h: 128 })
    expect(frames[8]?.sheet_rect).toEqual({ x: 1024, y: 0, w: 128, h: 128 })
    expect(frames[15]?.sheet_rect).toEqual({ x: 1920, y: 0, w: 128, h: 128 })
  })

  it('refuses ambiguous or unbounded frame layouts', () => {
    expect(inferHorizontalSpriteFrames(16, 2047, 128)).toEqual([])
    expect(inferHorizontalSpriteFrames(1, 128, 128)).toEqual([])
    expect(inferHorizontalSpriteFrames(257, 32896, 128)).toEqual([])
  })
})

describe('fitSpriteFrame', () => {
  it('uses the single-frame bounds instead of exposing adjacent frames in a wide card', () => {
    expect(fitSpriteFrame(296, 120, { w: 128, h: 128 })).toEqual({
      width: 120,
      height: 120,
      scaleX: 0.9375,
      scaleY: 0.9375,
    })
  })
})

describe('shouldAnimateSpriteSequence', () => {
  const visiblePlayback = {
    frameCount: 16,
    isVisible: true,
    isDocumentVisible: true,
    prefersReducedMotion: false,
  }

  it('plays only when the sequence and page are visible', () => {
    expect(shouldAnimateSpriteSequence(visiblePlayback)).toBe(true)
    expect(shouldAnimateSpriteSequence({ ...visiblePlayback, isVisible: false })).toBe(false)
    expect(shouldAnimateSpriteSequence({ ...visiblePlayback, isDocumentVisible: false })).toBe(false)
  })

  it('keeps the first frame static for reduced-motion users', () => {
    expect(shouldAnimateSpriteSequence({ ...visiblePlayback, prefersReducedMotion: true })).toBe(false)
  })
})
