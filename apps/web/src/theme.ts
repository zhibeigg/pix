import { createTheme } from '@mui/material/styles'

export const pixTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#67c7ff', contrastText: '#07131c' },
    secondary: { main: '#f4a7dc', contrastText: '#20101a' },
    background: { default: '#14181d', paper: '#20262d' },
    text: { primary: '#eef4ff', secondary: '#aab7c7' },
    success: { main: '#77e0a1' },
    warning: { main: '#f0cf6a' },
    error: { main: '#ff7c7c' },
    info: { main: '#67c7ff' },
  },
  shape: { borderRadius: 16 },
  typography: {
    fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: { fontWeight: 900, letterSpacing: '-0.06em', lineHeight: 0.95 },
    h2: { fontWeight: 900, letterSpacing: '-0.04em', lineHeight: 1 },
    h3: { fontWeight: 850 },
    button: { fontWeight: 800, textTransform: 'none' },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background: 'radial-gradient(circle at 18% 0%, #26313a 0, #14181d 36rem)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none', border: '1px solid rgba(170,183,199,.16)' },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { backgroundImage: 'none', border: '1px solid rgba(170,183,199,.16)' },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { minHeight: 42 } },
    },
    MuiTab: {
      styleOverrides: { root: { alignItems: 'flex-start', minHeight: 56, textTransform: 'none' } },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 800 } },
    },
  },
})
