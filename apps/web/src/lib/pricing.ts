import type { PricingDiscount, PricingRule, VideoBridgeModel } from '../types'

export const DEFAULT_VIDEO_BRIDGE_MODEL: VideoBridgeModel = 'doubao-seedance-2-0-260128'
export const VIDEO_BRIDGE_IMAGE_PRICE_CREDITS = 10
export const VIDEO_BRIDGE_PRICE_MULTIPLIER = 20
export const VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS = 4
export const VIDEO_BRIDGE_ALLOWED_DURATION_SECONDS = [4, 5, 10, 15] as const

type VideoBridgeDurationSeconds = typeof VIDEO_BRIDGE_ALLOWED_DURATION_SECONDS[number]
type VideoBridgeModelPrice = { value: VideoBridgeModel; label: string; videoPricesCny: Record<VideoBridgeDurationSeconds, number> }

export const VIDEO_BRIDGE_MODELS: VideoBridgeModelPrice[] = [
  { value: 'doubao-seedance-2-0-260128', label: 'Seedance 2.0', videoPricesCny: { 4: 1.85, 5: 2.31, 10: 4.62, 15: 6.93 } },
  { value: 'doubao-seedance-2-0-fast-260128', label: 'Seedance 2.0 Fast', videoPricesCny: { 4: 1.49, 5: 1.86, 10: 3.72, 15: 5.57 } },
  { value: 'doubao-seedance-2-0-mini-260615', label: 'Seedance 2.0 Mini', videoPricesCny: { 4: 0.92, 5: 1.16, 10: 2.31, 15: 3.47 } },
]

export function normalizeVideoBridgeModel(value: unknown): VideoBridgeModel {
  return VIDEO_BRIDGE_MODELS.some((item) => item.value === value) ? value as VideoBridgeModel : DEFAULT_VIDEO_BRIDGE_MODEL
}

export function normalizeVideoBridgeDurationSeconds(value: number): VideoBridgeDurationSeconds {
  const seconds = Math.max(VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS, Math.round(value || 0))
  return VIDEO_BRIDGE_ALLOWED_DURATION_SECONDS.find((tier) => seconds <= tier) ?? 15
}

export function videoBridgePricingKey(model: VideoBridgeModel): string {
  return `sprite_video_bridge:${model}`
}

function videoBridgeModelPrice(model: VideoBridgeModel): VideoBridgeModelPrice {
  const fallback: VideoBridgeModelPrice = {
    value: DEFAULT_VIDEO_BRIDGE_MODEL,
    label: 'Seedance 2.0',
    videoPricesCny: { 4: 1.85, 5: 2.31, 10: 4.62, 15: 6.93 },
  }
  return VIDEO_BRIDGE_MODELS.find((item) => item.value === model) ?? fallback
}

export function videoBridgePriceCny(model: VideoBridgeModel, durationSeconds = VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS): number {
  const seconds = normalizeVideoBridgeDurationSeconds(durationSeconds)
  return videoBridgeModelPrice(model).videoPricesCny[seconds]
}

function creditsFromVideoPriceCny(priceCny: number): number {
  return Math.ceil(priceCny * VIDEO_BRIDGE_PRICE_MULTIPLIER + VIDEO_BRIDGE_IMAGE_PRICE_CREDITS - 1e-9)
}

export function videoBridgePriceCredits(
  model: VideoBridgeModel,
  pricing: PricingRule[] = [],
  durationSeconds = VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS,
): number {
  const seconds = normalizeVideoBridgeDurationSeconds(durationSeconds)
  const rule = pricing.find((item) => item.key === videoBridgePricingKey(model))
  if (rule) {
    const basePrice = Math.max(0, Math.round(rule.price_credits || 0))
    if (seconds <= VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS || basePrice <= VIDEO_BRIDGE_IMAGE_PRICE_CREDITS) return basePrice
    const videoComponent = basePrice - VIDEO_BRIDGE_IMAGE_PRICE_CREDITS
    const ratio = videoBridgePriceCny(model, seconds) / videoBridgePriceCny(model, VIDEO_BRIDGE_DEFAULT_DURATION_SECONDS)
    return VIDEO_BRIDGE_IMAGE_PRICE_CREDITS + Math.ceil(videoComponent * ratio)
  }
  return creditsFromVideoPriceCny(videoBridgePriceCny(model, seconds))
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
