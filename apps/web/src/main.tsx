import React, { useEffect, useMemo, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { App } from './App'
import './styles.css'
import { createPixTheme, type PixThemeMode, type PixThemePreference } from './theme'

const THEME_KEY = 'pix_web_theme'

function getSystemThemeMode(): PixThemeMode {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function initialThemePreference(): PixThemePreference {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  return 'system'
}

function PixThemeRoot() {
  const [themePreference, setThemePreference] = useState<PixThemePreference>(initialThemePreference)
  const [systemThemeMode, setSystemThemeMode] = useState<PixThemeMode>(getSystemThemeMode)
  const resolvedThemeMode = themePreference === 'system' ? systemThemeMode : themePreference
  const theme = useMemo(() => createPixTheme(resolvedThemeMode), [resolvedThemeMode])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    function syncSystemMode() {
      setSystemThemeMode(media.matches ? 'dark' : 'light')
    }
    syncSystemMode()
    media.addEventListener('change', syncSystemMode)
    return () => media.removeEventListener('change', syncSystemMode)
  }, [])

  function changeThemePreference(next: PixThemePreference) {
    localStorage.setItem(THEME_KEY, next)
    setThemePreference(next)
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App
        themeMode={resolvedThemeMode}
        themePreference={themePreference}
        systemThemeMode={systemThemeMode}
        onThemePreferenceChange={changeThemePreference}
      />
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PixThemeRoot />
  </React.StrictMode>,
)
