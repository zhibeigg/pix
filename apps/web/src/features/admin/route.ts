export const ADMIN_TABS = [
  'overview',
  'jobs',
  'shares',
  'users',
  'orders',
  'announcements',
  'pricing',
  'packages',
  'membership',
  'promo',
  'providers',
  'performance',
  'updates',
  'settings',
] as const

export type AdminTab = (typeof ADMIN_TABS)[number]

const ADMIN_TAB_SET = new Set<string>(ADMIN_TABS)

export function normalizeAdminTab(value: string | null | undefined): AdminTab {
  return value && ADMIN_TAB_SET.has(value) ? value as AdminTab : 'overview'
}

export function parseAdminHash(hash = typeof window === 'undefined' ? '#/admin' : window.location.hash) {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash
  const [path, query = ''] = raw.split('?', 2)
  const params = new URLSearchParams(query)
  return {
    path: path || '/admin',
    tab: normalizeAdminTab(params.get('tab')),
    params,
  }
}

export function buildAdminHash(tab: AdminTab, current?: URLSearchParams, patch: Record<string, string | null | undefined> = {}) {
  const params = new URLSearchParams(current)
  params.set('tab', tab)
  Object.entries(patch).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') params.delete(key)
    else params.set(key, value)
  })
  return `#/admin?${params.toString()}`
}

export function replaceAdminHash(tab: AdminTab, current?: URLSearchParams, patch: Record<string, string | null | undefined> = {}) {
  if (typeof window === 'undefined') return
  const next = buildAdminHash(tab, current, patch)
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${next}`)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}
