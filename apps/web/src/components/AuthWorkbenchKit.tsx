import type { ReactNode } from 'react'
import { Alert, Box, Button, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'

export const authTextFieldSx = {
  '& .MuiInputLabel-root': {
    color: 'rgba(255,248,234,.62)',
    fontWeight: 600,
  },
  '& .MuiInputLabel-root.Mui-focused': {
    color: 'oklch(86% .065 245)',
  },
  '& .MuiOutlinedInput-root': {
    minHeight: 56,
    borderRadius: '9px',
    color: notionTokens.onDark,
    bgcolor: 'oklch(17% .026 263)',
    transition: 'background-color .18s ease, border-color .18s ease, transform .18s ease',
  },
  '& .MuiOutlinedInput-input': {
    color: notionTokens.onDark,
    fontWeight: 650,
    letterSpacing: '.01em',
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: 'oklch(54% .055 255)',
  },
  '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': {
    borderColor: 'oklch(72% .07 250)',
  },
  '& .MuiOutlinedInput-root.Mui-focused': {
    bgcolor: 'oklch(47% .105 247)',
  },
  '& .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
    borderColor: 'oklch(75% .08 246)',
    borderWidth: 1,
  },
  '& .MuiFormHelperText-root': {
    color: 'rgba(255,248,234,.66)',
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
        borderRadius: '14px',
        border: '1px solid oklch(44% .052 257)',
        bgcolor: 'oklch(16% .028 263)',
        color: notionTokens.onDark,
        boxShadow: '0 28px 80px -42px rgba(0,0,0,.86)',
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: 0,
          zIndex: -1,
          background: 'radial-gradient(circle at 12% 4%, oklch(37% .08 255 / .22), transparent 34%), linear-gradient(135deg, oklch(18% .03 263), oklch(14% .025 263))',
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          inset: 12,
          borderRadius: '10px',
          border: '1px solid oklch(28% .04 258 / .62)',
          pointerEvents: 'none',
        },
      }}
    >
      <Box sx={{ position: 'absolute', top: 18, right: 18, display: 'grid', gridTemplateColumns: 'repeat(3, 5px)', gap: '5px', opacity: .55 }} aria-hidden="true">
        {Array.from({ length: 6 }).map((_, index) => (
          <Box key={index} sx={{ width: 5, height: 5, borderRadius: '2px', bgcolor: index % 2 ? notionTokens.tintYellowBold : notionTokens.brandPink }} />
        ))}
      </Box>
      <Stack spacing={3} sx={{ position: 'relative', p: { xs: 2, sm: 2.4 }, pt: { xs: 2.4, sm: 3 } }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
          <Box sx={{ minWidth: 0, pr: 7 }}>
            <Typography variant="overline" sx={{ color: 'rgba(255,248,234,.78)', fontWeight: 800, letterSpacing: '.03em' }}>{eyebrow}</Typography>
            <Typography variant="h4" component="h2" sx={{ mt: .4, color: notionTokens.onDark, fontSize: { xs: 26, sm: 30 }, letterSpacing: '-.04em' }}>{title}</Typography>
            {subtitle && <Typography sx={{ mt: .8, color: notionTokens.onDarkMuted, lineHeight: 1.65 }}>{subtitle}</Typography>}
          </Box>
          {actionLabel && onAction && (
            <Button
              type="button"
              variant="outlined"
              onClick={onAction}
              sx={{
                flex: '0 0 auto',
                minHeight: 46,
                px: 2,
                borderColor: 'oklch(58% .06 254)',
                color: notionTokens.onDark,
                bgcolor: 'oklch(14% .024 263)',
                '&:hover': { borderColor: 'oklch(78% .07 250)', bgcolor: 'oklch(20% .036 263)' },
              }}
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
        bgcolor: notionTokens.brandNavyDeep,
        color: notionTokens.onDark,
        px: { xs: 2, md: 4 },
        py: { xs: 7, md: 9 },
        overflow: 'hidden',
      }}
    >
      <Box sx={{ position: 'absolute', inset: 0, opacity: .2, backgroundImage: 'linear-gradient(oklch(92% .03 248 / .18) 1px, transparent 1px), linear-gradient(90deg, oklch(92% .03 248 / .18) 1px, transparent 1px)', backgroundSize: '32px 32px' }} aria-hidden="true" />
      <Box sx={{ position: 'absolute', left: { xs: -60, md: 42 }, bottom: { xs: 24, md: 72 }, width: 180, height: 180, opacity: .5, background: 'linear-gradient(135deg, oklch(77% .17 82), oklch(64% .16 322))', clipPath: 'polygon(0 0, 100% 0, 100% 18%, 18% 18%, 18% 100%, 0 100%)' }} aria-hidden="true" />
      <Box sx={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 1152, mx: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '.9fr 1.1fr' }, gap: { xs: 4, lg: 7 }, alignItems: 'center' }}>
        <Stack spacing={2.5} sx={{ maxWidth: 560 }}>
          <Box sx={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 1, px: 1.2, py: .7, borderRadius: '9px', border: '1px solid oklch(45% .06 256)', bgcolor: 'oklch(16% .03 263)' }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '3px', bgcolor: notionTokens.tintYellowBold }} />
            <Typography variant="caption" sx={{ color: notionTokens.onDark, fontWeight: 800 }}>{label}</Typography>
          </Box>
          <Typography variant="h2" sx={{ color: notionTokens.onDark, fontSize: { xs: 38, md: 56 }, letterSpacing: '-.06em', maxWidth: 620 }}>{title}</Typography>
          <Typography sx={{ color: notionTokens.onDarkMuted, maxWidth: 560, fontSize: { md: 18 }, lineHeight: 1.72 }}>{description}</Typography>
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
  const styles = {
    info: { bg: 'oklch(25% .047 253)', border: 'oklch(48% .07 250)', color: notionTokens.onDark },
    error: { bg: 'oklch(15% .045 35)', border: 'oklch(59% .18 35)', color: 'oklch(91% .055 50)' },
    success: { bg: 'oklch(22% .055 158)', border: 'oklch(63% .12 156)', color: 'oklch(91% .07 150)' },
  }[severity]

  return (
    <Alert
      severity={severity}
      sx={{
        alignItems: 'center',
        borderRadius: '10px',
        border: `1px solid ${styles.border}`,
        bgcolor: styles.bg,
        color: styles.color,
        '& .MuiAlert-icon': { color: styles.color },
      }}
    >
      {children}
    </Alert>
  )
}

function AuthStat({ label, value }: { label: string; value: string | number }) {
  return (
    <Box sx={{ border: '1px solid oklch(43% .052 257)', borderRadius: '10px', bgcolor: 'oklch(15% .026 263)', px: 1.5, py: 1.2, minWidth: 0 }}>
      <Typography sx={{ color: notionTokens.tintYellowBold, fontWeight: 900, fontVariantNumeric: 'tabular-nums' }} noWrap>{value}</Typography>
      <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }} noWrap>{label}</Typography>
    </Box>
  )
}
