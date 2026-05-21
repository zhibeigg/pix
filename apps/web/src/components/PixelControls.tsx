import { Button } from './ui/button'
import { Input } from './ui/input'
import { Slider } from './ui/slider'
import { PixField } from './pix/PixField'
import { cn } from '../lib/utils'

const DEFAULT_SIZE_OPTIONS = ['16x16', '24x24', '32x32', '48x48', '64x64', '96x96', '128x128', '256x256']
const COLOR_PRESETS = [8, 12, 16, 24, 32, 64]

type PixelControlsProps = {
  pixelSize: string
  onPixelSizeChange: (value: string) => void
  colors: number
  onColorsChange: (value: number) => void
  pixelLabel?: string
  sizeOptions?: string[]
  compact?: boolean
}

export function PixelControls({ pixelSize, onPixelSizeChange, colors, onColorsChange, pixelLabel = '像素尺寸', sizeOptions = DEFAULT_SIZE_OPTIONS, compact = false }: PixelControlsProps) {
  const safeColors = clampColors(colors)
  const updateColors = (value: number) => onColorsChange(clampColors(value))

  return (
    <div className={cn('grid gap-4', compact ? 'grid-cols-1' : 'md:grid-cols-[minmax(0,1fr)_minmax(300px,.85fr)]')}>
      <PixField label={pixelLabel}>
        <Input value={pixelSize} onChange={(event) => onPixelSizeChange(event.target.value)} />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {sizeOptions.map((size) => (
            <Button key={size} type="button" size="sm" variant={pixelSize === size ? 'default' : 'outline'} className="h-7 rounded-lg px-2.5 text-xs" onClick={() => onPixelSizeChange(size)}>{size}</Button>
          ))}
        </div>
      </PixField>

      <div className="rounded-2xl border border-border bg-card p-3.5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[.12em] text-muted-foreground">颜色数</p>
            {!compact && <p className="mt-0.5 text-xs text-muted-foreground">拖动滑块，或直接输入 2–256</p>}
          </div>
          <Input aria-label="颜色数" type="number" min={2} max={256} value={safeColors} onChange={(event) => updateColors(Number(event.target.value))} className="h-9 w-20 text-center font-bold" />
        </div>
        <Slider className="mt-4" min={2} max={256} step={1} value={safeColors} onValueChange={updateColors} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          {COLOR_PRESETS.map((preset) => (
            <Button key={preset} type="button" size="sm" variant={safeColors === preset ? 'default' : 'outline'} className="h-7 rounded-lg px-2.5 text-xs" onClick={() => updateColors(preset)}>{preset}</Button>
          ))}
        </div>
      </div>
    </div>
  )
}

function clampColors(value: number) {
  if (!Number.isFinite(value)) return 16
  return Math.max(2, Math.min(256, Math.round(value)))
}
