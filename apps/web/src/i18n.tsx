import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react'
import i18next, { type TFunction } from 'i18next'
import { initReactI18next, I18nextProvider, useTranslation } from 'react-i18next'
import { zhCN } from './locales/zh-CN'
import { enUS } from './locales/en-US'
import type { PixLanguage } from './theme'

export const resources = {
  'zh-CN': { translation: zhCN },
    en: { translation: enUS },
} as const

export const i18n = i18next.createInstance()

void i18n
  .use(initReactI18next)
  .init({
    lng: 'zh-CN',
    fallbackLng: 'zh-CN',
    resources,
    interpolation: { escapeValue: false },
    returnNull: false,
  })

type I18nContextValue = {
  language: PixLanguage
  isEnglish: boolean
  /** @deprecated 新代码请使用 t('namespace.key')，该函数仅保留给未迁移组件兼容。 */
  text: (zh: string, en: string) => string
  t: TFunction<'translation', undefined>
}

const I18nContext = createContext<I18nContextValue>({
  language: 'zh-CN',
  isEnglish: false,
  text: (zh) => zh,
  t: ((key: string) => key) as TFunction<'translation', undefined>,
})

export function I18nProvider({ language, children }: { language: PixLanguage; children: ReactNode }) {
  useEffect(() => {
    if (i18n.language !== language) {
      void i18n.changeLanguage(language)
    }
  }, [language])

  return (
    <I18nextProvider i18n={i18n}>
      <I18nCompatProvider language={language}>{children}</I18nCompatProvider>
    </I18nextProvider>
  )
}

function I18nCompatProvider({ language, children }: { language: PixLanguage; children: ReactNode }) {
  const { t } = useTranslation()
  const value = useMemo<I18nContextValue>(() => {
    const isEnglish = language === 'en'
    return {
      language,
      isEnglish,
      text: (zh, en) => (isEnglish ? en : zh),
      t,
    }
  }, [language, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}

/** @deprecated 新代码请使用 i18next t('namespace.key')。 */
export function localText(language: PixLanguage, zh: string, en: string) {
  return language === 'en' ? en : zh
}
