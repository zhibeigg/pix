import { Box, Chip, Slider, Stack, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'

const DEFAULT_SIZE_OPTIONS = ['16x16', '24x24', '32x32', '48x48', '64x64', '96x96', '128x128', '256x256']
const COLOR_MARKS = [
  { value: 2, label: '2' },
  { value: 8, label: '8' },
  { value: 16, label: '16' },
  { value: 32, label: '32' },
  { value: 64, label: '64' },
  { value: 128, label: '128' },
  { value: 256, label: '256' },
]

type PixelControlsProps = {
  pixelSize: string
  onPixelSizeChange: (value: string) => void
  colors: number
  onColorsChange: (value: number) => void
  pixelLabel?: string
  sizeOptions?: string[]
}

export function PixelControls({
  pixelSize,
  onPixelSizeChange,
  colors,
  onColorsChange,
  pixelLabel = '像素尺寸',
  sizeOptions = DEFAULT_SIZE_OPTIONS,
}: PixelControlsProps) {
  const safeColors = clampColors(colors)

  function updateColors(value: number) {
    onColorsChange(clampColors(value))
  }

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'minmax(0, 1.1fr) minmax(0, 1fr)' }, gap: 2 }}>
      <TextField
        label={pixelLabel}
        value={pixelSize}
        onChange={(event) => onPixelSizeChange(event.target.value)}
        helperText={(
          <Stack direction="row" component="span" sx={{ flexWrap: 'wrap', gap: .65, pt: .55 }}>
            {sizeOptions.map((size) => (
              <Chip
                key={size}
                component="button"
                type="button"
                size="small"
                clickable
                label={size}
                color={pixelSize === size ? 'primary' : 'default'}
                variant={pixelSize === size ? 'filled' : 'outlined'}
                onClick={() => onPixelSizeChange(size)}
                sx={{ height: 24, bgcolor: pixelSize === size ? undefined : notionTokens.canvas }}
              />
            ))}
          </Stack>
        )}
        fullWidth
      />
      <Box sx={{ border: `1px solid ${notionTokens.hairlineStrong}`, borderRadius: 1, px: 1.45, py: 1.05, bgcolor: notionTokens.canvas }}>
        <Stack spacing={.85}>
          <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Typography variant="caption" color="text.secondary">颜色数</Typography>
            <TextField
              type="number"
              value={safeColors}
              onChange={(event) => updateColors(Number(event.target.value))}
              size="small"
              slotProps={{ htmlInput: { min: 2, max: 256, step: 1 } }}
              sx={{ width: 92, '& input': { py: .65, textAlign: 'center' } }}
            />
          </Stack>
          <Slider
            value={safeColors}
            min={2}
            max={256}
            step={1}
            marks={COLOR_MARKS}
            valueLabelDisplay="auto"
            onChange={(_, value) => updateColors(Array.isArray(value) ? value[0] : value)}
            sx={{ px: .5 }}
          />
        </Stack>
      </Box>
    </Box>
  )
}

function clampColors(value: number) {
  if (!Number.isFinite(value)) return 16
  return Math.max(2, Math.min(256, Math.round(value)))
}
