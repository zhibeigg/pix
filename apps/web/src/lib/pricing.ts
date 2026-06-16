import type { PricingDiscount } from '../types'

/** 展示用折后价；必须与后端 apply_discount 取整规则保持一致（向下取整 + 保底 1 点）。 */
export function applyDiscount(amount: number, discount?: PricingDiscount | null): number {
  if (!discount?.active || amount <= 0) return amount
  if (discount.rate <= 0) return 0
  return Math.max(1, Math.floor(amount * discount.rate))
}

/** 0.8 → 8；0.85 → 8.5（避免浮点噪声）。 */
export function discountZhe(rate: number): number {
  return Math.round(rate * 100) / 10
}

/** 0.8 → 20（百分比折扣）。 */
export function discountPercentOff(rate: number): number {
  return Math.round((1 - rate) * 100)
}
