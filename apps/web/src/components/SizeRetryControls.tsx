import { useI18n } from '../i18n'
import { sizeRetryAttemptPrice } from '../lib/pricing'
import type { PricingDiscount, SizeRetryMode } from '../types'
import { DEFAULT_SIZE_OPTIONS } from './PixelControls'
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
  /** 目标像素尺寸（如 24x24）；必须来自像素尺寸可选档位。 */
  imageSize?: string | null
  /** 支持尺寸重试的像素尺寸档位；默认与 PixelControls 的可选尺寸一致。 */
  supportedSizeOptions?: string[]
  /** 重试每次尝试的计费倍率（6 折 = 0.6）。 */
  retryRate?: number
  /** 最大尝试次数硬上限。 */
  maxAttemptsLimit?: number
}

function normalizeSizeKey(size: string | null | undefined): string {
  const m = (size || '').trim().toLowerCase().replace(/×/g, 'x').replace(/\s+/g, '').match(/^(\d+)x(\d+)$/)
  if (!m) return ''
  const w = Number(m[1])
  const h = Number(m[2])
  return Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0 ? `${w}x${h}` : ''
}

/** 目标尺寸需来自像素尺寸可选档位；默认支持 16/24/32/48/64/96/128/256。 */
function isRetriableTarget(size: string | null | undefined, supportedSizeOptions: string[]): boolean {
  const target = normalizeSizeKey(size)
  if (!target) return false
  return new Set(supportedSizeOptions.map(normalizeSizeKey).filter(Boolean)).has(target)
}

function targetTooSmall(size: string | null | undefined): boolean {
  const target = normalizeSizeKey(size)
  const [width] = target.split('x').map((part) => Number(part))
  return Number.isFinite(width) && width <= 32
}

export function SizeRetryControls({ value, onChange, basePrice, discount, imageSize, supportedSizeOptions = DEFAULT_SIZE_OPTIONS, retryRate = 0.6, maxAttemptsLimit = 8 }: Props) {
  const { text } = useI18n()
  const supported = isRetriableTarget(imageSize, supportedSizeOptions)
  const tooSmall = supported && targetTooSmall(imageSize)
  const perAttempt = sizeRetryAttemptPrice(basePrice, retryRate, discount)
  const percentOff = Math.round((1 - retryRate) * 100)

  const update = (patch: Partial<SizeRetryState>) => onChange({ ...value, ...patch })

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
                  '开启后会自动多试几次，尽量让成品匹配你选择的像素尺寸。每次尝试按标准价 6 折计费（与全局折扣取更优），按实际尝试次数结算。',
                  'When enabled, Pix will retry a few times to better match your selected pixel size. Each attempt is billed at 60% (or better with global discount), settled by actual attempts.',
                )
              : text(
                  '尺寸重试要求目标像素尺寸来自上方可选档位（16 / 24 / 32 / 48 / 64 / 96 / 128 / 256）。当前目标尺寸不在可选档位中，功能不可用。',
                  'Size-match retry requires a target from the available pixel-size presets (16 / 24 / 32 / 48 / 64 / 96 / 128 / 256). Current target is not in the preset list, so it is unavailable.',
                )}
          </span>
          {tooSmall && (
            <span className="text-xs text-amber-600">
              {text(
                '提示：目标尺寸较小时可能更难命中，可增加重试次数或提高目标尺寸。',
                'Note: smaller targets can be harder to match. Increase retries or choose a larger target size.',
              )}
            </span>
          )}
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
