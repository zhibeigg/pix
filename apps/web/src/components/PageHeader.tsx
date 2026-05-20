import { Box, Chip, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'

type PageHeaderProps = {
  eyebrow: string
  title: string
  description?: string
  tint?: 'cream' | 'sky' | 'mint' | 'lavender' | 'yellow'
}

const tintMap = {
  cream: notionTokens.tintCream,
  sky: notionTokens.tintSky,
  mint: notionTokens.tintMint,
  lavender: notionTokens.tintLavender,
  yellow: notionTokens.tintYellow,
}

export function PageHeader({ eyebrow, title, description, tint = 'cream' }: PageHeaderProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        border: `1px solid ${notionTokens.hairline}`,
        borderRadius: 1.5,
        bgcolor: notionTokens.canvas,
        p: { xs: 2.5, md: 3.2 },
      }}
    >
      <Box
        aria-hidden="true"
        sx={{
          position: 'absolute',
          top: -48,
          right: -48,
          width: 180,
          height: 180,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${tintMap[tint]} 0%, transparent 70%)`,
          opacity: .55,
          pointerEvents: 'none',
        }}
      />
      <Stack spacing={1.05} sx={{ maxWidth: 900, position: 'relative' }}>
        <Chip label={eyebrow} size="small" sx={{ alignSelf: 'flex-start', bgcolor: tintMap[tint], color: notionTokens.ink, borderRadius: 1, fontWeight: 600, letterSpacing: '.02em' }} />
        <Typography variant="h2" sx={{ fontSize: { xs: 32, sm: 42, md: 50 }, color: notionTokens.ink, maxWidth: 780, letterSpacing: '-.03em' }}>{title}</Typography>
        {description && <Typography color="text.secondary" sx={{ maxWidth: 760, fontSize: { md: 17 }, lineHeight: 1.68 }}>{description}</Typography>}
      </Stack>
    </Box>
  )
}
