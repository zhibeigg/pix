import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import { I18nProvider } from './i18n'
import './styles.css'
import type { PixLanguage, PixThemeMode, PixThemePreference } from './theme'

const THEME_KEY = 'pix_web_theme'
const LANGUAGE_KEY = 'pix_web_language'

function getSystemThemeMode(): PixThemeMode {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function initialThemePreference(): PixThemePreference {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  return 'light'
}

function initialLanguagePreference(): PixLanguage {
  const stored = localStorage.getItem(LANGUAGE_KEY)
  if (stored === 'zh-CN' || stored === 'en') return stored
  return 'zh-CN'
}

function PixThemeRoot() {
  const [themePreference, setThemePreference] = useState<PixThemePreference>(initialThemePreference)
  const [language, setLanguage] = useState<PixLanguage>(initialLanguagePreference)
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

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  function changeThemePreference(next: PixThemePreference) {
    localStorage.setItem(THEME_KEY, next)
    setThemePreference(next)
  }

  function changeLanguage(next: PixLanguage) {
    localStorage.setItem(LANGUAGE_KEY, next)
    setLanguage(next)
  }

  return (
    <I18nProvider language={language}>
      <App
        themeMode={resolvedThemeMode}
        themePreference={themePreference}
        systemThemeMode={systemThemeMode}
        language={language}
        onThemePreferenceChange={changeThemePreference}
        onLanguageChange={changeLanguage}
      />
    </I18nProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PixThemeRoot />
  </React.StrictMode>,
)
