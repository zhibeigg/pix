import React, { useMemo, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { App } from './App'
import './styles.css'
import { createPixTheme, type PixThemeMode } from './theme'

const THEME_KEY = 'pix_web_theme'

function initialThemeMode(): PixThemeMode {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function PixThemeRoot() {
  const [themeMode, setThemeMode] = useState<PixThemeMode>(initialThemeMode)
  const theme = useMemo(() => createPixTheme(themeMode), [themeMode])

  function toggleTheme() {
    setThemeMode((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      localStorage.setItem(THEME_KEY, next)
      return next
    })
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App themeMode={themeMode} onToggleTheme={toggleTheme} />
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PixThemeRoot />
  </React.StrictMode>,
)
