import { describe, expect, test } from 'vitest'
import { DEFAULT_VIDEO_BRIDGE_MODEL, normalizeVideoBridgeModel, videoBridgePriceCredits, videoBridgePricingKey } from './pricing'
import type { PricingRule, VideoBridgeModel } from '../types'

const models: Array<[VideoBridgeModel, number]> = [
  ['doubao-seedance-2-0-lite-260128', 30],
  ['doubao-seedance-2-0-260128', 47],
  ['doubao-seedance-2-0-pro-260128', 84],
]

describe('video bridge pricing', () => {
  test('uses default price table points', () => {
    for (const [model, price] of models) {
      expect(videoBridgePriceCredits(model)).toBe(price)
    }
  })

  test('prefers backend pricing rules when present', () => {
    const rules = [{ key: videoBridgePricingKey('doubao-seedance-2-0-pro-260128'), price_credits: 99, enabled: true, updated_at: '2026-07-02T00:00:00Z' }] as PricingRule[]
    expect(videoBridgePriceCredits('doubao-seedance-2-0-pro-260128', rules)).toBe(99)
  })

  test('scales longer submitted video durations from the four-second base price', () => {
    expect(videoBridgePriceCredits('doubao-seedance-2-0-pro-260128', [], 8)).toBe(158)
  })

  test('normalizes unknown model to default', () => {
    expect(normalizeVideoBridgeModel('unknown-model')).toBe(DEFAULT_VIDEO_BRIDGE_MODEL)
  })
})
