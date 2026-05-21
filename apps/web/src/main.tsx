import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import './styles.css'
import type { PixThemeMode, PixThemePreference } from './theme'

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

  useEffect(() => {
    const root = document.documentElement
    root.dataset.theme = resolvedThemeMode
    root.classList.toggle('dark', resolvedThemeMode === 'dark')
  }, [resolvedThemeMode])

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
    <App
      themeMode={resolvedThemeMode}
      themePreference={themePreference}
      systemThemeMode={systemThemeMode}
      onThemePreferenceChange={changeThemePreference}
    />
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PixThemeRoot />
  </React.StrictMode>,
)
