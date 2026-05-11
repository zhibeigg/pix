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
  yellow: notionTokens.tintYellowBold,
}

export function PageHeader({ eyebrow, title, description, tint = 'cream' }: PageHeaderProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        border: 1,
        borderColor: 'divider',
        borderRadius: 1.5,
        bgcolor: tintMap[tint],
        p: { xs: 3, md: 4 },
      }}
    >
      <Box sx={{ position: 'absolute', right: 28, top: 24, width: 12, height: 12, borderRadius: 0.75, bgcolor: notionTokens.primary, transform: 'rotate(8deg)', opacity: .9 }} />
      <Box sx={{ position: 'absolute', right: 78, bottom: 30, width: 10, height: 10, borderRadius: 0.75, bgcolor: notionTokens.brandOrange, transform: 'rotate(-12deg)', opacity: .8 }} />
      <Stack spacing={1} sx={{ maxWidth: 880, position: 'relative' }}>
        <Chip label={eyebrow} size="small" sx={{ alignSelf: 'flex-start', bgcolor: notionTokens.canvas, color: notionTokens.brandPurple800, borderRadius: 1, fontWeight: 600 }} />
        <Typography variant="h2" sx={{ fontSize: { xs: 36, sm: 48, md: 56 }, color: notionTokens.ink, maxWidth: 760 }}>{title}</Typography>
        {description && <Typography color="text.secondary" sx={{ maxWidth: 760, fontSize: { md: 18 } }}>{description}</Typography>}
      </Stack>
    </Box>
  )
}
