import { createTheme } from '@mui/material/styles'

export type PixThemeMode = 'light' | 'dark'
export type PixThemePreference = PixThemeMode | 'system'

const lightVars = {
  '--pix-primary': 'oklch(57% .115 292)',
  '--pix-primary-pressed': 'oklch(49% .13 292)',
  '--pix-primary-deep': 'oklch(35% .1 292)',
  '--pix-brand-navy': 'oklch(22% .043 258)',
  '--pix-brand-navy-deep': 'oklch(16% .035 258)',
  '--pix-brand-navy-mid': 'oklch(28% .05 258)',
  '--pix-link-blue': 'oklch(49% .105 248)',
  '--pix-canvas': 'oklch(97% .012 82)',
  '--pix-surface': 'oklch(94% .018 82)',
  '--pix-surface-soft': 'oklch(91% .02 82)',
  '--pix-hairline': 'oklch(84% .02 82)',
  '--pix-hairline-soft': 'oklch(89% .016 82)',
  '--pix-hairline-strong': 'oklch(72% .026 82)',
  '--pix-ink-deep': 'oklch(18% .028 78)',
  '--pix-ink': 'oklch(24% .026 78)',
  '--pix-charcoal': 'oklch(34% .023 78)',
  '--pix-slate': 'oklch(47% .02 78)',
  '--pix-steel': 'oklch(55% .018 78)',
  '--pix-stone': 'oklch(64% .017 78)',
  '--pix-muted': 'oklch(72% .014 78)',
  '--pix-on-dark': 'oklch(94% .018 82)',
  '--pix-on-dark-muted': 'oklch(84% .02 82 / .76)',
  '--pix-on-primary': 'oklch(97% .012 82)',
  '--pix-on-secondary': 'oklch(18% .028 78)',
  '--pix-brand-pink': 'oklch(66% .096 345)',
  '--pix-brand-orange': 'oklch(68% .105 64)',
  '--pix-brand-orange-deep': 'oklch(46% .095 56)',
  '--pix-brand-purple-800': 'oklch(39% .1 292)',
  '--pix-brand-teal': 'oklch(60% .085 186)',
  '--pix-brand-green': 'oklch(58% .09 154)',
  '--pix-brand-brown': 'oklch(49% .062 64)',
  '--pix-tint-peach': 'oklch(88% .04 54)',
  '--pix-tint-rose': 'oklch(88% .038 352)',
  '--pix-tint-mint': 'oklch(88% .035 164)',
  '--pix-tint-lavender': 'oklch(88% .033 292)',
  '--pix-tint-sky': 'oklch(88% .032 235)',
  '--pix-tint-yellow': 'oklch(90% .05 88)',
  '--pix-tint-yellow-bold': 'oklch(82% .09 86)',
  '--pix-tint-cream': 'oklch(91% .028 82)',
  '--pix-tint-gray': 'oklch(87% .014 82)',
  '--pix-success': 'oklch(55% .105 154)',
  '--pix-warning': 'oklch(63% .12 64)',
  '--pix-error': 'oklch(55% .16 28)',
  '--pix-body-gradient-a': 'oklch(86% .035 292 / .34)',
  '--pix-body-gradient-b': 'oklch(87% .028 186 / .28)',
  '--pix-card-shadow': 'oklch(18% .028 78 / .05) 0px 1px 2px 0px',
  '--pix-lift-shadow': 'oklch(18% .028 78 / .14) 0px 20px 42px -24px',
  '--pix-mockup-shadow': 'oklch(12% .03 258 / .38) 0 32px 80px -34px',
  '--pix-focus-ring': '0 0 0 2px oklch(57% .115 292 / .20)',
  '--pix-error-panel': 'oklch(90% .055 28 / .72)',
}

const darkVars = {
  '--pix-primary': 'oklch(72% .095 292)',
  '--pix-primary-pressed': 'oklch(66% .11 292)',
  '--pix-primary-deep': 'oklch(82% .064 292)',
  '--pix-brand-navy': 'oklch(17% .032 258)',
  '--pix-brand-navy-deep': 'oklch(12% .026 258)',
  '--pix-brand-navy-mid': 'oklch(24% .04 258)',
  '--pix-link-blue': 'oklch(75% .07 248)',
  '--pix-canvas': 'oklch(20% .032 258)',
  '--pix-surface': 'oklch(24% .035 258)',
  '--pix-surface-soft': 'oklch(15% .028 258)',
  '--pix-hairline': 'oklch(33% .035 258)',
  '--pix-hairline-soft': 'oklch(28% .032 258)',
  '--pix-hairline-strong': 'oklch(47% .036 258)',
  '--pix-ink-deep': 'oklch(96% .018 82)',
  '--pix-ink': 'oklch(90% .022 82)',
  '--pix-charcoal': 'oklch(82% .021 82)',
  '--pix-slate': 'oklch(70% .018 82)',
  '--pix-steel': 'oklch(62% .016 82)',
  '--pix-stone': 'oklch(53% .015 82)',
  '--pix-muted': 'oklch(44% .014 82)',
  '--pix-on-dark': 'oklch(95% .018 82)',
  '--pix-on-dark-muted': 'oklch(84% .02 82 / .74)',
  '--pix-on-primary': 'oklch(16% .035 258)',
  '--pix-on-secondary': 'oklch(16% .035 258)',
  '--pix-brand-pink': 'oklch(76% .08 345)',
  '--pix-brand-orange': 'oklch(76% .082 64)',
  '--pix-brand-orange-deep': 'oklch(82% .07 64)',
  '--pix-brand-purple-800': 'oklch(82% .06 292)',
  '--pix-brand-teal': 'oklch(73% .07 186)',
  '--pix-brand-green': 'oklch(72% .075 154)',
  '--pix-brand-brown': 'oklch(68% .055 64)',
  '--pix-tint-peach': 'oklch(30% .035 54)',
  '--pix-tint-rose': 'oklch(30% .036 352)',
  '--pix-tint-mint': 'oklch(30% .033 164)',
  '--pix-tint-lavender': 'oklch(31% .035 292)',
  '--pix-tint-sky': 'oklch(30% .034 235)',
  '--pix-tint-yellow': 'oklch(35% .04 88)',
  '--pix-tint-yellow-bold': 'oklch(46% .065 86)',
  '--pix-tint-cream': 'oklch(28% .028 82)',
  '--pix-tint-gray': 'oklch(27% .018 258)',
  '--pix-success': 'oklch(72% .08 154)',
  '--pix-warning': 'oklch(76% .09 64)',
  '--pix-error': 'oklch(74% .12 28)',
  '--pix-body-gradient-a': 'oklch(34% .055 292 / .22)',
  '--pix-body-gradient-b': 'oklch(30% .05 186 / .18)',
  '--pix-card-shadow': 'oklch(8% .02 258 / .28) 0px 1px 2px 0px',
  '--pix-lift-shadow': 'oklch(7% .02 258 / .48) 0px 22px 48px -26px',
  '--pix-mockup-shadow': 'oklch(5% .018 258 / .64) 0 36px 86px -34px',
  '--pix-focus-ring': '0 0 0 2px oklch(72% .095 292 / .28)',
  '--pix-error-panel': 'oklch(29% .05 28 / .78)',
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

export const checkerboardSx = {
  backgroundColor: notionTokens.canvas,
  backgroundImage: `linear-gradient(45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(-45deg, ${notionTokens.hairlineSoft} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%), linear-gradient(-45deg, transparent 75%, ${notionTokens.hairlineSoft} 75%)`,
  backgroundSize: '16px 16px',
  backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0',
}

const displayFont = '"ZCOOL QingKe HuangYou", "TsangerJinKai03", "Noto Serif SC", "Microsoft YaHei", sans-serif'
const uiFont = '"MiSans", "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif'
const monoFont = '"Maple Mono NF CN", "Cascadia Mono", "SFMono-Regular", Consolas, monospace'

function themeVars(mode: PixThemeMode) {
  return mode === 'dark' ? darkVars : lightVars
}

const materialPalettes = {
  light: {
    primary: '#6f5aa8',
    primaryPressed: '#59438f',
    secondary: '#a56f36',
    secondaryPressed: '#744423',
    canvas: '#faf7ef',
    surfaceSoft: '#eae2d7',
    ink: '#34291d',
    slate: '#746b60',
    success: '#4f8a55',
    warning: '#b47433',
    error: '#b9483d',
    linkBlue: '#3f6fa0',
    hairline: '#d8d0c5',
    onPrimary: '#faf7ef',
    onSecondary: '#34291d',
    onDark: '#f4ecdf',
  },
  dark: {
    primary: '#b9a0e6',
    primaryPressed: '#9e82d2',
    secondary: '#c89a64',
    secondaryPressed: '#d7b07b',
    canvas: '#20283a',
    surfaceSoft: '#12192a',
    ink: '#ece3d4',
    slate: '#b4aa9c',
    success: '#8ac48a',
    warning: '#d1a465',
    error: '#df8275',
    linkBlue: '#9bb8dd',
    hairline: '#44506a',
    onPrimary: '#101728',
    onSecondary: '#101728',
    onDark: '#f4ecdf',
  },
}

export function createPixTheme(mode: PixThemeMode) {
  const vars = themeVars(mode)
  const material = materialPalettes[mode]

  return createTheme({
    palette: {
      mode,
      primary: { main: material.primary, dark: material.primaryPressed, contrastText: material.onPrimary },
      secondary: { main: material.secondary, dark: material.secondaryPressed, contrastText: material.onSecondary },
      background: { default: material.surfaceSoft, paper: material.canvas },
      text: { primary: material.ink, secondary: material.slate },
      success: { main: material.success, contrastText: material.onSecondary },
      warning: { main: material.warning, contrastText: material.onSecondary },
      error: { main: material.error, contrastText: material.onDark },
      info: { main: material.linkBlue, contrastText: material.onDark },
      divider: material.hairline,
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: uiFont,
      h1: { fontFamily: displayFont, fontWeight: 600, letterSpacing: '-0.04em', lineHeight: 1.05 },
      h2: { fontFamily: displayFont, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.10 },
      h3: { fontFamily: displayFont, fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1.15 },
      h4: { fontWeight: 600, letterSpacing: '-0.014em', lineHeight: 1.20 },
      h5: { fontWeight: 600, lineHeight: 1.25 },
      h6: { fontWeight: 600, lineHeight: 1.30 },
      body1: { lineHeight: 1.55 },
      body2: { lineHeight: 1.50 },
      button: { fontWeight: 500, textTransform: 'none', letterSpacing: 0 },
      overline: { fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase' },
      caption: { lineHeight: 1.40 },
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
          code: {
            fontFamily: monoFont,
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
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: notionTokens.primary, borderWidth: 1 },
          },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: { color: notionTokens.steel, fontWeight: 650 },
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
          root: { fontWeight: 600, borderRadius: 8 },
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
