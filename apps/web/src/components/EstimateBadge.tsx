import { useI18n } from '../i18n'
import { applyDiscount, discountPercentOff, discountZhe } from '../lib/pricing'
import type { PricingDiscount } from '../types'
import { Badge } from './ui/badge'

type Props = {
  price: number
  discount?: PricingDiscount | null
  sprite?: { billingUnits: number; basePrice: number; totalFrames: number } | null
  videoBridge?: { durationSeconds: number; totalFrames: number; fps: number } | null
  variant?: 'info' | 'danger' | 'outline' | 'success'
}

export function EstimateBadge({ price, discount, sprite, videoBridge, variant = 'info' }: Props) {
  const { text } = useI18n()
  const discounted = applyDiscount(price, discount)
  const active = !!discount?.active && discounted < price
  const frames = sprite ? text(`（共 ${sprite.totalFrames} 帧）`, ` (${sprite.totalFrames} frames)`) : ''
  const videoBridgeLabel = videoBridge
    ? text(
        `预计 ${videoBridge.durationSeconds}s 视频补间 = ${price} 点（${videoBridge.totalFrames} 帧 @ ${videoBridge.fps}fps）`,
        `Estimated ${videoBridge.durationSeconds}s video bridge = ${price} credits (${videoBridge.totalFrames} frames @ ${videoBridge.fps}fps)`,
      )
    : ''

  if (!active) {
    const label = videoBridgeLabel || (sprite
      ? text(
          `预计 ${sprite.billingUnits} × ${sprite.basePrice} = ${price} 点${frames}`,
          `Estimated ${sprite.billingUnits} × ${sprite.basePrice} = ${price} credits${frames}`,
        )
      : text(`预计 ${price} 点`, `Estimated ${price} credits`))
    return <Badge variant={variant}>{label}</Badge>
  }

  const rate = discount?.rate ?? 1
  const promo = (discount?.label || '').trim() || text(`${discountZhe(rate)} 折`, `${discountPercentOff(rate)}% OFF`)
  return (
    <Badge variant={variant}>
      <span className="mr-1 font-semibold text-amber-600">{promo}</span>
      <del className="opacity-60">{text(`${price} 点`, `${price} credits`)}</del>
      <span className="ml-1 font-semibold">{text(`${discounted} 点`, `${discounted} credits`)}</span>
      {sprite ? <span className="ml-1 opacity-70">{frames}</span> : null}
      {videoBridge ? <span className="ml-1 opacity-70">{text(`（${videoBridge.durationSeconds}s · ${videoBridge.totalFrames} 帧 @ ${videoBridge.fps}fps）`, `(${videoBridge.durationSeconds}s · ${videoBridge.totalFrames} frames @ ${videoBridge.fps}fps)`)}</span> : null}
    </Badge>
  )
}
