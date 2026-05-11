import { createTheme } from '@mui/material/styles'

export type PixThemeMode = 'light' | 'dark'
export type PixThemePreference = PixThemeMode | 'system'

const lightVars = {
  '--pix-primary': '#6C47FF',
  '--pix-primary-pressed': '#5A35D6',
  '--pix-primary-deep': '#3F2AA8',
  '--pix-brand-navy': '#0F1B3D',
  '--pix-brand-navy-deep': '#0A1230',
  '--pix-brand-navy-mid': '#172955',
  '--pix-link-blue': '#0B65D8',
  '--pix-canvas': '#FFFFFF',
  '--pix-surface': '#F7F6F3',
  '--pix-surface-soft': '#FBFAF7',
  '--pix-hairline': '#E6E2D9',
  '--pix-hairline-soft': '#EFECE5',
  '--pix-hairline-strong': '#CFC8BC',
  '--pix-ink-deep': '#0F0F0F',
  '--pix-ink': '#191711',
  '--pix-charcoal': '#2F2B25',
  '--pix-slate': '#6B665F',
  '--pix-steel': '#78736D',
  '--pix-stone': '#9A948B',
  '--pix-muted': '#B9B2A7',
  '--pix-on-dark': '#FFFFFF',
  '--pix-on-dark-muted': 'rgba(255,255,255,.72)',
  '--pix-on-primary': '#FFFFFF',
  '--pix-on-secondary': '#0F0F0F',
  '--pix-brand-pink': '#FF7AB6',
  '--pix-brand-orange': '#F59A3D',
  '--pix-brand-orange-deep': '#A84E18',
  '--pix-brand-purple-800': '#4B2BA8',
  '--pix-brand-teal': '#18A999',
  '--pix-brand-green': '#23A455',
  '--pix-brand-brown': '#8A5A34',
  '--pix-tint-peach': '#FFE2D2',
  '--pix-tint-rose': '#FFE0EA',
  '--pix-tint-mint': '#DBF4E8',
  '--pix-tint-lavender': '#EEE5FF',
  '--pix-tint-sky': '#DDF0FF',
  '--pix-tint-yellow': '#FFF1B8',
  '--pix-tint-yellow-bold': '#FFE45C',
  '--pix-tint-cream': '#FBF3DB',
  '--pix-tint-gray': '#F3F1EC',
  '--pix-success': '#23A455',
  '--pix-warning': '#D9822B',
  '--pix-error': '#D92D20',
  '--pix-body-gradient-a': 'rgba(238, 229, 255, .85)',
  '--pix-body-gradient-b': 'rgba(221, 240, 255, .9)',
  '--pix-card-shadow': 'rgba(15, 15, 15, 0.04) 0px 1px 2px 0px',
  '--pix-lift-shadow': 'rgba(15, 15, 15, 0.10) 0px 16px 36px -16px',
  '--pix-mockup-shadow': 'rgba(0,0,0,.32) 0 28px 70px -28px',
  '--pix-focus-ring': '0 0 0 2px rgba(108,71,255,.16)',
  '--pix-error-panel': 'rgba(255,124,124,.10)',
}

const darkVars = {
  '--pix-primary': '#9D7CFF',
  '--pix-primary-pressed': '#7E5AF2',
  '--pix-primary-deep': '#C3B1FF',
  '--pix-brand-navy': '#09111F',
  '--pix-brand-navy-deep': '#050915',
  '--pix-brand-navy-mid': '#111C35',
  '--pix-link-blue': '#8AB7FF',
  '--pix-canvas': '#121A2B',
  '--pix-surface': '#182238',
  '--pix-surface-soft': '#0A1020',
  '--pix-hairline': '#2C3850',
  '--pix-hairline-soft': '#202B41',
  '--pix-hairline-strong': '#52617B',
  '--pix-ink-deep': '#050915',
  '--pix-ink': '#ECE5D8',
  '--pix-charcoal': '#D7CEBF',
  '--pix-slate': '#AFA695',
  '--pix-steel': '#958D81',
  '--pix-stone': '#7F776D',
  '--pix-muted': '#625C54',
  '--pix-on-dark': '#FFF8EA',
  '--pix-on-dark-muted': 'rgba(255,248,234,.74)',
  '--pix-on-primary': '#050915',
  '--pix-on-secondary': '#050915',
  '--pix-brand-pink': '#FF9AC6',
  '--pix-brand-orange': '#EFA057',
  '--pix-brand-orange-deep': '#FFBE7D',
  '--pix-brand-purple-800': '#D9CAFF',
  '--pix-brand-teal': '#55D5C7',
  '--pix-brand-green': '#75D698',
  '--pix-brand-brown': '#CE9B67',
  '--pix-tint-peach': '#3D261D',
  '--pix-tint-rose': '#3E2230',
  '--pix-tint-mint': '#173527',
  '--pix-tint-lavender': '#2A2345',
  '--pix-tint-sky': '#142E46',
  '--pix-tint-yellow': '#3B3218',
  '--pix-tint-yellow-bold': '#514418',
  '--pix-tint-cream': '#342E21',
  '--pix-tint-gray': '#222838',
  '--pix-success': '#75D698',
  '--pix-warning': '#ECA85F',
  '--pix-error': '#FF8A7A',
  '--pix-body-gradient-a': 'rgba(72, 58, 128, .34)',
  '--pix-body-gradient-b': 'rgba(24, 72, 104, .28)',
  '--pix-card-shadow': 'rgba(0, 0, 0, 0.26) 0px 1px 2px 0px',
  '--pix-lift-shadow': 'rgba(0, 0, 0, 0.42) 0px 20px 44px -22px',
  '--pix-mockup-shadow': 'rgba(0,0,0,.58) 0 32px 80px -28px',
  '--pix-focus-ring': '0 0 0 2px rgba(157,124,255,.28)',
  '--pix-error-panel': 'rgba(255,138,122,.14)',
}

export const notionTokens = {
  primary: 'var(--pix-primary)',
  primaryPressed: 'var(--pix-primary-pressed)',
  primaryDeep: 'var(--pix-primary-deep)',
  brandNavy: 'var(--pix-brand-navy)',
  brandNavyDeep: 'var(--pix-brand-navy-deep)',
  brandNavyMid: 'var(--pix-brand-navy-mid)',
  linkBlue: 'var(--pix-link-blue)',
  canvas: 'var(--pix-canvas)',
  surface: 'var(--pix-surface)',
  surfaceSoft: 'var(--pix-surface-soft)',
  hairline: 'var(--pix-hairline)',
  hairlineSoft: 'var(--pix-hairline-soft)',
  hairlineStrong: 'var(--pix-hairline-strong)',
  inkDeep: 'var(--pix-ink-deep)',
  ink: 'var(--pix-ink)',
  charcoal: 'var(--pix-charcoal)',
  slate: 'var(--pix-slate)',
  steel: 'var(--pix-steel)',
  stone: 'var(--pix-stone)',
  muted: 'var(--pix-muted)',
  onDark: 'var(--pix-on-dark)',
  onDarkMuted: 'var(--pix-on-dark-muted)',
  onPrimary: 'var(--pix-on-primary)',
  onSecondary: 'var(--pix-on-secondary)',
  brandPink: 'var(--pix-brand-pink)',
  brandOrange: 'var(--pix-brand-orange)',
  brandOrangeDeep: 'var(--pix-brand-orange-deep)',
  brandPurple800: 'var(--pix-brand-purple-800)',
  brandTeal: 'var(--pix-brand-teal)',
  brandGreen: 'var(--pix-brand-green)',
  brandBrown: 'var(--pix-brand-brown)',
  tintPeach: 'var(--pix-tint-peach)',
  tintRose: 'var(--pix-tint-rose)',
  tintMint: 'var(--pix-tint-mint)',
  tintLavender: 'var(--pix-tint-lavender)',
  tintSky: 'var(--pix-tint-sky)',
  tintYellow: 'var(--pix-tint-yellow)',
  tintYellowBold: 'var(--pix-tint-yellow-bold)',
  tintCream: 'var(--pix-tint-cream)',
  tintGray: 'var(--pix-tint-gray)',
  success: 'var(--pix-success)',
  warning: 'var(--pix-warning)',
  error: 'var(--pix-error)',
  cardShadow: 'var(--pix-card-shadow)',
  liftShadow: 'var(--pix-lift-shadow)',
  mockupShadow: 'var(--pix-mockup-shadow)',
  focusRing: 'var(--pix-focus-ring)',
  errorPanel: 'var(--pix-error-panel)',
}

function themeVars(mode: PixThemeMode) {
  return mode === 'dark' ? darkVars : lightVars
}

export function createPixTheme(mode: PixThemeMode) {
  const vars = themeVars(mode)

  return createTheme({
    palette: {
      mode,
      primary: { main: vars['--pix-primary'], dark: vars['--pix-primary-pressed'], contrastText: vars['--pix-on-primary'] },
      secondary: { main: vars['--pix-brand-orange'], dark: vars['--pix-brand-orange-deep'], contrastText: vars['--pix-on-secondary'] },
      background: { default: vars['--pix-surface-soft'], paper: vars['--pix-canvas'] },
      text: { primary: vars['--pix-ink'], secondary: vars['--pix-slate'] },
      success: { main: vars['--pix-success'] },
      warning: { main: vars['--pix-warning'] },
      error: { main: vars['--pix-error'] },
      info: { main: vars['--pix-link-blue'] },
      divider: vars['--pix-hairline'],
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: '"Notion Sans", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
      h1: { fontWeight: 600, letterSpacing: '-2px', lineHeight: 1.05 },
      h2: { fontWeight: 600, letterSpacing: '-1px', lineHeight: 1.1 },
      h3: { fontWeight: 600, letterSpacing: '-0.5px', lineHeight: 1.15 },
      h4: { fontWeight: 600, letterSpacing: '-0.5px', lineHeight: 1.2 },
      h5: { fontWeight: 600, lineHeight: 1.3 },
      h6: { fontWeight: 600, lineHeight: 1.35 },
      body1: { lineHeight: 1.55 },
      body2: { lineHeight: 1.5 },
      button: { fontWeight: 500, textTransform: 'none', letterSpacing: 0 },
      overline: { fontWeight: 600, letterSpacing: '.02em', textTransform: 'none' },
      caption: { lineHeight: 1.4 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          ':root': {
            colorScheme: mode,
            ...vars,
          },
          body: {
            background: notionTokens.surfaceSoft,
            color: notionTokens.ink,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            borderColor: notionTokens.hairline,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            border: `1px solid ${notionTokens.hairline}`,
            borderRadius: 12,
            boxShadow: notionTokens.cardShadow,
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            minHeight: 40,
            borderRadius: 8,
            padding: '10px 18px',
            fontWeight: 500,
            boxShadow: 'none',
            '&.MuiButton-containedPrimary': {
              backgroundColor: notionTokens.primary,
              color: notionTokens.onPrimary,
            },
            transition: 'transform .14s ease, box-shadow .18s ease, background-color .18s ease, border-color .18s ease',
            '@media (hover: hover)': {
              '&:hover:not(.Mui-disabled)': { transform: 'translateY(-1px)' },
            },
            '&:active:not(.Mui-disabled)': { transform: 'translateY(1px)' },
            '@media (prefers-reduced-motion: reduce)': {
              '&, &:hover:not(.Mui-disabled), &:active:not(.Mui-disabled)': { transform: 'none' },
            },
            '&.MuiButton-containedPrimary:active': {
              backgroundColor: notionTokens.primaryPressed,
            },
          },
          outlined: {
            borderColor: notionTokens.hairlineStrong,
            color: notionTokens.ink,
            backgroundColor: 'transparent',
          },
          text: {
            color: notionTokens.linkBlue,
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            minHeight: 44,
            borderRadius: 8,
            backgroundColor: notionTokens.canvas,
            '& .MuiOutlinedInput-notchedOutline': { borderColor: notionTokens.hairlineStrong },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: notionTokens.primary, borderWidth: 2 },
          },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: { color: notionTokens.steel },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            minHeight: 44,
            textTransform: 'none',
            fontWeight: 500,
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 600, borderRadius: 999 },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 12, border: `1px solid ${notionTokens.hairline}` },
        },
      },
      MuiAccordion: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            border: `1px solid ${notionTokens.hairline}`,
            boxShadow: 'none',
            '&:before': { display: 'none' },
          },
        },
      },
    },
  })
}

export const pixTheme = createPixTheme('light')
