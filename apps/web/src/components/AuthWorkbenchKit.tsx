import type { ReactNode } from 'react'
import { Alert, Box, Button, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'

export const authTextFieldSx = {
  '& .MuiInputLabel-root': {
    color: notionTokens.steel,
    fontWeight: 600,
  },
  '& .MuiInputLabel-root.Mui-focused': {
    color: notionTokens.primary,
  },
  '& .MuiOutlinedInput-root': {
    minHeight: 56,
    borderRadius: '8px',
    color: notionTokens.ink,
    bgcolor: notionTokens.canvas,
    transition: 'background-color .18s ease, border-color .18s ease, transform .18s ease',
  },
  '& .MuiOutlinedInput-input': {
    color: notionTokens.ink,
    fontWeight: 650,
    letterSpacing: '.01em',
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: notionTokens.hairlineStrong,
  },
  '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': {
    borderColor: notionTokens.primary,
  },
  '& .MuiOutlinedInput-root.Mui-focused': {
    bgcolor: notionTokens.surface,
  },
  '& .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
    borderColor: notionTokens.primary,
    borderWidth: 2,
  },
  '& .MuiFormHelperText-root': {
    color: notionTokens.steel,
  },
}

type AuthCardFrameProps = {
  eyebrow: string
  title: string
  subtitle?: string
  actionLabel?: string
  onAction?: () => void
  children: ReactNode
  footer?: ReactNode
}

export function AuthCardFrame({ eyebrow, title, subtitle, actionLabel, onAction, children, footer }: AuthCardFrameProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        isolation: 'isolate',
        width: '100%',
        maxWidth: 640,
        mx: 'auto',
        borderRadius: '12px',
        border: `1px solid ${notionTokens.hairline}`,
        bgcolor: notionTokens.canvas,
        color: notionTokens.ink,
        boxShadow: notionTokens.mockupShadow,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ position: 'absolute', top: 18, right: 18, display: 'grid', gridTemplateColumns: 'repeat(3, 5px)', gap: '5px', opacity: .35 }} aria-hidden="true">
        {Array.from({ length: 6 }).map((_, index) => (
          <Box key={index} sx={{ width: 5, height: 5, borderRadius: '2px', bgcolor: index % 2 ? notionTokens.tintYellow : notionTokens.tintLavender }} />
        ))}
      </Box>
      <Stack spacing={3} sx={{ position: 'relative', p: { xs: 2, sm: 2.4 }, pt: { xs: 2.4, sm: 3 } }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
          <Box sx={{ minWidth: 0, pr: 7 }}>
            <Typography variant="overline" sx={{ color: notionTokens.steel, fontWeight: 600, letterSpacing: '.03em' }}>{eyebrow}</Typography>
            <Typography variant="h4" component="h2" sx={{ mt: .4, color: notionTokens.inkDeep, fontSize: { xs: 26, sm: 30 }, letterSpacing: '-.04em' }}>{title}</Typography>
            {subtitle && <Typography sx={{ mt: .8, color: notionTokens.slate, lineHeight: 1.65 }}>{subtitle}</Typography>}
          </Box>
          {actionLabel && onAction && (
            <Button
              type="button"
              variant="outlined"
              onClick={onAction}
              sx={{ flex: '0 0 auto', minHeight: 46, px: 2 }}
            >
              {actionLabel}
            </Button>
          )}
        </Stack>
        {children}
        {footer && <Box>{footer}</Box>}
      </Stack>
    </Box>
  )
}

type AuthSceneProps = {
  label: string
  title: string
  description: string
  stats?: Array<{ label: string; value: string | number }>
  children: ReactNode
}

export function AuthScene({ label, title, description, stats, children }: AuthSceneProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        minHeight: { md: '100vh' },
        display: 'flex',
        alignItems: 'center',
        bgcolor: notionTokens.surfaceSoft,
        color: notionTokens.ink,
        px: { xs: 2, md: 4 },
        py: { xs: 7, md: 9 },
        overflow: 'hidden',
      }}
    >
      <Box sx={{ position: 'absolute', inset: 0, opacity: .04, backgroundImage: `linear-gradient(${notionTokens.hairlineStrong} 1px, transparent 1px), linear-gradient(90deg, ${notionTokens.hairlineStrong} 1px, transparent 1px)`, backgroundSize: '32px 32px' }} aria-hidden="true" />
      <Box sx={{ position: 'absolute', left: { xs: -60, md: 42 }, bottom: { xs: 24, md: 72 }, width: 180, height: 180, opacity: .08, background: `linear-gradient(135deg, ${notionTokens.tintYellow}, ${notionTokens.tintLavender})`, clipPath: 'polygon(0 0, 100% 0, 100% 18%, 18% 18%, 18% 100%, 0 100%)' }} aria-hidden="true" />
      <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1152, mx: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 4, lg: 7 }, alignItems: 'center' }}>
        <Stack spacing={2.5} sx={{ maxWidth: 560 }}>
          <Box sx={{ justifySelf: { xs: 'start', sm: 'end' }, display: 'inline-flex', alignItems: 'center', gap: 1, px: 1.2, py: .7, borderRadius: '8px', border: `1px solid ${notionTokens.hairline}`, bgcolor: notionTokens.canvas }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '3px', bgcolor: notionTokens.tintYellowBold }} />
            <Typography variant="caption" sx={{ color: notionTokens.ink, fontWeight: 600 }}>{label}</Typography>
          </Box>
          <Typography variant="h2" sx={{ color: notionTokens.inkDeep, fontSize: { xs: 38, md: 56 }, letterSpacing: '-.06em', maxWidth: 620 }}>{title}</Typography>
          <Typography sx={{ color: notionTokens.slate, maxWidth: 560, fontSize: { md: 18 }, lineHeight: 1.72 }}>{description}</Typography>
          {stats && (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1.2, pt: 1 }}>
              {stats.map((item) => <AuthStat key={item.label} label={item.label} value={item.value} />)}
            </Box>
          )}
        </Stack>
        <Box>{children}</Box>
      </Box>
    </Box>
  )
}

export function AuthInlineAlert({ severity, children }: { severity: 'info' | 'error' | 'success'; children: ReactNode }) {
  return (
    <Alert severity={severity} sx={{ alignItems: 'center', borderRadius: '12px' }}>
      {children}
    </Alert>
  )
}

function AuthStat({ label, value }: { label: string; value: string | number }) {
  return (
    <Box sx={{ border: `1px solid ${notionTokens.hairline}`, borderRadius: '8px', bgcolor: notionTokens.canvas, px: 1.5, py: 1.2, minWidth: 0 }}>
      <Typography sx={{ color: notionTokens.primary, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }} noWrap>{value}</Typography>
      <Typography variant="caption" sx={{ color: notionTokens.steel }} noWrap>{label}</Typography>
    </Box>
  )
}
