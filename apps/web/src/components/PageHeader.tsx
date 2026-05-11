import { Box, Typography } from '@mui/material'

type PageHeaderProps = {
  eyebrow: string
  title: string
  description?: string
}

export function PageHeader({ eyebrow, title, description }: PageHeaderProps) {
  return (
    <Box sx={{ maxWidth: 880 }}>
      <Typography variant="overline" color="primary.main" sx={{ display: 'block', fontWeight: 900, letterSpacing: '.14em' }}>{eyebrow}</Typography>
      <Typography variant="h2" sx={{ fontSize: { xs: '2rem', md: '3.4rem' }, fontWeight: 950 }}>{title}</Typography>
      {description && <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>{description}</Typography>}
    </Box>
  )
}
