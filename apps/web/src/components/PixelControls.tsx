import { useI18n } from '../i18n'
import type { EdgeStyleChoice } from '../pixelize'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Slider } from './ui/slider'
import { PixField } from './pix/PixField'
import { cn } from '../lib/utils'

const DEFAULT_SIZE_OPTIONS = ['16x16', '24x24', '32x32', '48x48', '64x64', '96x96', '128x128', '256x256']
const COLOR_PRESETS = [8, 12, 16, 24, 32, 64]
const EDGE_STYLE_OPTIONS: Array<{ value: EdgeStyleChoice; zh: string; en: string }> = [
  { value: 'outline', zh: '描边', en: 'Outline' },
  { value: 'feather', zh: '羽化边缘', en: 'Feather edge' },
  { value: 'hard', zh: '不需要', en: 'None' },
]

type PixelControlsProps = {
  pixelSize: string
  onPixelSizeChange: (value: string) => void
  colors: number
  onColorsChange: (value: number) => void
  pixelLabel?: string
  sizeOptions?: string[]
  compact?: boolean
  edgeStyle?: EdgeStyleChoice
  onEdgeStyleChange?: (value: EdgeStyleChoice) => void
  edgeStyleDisabled?: boolean
  sizeHidden?: boolean
  colorDescription?: string
}

export function PixelControls({ pixelSize, onPixelSizeChange, colors, onColorsChange, pixelLabel, sizeOptions = DEFAULT_SIZE_OPTIONS, compact = false, edgeStyle, onEdgeStyleChange, edgeStyleDisabled = false, sizeHidden = false, colorDescription }: PixelControlsProps) {
  const { text } = useI18n()
  const resolvedPixelLabel = pixelLabel ?? text('像素尺寸', 'Pixel size')
  const safeColors = clampColors(colors)
  const updateColors = (value: number) => onColorsChange(clampColors(value))
  const showEdgeStyle = edgeStyle !== undefined && onEdgeStyleChange !== undefined

  return (
    <div className={cn('grid gap-4', compact ? 'grid-cols-1' : 'md:grid-cols-[minmax(0,1fr)_minmax(300px,.85fr)]')}>
      {sizeHidden ? (
        <PixField label={resolvedPixelLabel}>
          <p className="text-xs text-muted-foreground">{text('尺寸自动按检测到的像素网格确定，无需选择。', 'Size is auto-detected from the pixel grid; no selection needed.')}</p>
        </PixField>
      ) : (
        <PixField label={resolvedPixelLabel}>
          <Input value={pixelSize} onChange={(event) => onPixelSizeChange(event.target.value)} />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {sizeOptions.map((size) => (
              <Button key={size} type="button" size="sm" variant={pixelSize === size ? 'default' : 'outline'} className="h-7 rounded-lg px-2.5 text-xs" onClick={() => onPixelSizeChange(size)}>{size}</Button>
            ))}
          </div>
        </PixField>
      )}

      <div className="rounded-lg border border-border bg-card p-3.5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('颜色数', 'Color count')}</p>
            {!compact && <p className="mt-0.5 text-xs text-muted-foreground">{colorDescription ?? text('拖动滑块，或直接输入 2–256', 'Drag the slider or enter 2–256 directly')}</p>}
          </div>
          <Input aria-label={text('颜色数', 'Color count')} type="number" min={2} max={256} value={safeColors} onChange={(event) => updateColors(Number(event.target.value))} className="h-9 w-20 text-center font-bold" />
        </div>
        <Slider className="mt-4" min={2} max={256} step={1} value={safeColors} onValueChange={updateColors} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          {COLOR_PRESETS.map((preset) => (
            <Button key={preset} type="button" size="sm" variant={safeColors === preset ? 'default' : 'outline'} className="h-7 rounded-lg px-2.5 text-xs" onClick={() => updateColors(preset)}>{preset}</Button>
          ))}
        </div>
      </div>

      {showEdgeStyle && (
        <div className={cn('rounded-lg border border-border bg-card p-3.5', !compact && 'md:col-span-2', edgeStyleDisabled && 'opacity-60')}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('边缘处理', 'Edge treatment')}</p>
              {!compact && <p className="mt-0.5 text-xs text-muted-foreground">{text('透明背景开启时生效，可选择描边、羽化边缘或不额外处理。', 'Applies when transparent background is enabled. Choose outline, feathered edge, or no extra edge treatment.')}</p>}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {EDGE_STYLE_OPTIONS.map((option) => (
              <Button key={option.value} type="button" size="sm" variant={edgeStyle === option.value ? 'default' : 'outline'} className="h-8 rounded-lg px-3 text-xs" disabled={edgeStyleDisabled} onClick={() => onEdgeStyleChange(option.value)}>{text(option.zh, option.en)}</Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function clampColors(value: number) {
  if (!Number.isFinite(value)) return 16
  return Math.max(2, Math.min(256, Math.round(value)))
}
