import { Box, ButtonBase, Chip, Slider, Stack, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'

const DEFAULT_SIZE_OPTIONS = ['16x16', '24x24', '32x32', '48x48', '64x64', '96x96', '128x128', '256x256']
const COLOR_PRESETS = [8, 12, 16, 24, 32, 64]

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
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) minmax(320px, .9fr)' }, gap: 1.6, alignItems: 'stretch' }}>
      <Stack spacing={.8}>
        <TextField
          label={pixelLabel}
          value={pixelSize}
          onChange={(event) => onPixelSizeChange(event.target.value)}
          fullWidth
        />
        <Stack direction="row" sx={{ flexWrap: 'wrap', gap: .55 }}>
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
              sx={{ height: 25, bgcolor: pixelSize === size ? undefined : notionTokens.canvas }}
            />
          ))}
        </Stack>
      </Stack>

      <Box
        sx={{
          border: `1px solid ${notionTokens.hairlineStrong}`,
          borderRadius: 1,
          px: 1.45,
          py: 1.15,
          bgcolor: notionTokens.canvas,
          display: 'grid',
          alignContent: 'center',
        }}
      >
        <Stack spacing={1.15}>
          <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1.25 }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontWeight: 700 }}>颜色数</Typography>
              <Typography variant="caption" color="text.secondary">拖动滑块，或直接输入 2–256</Typography>
            </Box>
            <TextField
              aria-label="颜色数"
              type="number"
              value={safeColors}
              onChange={(event) => updateColors(Number(event.target.value))}
              size="small"
              slotProps={{ htmlInput: { min: 2, max: 256, step: 1 } }}
              sx={{ width: 92, flex: '0 0 auto', '& input': { py: .75, textAlign: 'center', fontWeight: 700 } }}
            />
          </Stack>

          <Slider
            aria-label="颜色数滑块"
            value={safeColors}
            min={2}
            max={256}
            step={1}
            valueLabelDisplay="auto"
            onChange={(_, value) => updateColors(Array.isArray(value) ? value[0] : value)}
            sx={{
              px: .35,
              py: .2,
              height: 6,
              '& .MuiSlider-rail': { opacity: 1, bgcolor: notionTokens.hairlineSoft },
              '& .MuiSlider-track': { border: 'none' },
              '& .MuiSlider-thumb': {
                width: 18,
                height: 18,
                boxShadow: notionTokens.focusRing,
                '&:hover, &.Mui-focusVisible': { boxShadow: notionTokens.liftShadow },
              },
            }}
          />

          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: .55 }}>
            {COLOR_PRESETS.map((preset) => {
              const active = safeColors === preset
              return (
                <ButtonBase
                  key={preset}
                  type="button"
                  onClick={() => updateColors(preset)}
                  sx={{
                    minWidth: 38,
                    height: 24,
                    px: .9,
                    borderRadius: .85,
                    border: `1px solid ${active ? notionTokens.primary : notionTokens.hairlineStrong}`,
                    bgcolor: active ? notionTokens.primary : notionTokens.surface,
                    color: active ? notionTokens.onPrimary : notionTokens.ink,
                    fontSize: 12,
                    fontWeight: 700,
                    lineHeight: 1,
                    transition: 'background-color .14s ease, border-color .14s ease, transform .14s ease',
                    '&:hover': { transform: 'translateY(-1px)', borderColor: notionTokens.primary },
                    '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } },
                  }}
                >
                  {preset}
                </ButtonBase>
              )
            })}
          </Stack>
        </Stack>
      </Box>
    </Box>
  )
}

function clampColors(value: number) {
  if (!Number.isFinite(value)) return 16
  return Math.max(2, Math.min(256, Math.round(value)))
}
