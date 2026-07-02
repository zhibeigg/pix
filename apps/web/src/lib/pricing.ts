import type { PricingDiscount, PricingRule, VideoBridgeModel } from '../types'

export const DEFAULT_VIDEO_BRIDGE_MODEL: VideoBridgeModel = 'doubao-seedance-2-0-260128'
export const VIDEO_BRIDGE_IMAGE_PRICE_CREDITS = 10
export const VIDEO_BRIDGE_PRICE_MULTIPLIER = 20
export const VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS = 4

export const VIDEO_BRIDGE_MODELS: Array<{ value: VideoBridgeModel; label: string; videoPriceCny: number }> = [
  { value: 'doubao-seedance-2-0-lite-260128', label: 'Seedance 2.0 Lite', videoPriceCny: 0.984312 },
  { value: 'doubao-seedance-2-0-260128', label: 'Seedance 2.0', videoPriceCny: 1.848096 },
  { value: 'doubao-seedance-2-0-pro-260128', label: 'Seedance 2.0 Pro', videoPriceCny: 3.696192 },
]

export function normalizeVideoBridgeModel(value: unknown): VideoBridgeModel {
  return VIDEO_BRIDGE_MODELS.some((item) => item.value === value) ? value as VideoBridgeModel : DEFAULT_VIDEO_BRIDGE_MODEL
}

export function videoBridgePricingKey(model: VideoBridgeModel): string {
  return `sprite_video_bridge:${model}`
}

export function videoBridgePriceCredits(
  model: VideoBridgeModel,
  pricing: PricingRule[] = [],
  durationSeconds = VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS,
): number {
  const seconds = Math.max(VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS, Math.round(durationSeconds || 0))
  const rule = pricing.find((item) => item.key === videoBridgePricingKey(model))
  if (rule) {
    const basePrice = Math.max(0, Math.round(rule.price_credits || 0))
    if (seconds <= VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS || basePrice <= VIDEO_BRIDGE_IMAGE_PRICE_CREDITS) return basePrice
    const videoComponent = basePrice - VIDEO_BRIDGE_IMAGE_PRICE_CREDITS
    return VIDEO_BRIDGE_IMAGE_PRICE_CREDITS + Math.ceil(videoComponent * seconds / VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS)
  }
  const fallback: { value: VideoBridgeModel; label: string; videoPriceCny: number } = {
    value: DEFAULT_VIDEO_BRIDGE_MODEL,
    label: 'Seedance 2.0',
    videoPriceCny: 1.848096,
  }
  const found = VIDEO_BRIDGE_MODELS.find((item) => item.value === model) ?? fallback
  const videoPriceCny = (found.videoPriceCny / VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS) * seconds
  return Math.ceil(videoPriceCny * VIDEO_BRIDGE_PRICE_MULTIPLIER + VIDEO_BRIDGE_IMAGE_PRICE_CREDITS)
}

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
