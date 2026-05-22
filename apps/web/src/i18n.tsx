import { createContext, useContext, type ReactNode } from 'react'
import type { PixLanguage } from './theme'

type I18nContextValue = {
  language: PixLanguage
  isEnglish: boolean
  text: (zh: string, en: string) => string
}

const I18nContext = createContext<I18nContextValue>({
  language: 'zh-CN',
  isEnglish: false,
  text: (zh) => zh,
})

export function I18nProvider({ language, children }: { language: PixLanguage; children: ReactNode }) {
  const isEnglish = language === 'en'
  const value: I18nContextValue = {
    language,
    isEnglish,
    text: (zh, en) => (isEnglish ? en : zh),
  }
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}

export function localText(language: PixLanguage, zh: string, en: string) {
  return language === 'en' ? en : zh
}
