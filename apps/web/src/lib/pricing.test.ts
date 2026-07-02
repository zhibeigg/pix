import { describe, expect, test } from 'vitest'
import { DEFAULT_VIDEO_BRIDGE_MODEL, normalizeVideoBridgeModel, videoBridgePriceCredits, videoBridgePricingKey } from './pricing'
import type { PricingRule, VideoBridgeModel } from '../types'

const models: Array<[VideoBridgeModel, number]> = [
  ['doubao-seedance-2-0-260128', 47],
  ['doubao-seedance-2-0-fast-260128', 40],
  ['doubao-seedance-2-0-mini-260615', 29],
]

describe('video bridge pricing', () => {
  test('uses default price table points', () => {
    for (const [model, price] of models) {
      expect(videoBridgePriceCredits(model)).toBe(price)
    }
  })

  test('prefers backend pricing rules when present', () => {
    const rules = [{ key: videoBridgePricingKey('doubao-seedance-2-0-fast-260128'), price_credits: 42, enabled: true, updated_at: '2026-07-02T00:00:00Z' }] as PricingRule[]
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', rules)).toBe(42)
  })

  test('uses exact duration price table and snaps unsupported seconds upward', () => {
    expect(videoBridgePriceCredits('doubao-seedance-2-0-260128', [], 5)).toBe(57)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-260128', [], 8)).toBe(103)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', [], 15)).toBe(122)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-mini-260615', [], 10)).toBe(57)
  })

  test('normalizes unknown model to default', () => {
    expect(normalizeVideoBridgeModel('unknown-model')).toBe(DEFAULT_VIDEO_BRIDGE_MODEL)
  })
})
