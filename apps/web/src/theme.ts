import { createTheme } from '@mui/material/styles'

export const notionTokens = {
  primary: '#6C47FF',
  primaryPressed: '#5A35D6',
  primaryDeep: '#3F2AA8',
  brandNavy: '#0F1B3D',
  brandNavyDeep: '#0A1230',
  brandNavyMid: '#172955',
  linkBlue: '#0B65D8',
  canvas: '#FFFFFF',
  surface: '#F7F6F3',
  surfaceSoft: '#FBFAF7',
  hairline: '#E6E2D9',
  hairlineSoft: '#EFECE5',
  hairlineStrong: '#CFC8BC',
  inkDeep: '#0F0F0F',
  ink: '#191711',
  charcoal: '#2F2B25',
  slate: '#6B665F',
  steel: '#78736D',
  stone: '#9A948B',
  muted: '#B9B2A7',
  onDark: '#FFFFFF',
  onDarkMuted: 'rgba(255,255,255,.72)',
  brandPink: '#FF7AB6',
  brandOrange: '#F59A3D',
  brandOrangeDeep: '#A84E18',
  brandPurple800: '#4B2BA8',
  brandTeal: '#18A999',
  brandGreen: '#23A455',
  brandBrown: '#8A5A34',
  tintPeach: '#FFE2D2',
  tintRose: '#FFE0EA',
  tintMint: '#DBF4E8',
  tintLavender: '#EEE5FF',
  tintSky: '#DDF0FF',
  tintYellow: '#FFF1B8',
  tintYellowBold: '#FFE45C',
  tintCream: '#FBF3DB',
  tintGray: '#F3F1EC',
  success: '#23A455',
  warning: '#D9822B',
  error: '#D92D20',
}

export const pixTheme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: notionTokens.primary, dark: notionTokens.primaryPressed, contrastText: notionTokens.onDark },
    secondary: { main: notionTokens.brandOrange, dark: notionTokens.brandOrangeDeep, contrastText: notionTokens.inkDeep },
    background: { default: notionTokens.surfaceSoft, paper: notionTokens.canvas },
    text: { primary: notionTokens.ink, secondary: notionTokens.slate },
    success: { main: notionTokens.success },
    warning: { main: notionTokens.warning },
    error: { main: notionTokens.error },
    info: { main: notionTokens.linkBlue },
    divider: notionTokens.hairline,
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
          boxShadow: 'rgba(15, 15, 15, 0.04) 0px 1px 2px 0px',
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
            color: notionTokens.onDark,
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
