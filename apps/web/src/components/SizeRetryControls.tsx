import { useI18n } from '../i18n'
import { sizeRetryAttemptPrice } from '../lib/pricing'
import type { PricingDiscount, SizeRetryMode } from '../types'
import { Checkbox } from './ui/checkbox'
import { Input } from './ui/input'
import { Badge } from './ui/badge'

export type SizeRetryState = {
  enabled: boolean
  mode: SizeRetryMode
  maxAttempts: number
  maxCredits: number
}

export const DEFAULT_SIZE_RETRY: SizeRetryState = {
  enabled: false,
  mode: 'attempts',
  maxAttempts: 3,
  maxCredits: 0,
}

type Props = {
  value: SizeRetryState
  onChange: (next: SizeRetryState) => void
  /** 标准单价（基础价），用于预估每次尝试折后价与最多消耗。 */
  basePrice: number
  discount?: PricingDiscount | null
  /** 当前请求的尺寸（如 1024x1024）；为 auto / 空时该功能不可用。 */
  imageSize?: string | null
  /** 重试每次尝试的计费倍率（6 折 = 0.6）。 */
  retryRate?: number
  /** 最大尝试次数硬上限。 */
  maxAttemptsLimit?: number
}

function isConcreteSize(size: string | null | undefined): boolean {
  return !!size && /^\d+x\d+$/.test(size.trim())
}

export function SizeRetryControls({ value, onChange, basePrice, discount, imageSize, retryRate = 0.6, maxAttemptsLimit = 8 }: Props) {
  const { text } = useI18n()
  const supported = isConcreteSize(imageSize)
  const perAttempt = sizeRetryAttemptPrice(basePrice, retryRate, discount)
  const percentOff = Math.round((1 - retryRate) * 100)

  const update = (patch: Partial<SizeRetryState>) => onChange({ ...value, ...patch })

  const maxSpend = value.mode === 'attempts'
    ? perAttempt * Math.max(1, value.maxAttempts)
    : Math.max(perAttempt, value.maxCredits)
  const estimatedAttempts = value.mode === 'credits' && perAttempt > 0
    ? Math.max(1, Math.min(maxAttemptsLimit, Math.floor(Math.max(0, value.maxCredits) / perAttempt)))
    : Math.max(1, Math.min(maxAttemptsLimit, value.maxAttempts))

  return (
    <div className="grid gap-3 rounded-xl border border-input/70 bg-muted/30 p-3">
      <label className="flex items-start gap-3">
        <Checkbox
          checked={value.enabled && supported}
          disabled={!supported}
          onCheckedChange={(checked) => update({ enabled: checked === true })}
          className="mt-0.5"
        />
        <div className="grid gap-1">
          <span className="text-sm font-medium">
            {text('尺寸重试', 'Size-match retry')}
            <Badge variant="outline" className="ml-2 text-amber-600">{text(`${percentOff}% 优惠`, `${percentOff}% off`)}</Badge>
          </span>
          <span className="text-xs text-muted-foreground">
            {supported
              ? text(
                  '开启后会反复重新生成，直到实际尺寸与请求尺寸一致，或达到停止条件。每次尝试按标准价 6 折计费（与全局折扣取更优），按实际尝试次数结算。',
                  'Regenerates until the actual size matches the requested size or a stop condition is hit. Each attempt is billed at 60% of standard price (or better with global discount), settled by actual attempts.',
                )
              : text(
                  '当前尺寸为自适应/自动，无法精确匹配，尺寸重试不可用。',
                  'Current size is adaptive/auto and cannot be matched exactly, so size-match retry is unavailable.',
                )}
          </span>
        </div>
      </label>

      {value.enabled && supported && (
        <div className="grid gap-3 pl-8">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => update({ mode: 'attempts' })}
              className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${value.mode === 'attempts' ? 'border-primary bg-primary/10 text-primary' : 'border-input text-muted-foreground hover:border-primary/50'}`}
            >
              {text('按最大重试次数', 'By max attempts')}
            </button>
            <button
              type="button"
              onClick={() => update({ mode: 'credits' })}
              className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${value.mode === 'credits' ? 'border-primary bg-primary/10 text-primary' : 'border-input text-muted-foreground hover:border-primary/50'}`}
            >
              {text('按最大点数', 'By max credits')}
            </button>
          </div>

          {value.mode === 'attempts' ? (
            <label className="grid gap-1 text-xs text-muted-foreground">
              {text(`最大重试次数（含首次，1-${maxAttemptsLimit}）`, `Max attempts (incl. first, 1-${maxAttemptsLimit})`)}
              <Input
                type="number"
                min={1}
                max={maxAttemptsLimit}
                value={value.maxAttempts}
                onChange={(event) => update({ maxAttempts: Math.max(1, Math.min(maxAttemptsLimit, Math.round(Number(event.target.value) || 1))) })}
                className="w-28"
              />
            </label>
          ) : (
            <label className="grid gap-1 text-xs text-muted-foreground">
              {text('最大点数预算', 'Max credit budget')}
              <Input
                type="number"
                min={perAttempt}
                value={value.maxCredits}
                onChange={(event) => update({ maxCredits: Math.max(0, Math.round(Number(event.target.value) || 0)) })}
                className="w-28"
              />
            </label>
          )}

          <div className="text-xs text-muted-foreground">
            {text(
              `每次尝试约 ${perAttempt} 点 · 最多尝试 ${estimatedAttempts} 次 · 最多消耗约 ${perAttempt * estimatedAttempts} 点（按实际命中次数结算）`,
              `~${perAttempt} credits/attempt · up to ${estimatedAttempts} attempts · max ~${perAttempt * estimatedAttempts} credits (settled by actual attempts)`,
            )}
          </div>
        </div>
      )}
    </div>
  )
}
