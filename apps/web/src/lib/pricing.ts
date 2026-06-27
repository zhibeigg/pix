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

/** 折后价的纯数学实现（向下取整 + 原价>0 保底 1 点），与后端 apply_discount 一致。 */
function discountedAmount(amount: number, rate: number): number {
  if (amount <= 0 || rate >= 1) return amount
  if (rate <= 0) return 0
  return Math.max(1, Math.floor(amount * rate))
}

/** 尺寸重试每次尝试单价：标准价 6 折与全局促销折扣取更优（更低）价。必须与后端 _size_retry_plan 一致。 */
export function sizeRetryAttemptPrice(base: number, retryRate: number, discount?: PricingDiscount | null): number {
  if (base <= 0) return 0
  let per = discountedAmount(base, retryRate)
  if (discount?.active) per = Math.min(per, discountedAmount(base, discount.rate))
  return per
}
