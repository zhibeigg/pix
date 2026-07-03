import { useI18n } from '../i18n'
import { applyDiscount, discountPercentOff, discountZhe } from '../lib/pricing'
import type { PricingDiscount } from '../types'
import { Badge } from './ui/badge'

type Props = {
  price: number
  discount?: PricingDiscount | null
  sprite?: { billingUnits: number; basePrice: number; totalFrames: number } | null
  videoBridge?: { durationSeconds: number; totalFrames: number; fps: number } | null
  repeat?: { count: number } | null
  variant?: 'info' | 'danger' | 'outline' | 'success'
}

export function EstimateBadge({ price, discount, sprite, videoBridge, repeat, variant = 'info' }: Props) {
  const { text } = useI18n()
  const repeatCount = repeat ? Math.max(1, Math.round(repeat.count || 1)) : 1
  const discounted = applyDiscount(price, discount)
  const totalPrice = price * repeatCount
  const discountedTotal = discounted * repeatCount
  const active = !!discount?.active && discounted < price
  const frames = sprite ? text(`（共 ${sprite.totalFrames} 帧）`, ` (${sprite.totalFrames} frames)`) : ''
  const repeatLabel = repeatCount > 1
    ? text(
        `预计 ${repeatCount} × ${price} = ${discountedTotal} 点`,
        `Estimated ${repeatCount} × ${price} = ${discountedTotal} credits`,
      )
    : ''
  const videoBridgeLabel = videoBridge
    ? text(
        `预计 ${videoBridge.durationSeconds}s 视频补间 = ${price} 点（${videoBridge.totalFrames} 帧 @ ${videoBridge.fps}fps）`,
        `Estimated ${videoBridge.durationSeconds}s video bridge = ${price} credits (${videoBridge.totalFrames} frames @ ${videoBridge.fps}fps)`,
      )
    : ''

  if (!active) {
    const label = videoBridgeLabel || repeatLabel || (sprite
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
      <del className="opacity-60">{text(`${totalPrice} 点`, `${totalPrice} credits`)}</del>
      <span className="ml-1 font-semibold">{text(`${discountedTotal} 点`, `${discountedTotal} credits`)}</span>
      {repeatCount > 1 ? <span className="ml-1 opacity-70">{text(`（${repeatCount} 张 × ${discounted} 点）`, `(${repeatCount} images × ${discounted} credits)`)}</span> : null}
      {sprite ? <span className="ml-1 opacity-70">{frames}</span> : null}
      {videoBridge ? <span className="ml-1 opacity-70">{text(`（${videoBridge.durationSeconds}s · ${videoBridge.totalFrames} 帧 @ ${videoBridge.fps}fps）`, `(${videoBridge.durationSeconds}s · ${videoBridge.totalFrames} frames @ ${videoBridge.fps}fps)`)}</span> : null}
    </Badge>
  )
}
