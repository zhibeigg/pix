import { useCallback, useEffect, useState } from 'react'
import type { PixLanguage } from '../theme'
import { applyPageSeo } from '../lib/seo'
import type { AppPage } from '../components/AppTabs'
import type { User } from '../types'

const HASH_PAGES: AppPage[] = ['home', 'workspace', 'raw-image', 'gallery', 'packs', 'billing', 'rewards', 'api', 'admin']

export function pageFromHash(user: User | null): AppPage {
  const pathname = window.location.pathname.replace(/\/+$/, '') || '/'
  const rootPath = pathname === '/' || pathname === '/index.html'
  const hash = window.location.hash || ''
  if (!hash) return rootPath ? 'home' : 'not-found'
  // `#/workspace` 是应用路由；`#auth-panel` / `#examples` 是首页锚点，不应被识别为 404。
  if (!hash.startsWith('#/')) return rootPath ? 'home' : 'not-found'
  const raw = hash.slice(2).split('?', 1)[0]
  if (!raw) return rootPath ? 'home' : 'not-found'
  if (!HASH_PAGES.includes(raw as AppPage)) return 'not-found'
  const page = raw as AppPage
  if (page === 'admin' && user?.role !== 'admin') return 'workspace'
  return page
}

/**
 * Hash 路由：page 状态、navigate、hashchange 同步与按页面应用 SEO。
 * 依赖 user 用于 admin 页守卫（非 admin 访问 #/admin 回落到 workspace）。
 */
export function useHashRoute(user: User | null, language: PixLanguage) {
  const [page, setPage] = useState<AppPage>(() => pageFromHash(null))

  const navigate = useCallback((nextPage: AppPage) => {
    window.location.hash = `/${nextPage}`
    setPage(nextPage)
  }, [])

  useEffect(() => {
    function syncHash() {
      setPage(pageFromHash(user))
    }
    window.addEventListener('hashchange', syncHash)
    syncHash()
    return () => window.removeEventListener('hashchange', syncHash)
  }, [user])

  useEffect(() => {
    applyPageSeo(page, language)
  }, [language, page])

  return { page, setPage, navigate }
}
