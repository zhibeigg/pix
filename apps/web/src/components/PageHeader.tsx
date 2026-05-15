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
      <Box sx={{ position: 'absolute', right: { xs: 18, md: 28 }, top: { xs: 18, md: 24 }, width: 84, height: 84, borderRadius: 2, bgcolor: tintMap[tint], transform: 'rotate(8deg)', opacity: .62 }} aria-hidden="true" />
      <Box sx={{ position: 'absolute', right: { xs: 72, md: 104 }, bottom: 24, width: 12, height: 12, borderRadius: .5, bgcolor: notionTokens.primary, opacity: .72 }} aria-hidden="true" />
      <Stack spacing={1.05} sx={{ maxWidth: 900, position: 'relative' }}>
        <Chip label={eyebrow} size="small" sx={{ alignSelf: 'flex-start', bgcolor: tintMap[tint], color: notionTokens.ink, borderRadius: 1, fontWeight: 600 }} />
        <Typography variant="h2" sx={{ fontSize: { xs: 32, sm: 42, md: 50 }, color: notionTokens.ink, maxWidth: 780 }}>{title}</Typography>
        {description && <Typography color="text.secondary" sx={{ maxWidth: 760, fontSize: { md: 17 }, lineHeight: 1.68 }}>{description}</Typography>}
      </Stack>
    </Box>
  )
}
