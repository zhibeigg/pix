import { describe, expect, test } from 'vitest'
import { DEFAULT_VIDEO_BRIDGE_MODEL, deriveVideoBridgeDurationSeconds, normalizeVideoBridgeModel, rawVideoBridgeDurationSeconds, videoBridgePriceCredits, videoBridgePricingKey } from './pricing'
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

  test('prefers customized backend pricing rules when present', () => {
    const rules = [{ key: videoBridgePricingKey('doubao-seedance-2-0-fast-260128'), price_credits: 42, enabled: true, updated_at: '2026-07-02T00:00:00Z' }] as PricingRule[]
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', rules)).toBe(42)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', rules, 5)).toBe(50)
  })

  test('keeps exact official duration table when backend rule equals default base price', () => {
    const rules = [{ key: videoBridgePricingKey('doubao-seedance-2-0-fast-260128'), price_credits: 40, enabled: true, updated_at: '2026-07-02T00:00:00Z' }] as PricingRule[]
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', rules, 15)).toBe(122)
  })

  test('uses exact duration price table and snaps unsupported seconds upward', () => {
    expect(videoBridgePriceCredits('doubao-seedance-2-0-260128', [], 5)).toBe(57)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-260128', [], 8)).toBe(84)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-260128', [], 12)).toBe(121)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', [], 6)).toBe(55)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-fast-260128', [], 15)).toBe(122)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-mini-260615', [], 10)).toBe(57)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-mini-260615', [], 14)).toBe(75)
    expect(videoBridgePriceCredits('doubao-seedance-2-0-mini-260615', [], 16)).toBe(80)
  })

  test('derives billing duration from custom frames and fps', () => {
    expect(rawVideoBridgeDurationSeconds(24, 8)).toBe(3)
    expect(deriveVideoBridgeDurationSeconds(24, 8)).toBe(4)
    expect(deriveVideoBridgeDurationSeconds(64, 8)).toBe(8)
    expect(deriveVideoBridgeDurationSeconds(64, 5)).toBe(13)
  })

  test('normalizes unknown model to default', () => {
    expect(normalizeVideoBridgeModel('unknown-model')).toBe(DEFAULT_VIDEO_BRIDGE_MODEL)
  })
})
