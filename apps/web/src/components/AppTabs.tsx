import { cn } from '../lib/utils'
import { useI18n } from '../i18n'
import type { User } from '../types'

export type AppPage = 'home' | 'workspace' | 'raw-image' | 'gallery' | 'packs' | 'billing' | 'admin'

type AppTab = { page: AppPage; labelKey: string; descriptionKey: string; adminOnly?: boolean }

const tabs: AppTab[] = [
  { page: 'workspace', labelKey: 'nav.workspace', descriptionKey: 'nav.workspaceDescription' },
  { page: 'raw-image', labelKey: 'nav.rawImage', descriptionKey: 'nav.rawImageDescription' },
  { page: 'gallery', labelKey: 'nav.gallery', descriptionKey: 'nav.galleryDescription' },
  { page: 'packs', labelKey: 'nav.packs', descriptionKey: 'nav.packsDescription' },
  { page: 'billing', labelKey: 'nav.billing', descriptionKey: 'nav.billingDescription' },
  { page: 'admin', labelKey: 'nav.admin', descriptionKey: 'nav.adminDescription', adminOnly: true },
]

interface AppTabsProps {
  page: AppPage
  user: User | null
  onChange: (page: AppPage) => void
  orientation?: 'top' | 'side'
}

export function AppTabs({ page, user, onChange, orientation = 'top' }: AppTabsProps) {
  const { t } = useI18n()
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.role === 'admin')

  if (orientation === 'side') {
    return (
      <nav aria-label={t('nav.workspaceNavigation')} className="grid gap-1">
        {visibleTabs.map((tab) => {
          const active = page === tab.page
          return (
            <button
              type="button"
              key={tab.page}
              aria-current={active ? 'page' : undefined}
              onClick={() => onChange(tab.page)}
              className={cn(
                'group rounded-md px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:focus-visible:ring-white/70',
                active
                  ? 'border border-border bg-card text-[hsl(var(--pix-ink))] shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-[hsl(var(--pix-brand-purple-300)/.28)] dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:ring-1 dark:ring-[hsl(var(--pix-brand-purple-300)/.18)]'
                  : 'text-[hsl(var(--pix-slate))] hover:bg-white/70 hover:text-[hsl(var(--pix-ink))] dark:text-white/62 dark:hover:bg-[hsl(var(--pix-dark-card-raised)/.72)] dark:hover:text-white',
              )}
            >
              <span className="block text-sm font-semibold leading-tight">{t(tab.labelKey)}</span>
              <span className={cn('mt-0.5 block text-[11px]', active ? 'text-[hsl(var(--pix-steel))] dark:text-white/58' : 'text-[hsl(var(--pix-muted))] group-hover:text-[hsl(var(--pix-steel))] dark:text-white/38 dark:group-hover:text-white/62')}>{t(tab.descriptionKey)}</span>
            </button>
          )
        })}
      </nav>
    )
  }

  return (
    <nav aria-label={t('nav.mainNavigation')} className="flex w-full gap-1 overflow-x-auto rounded-full border border-border bg-transparent p-1 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card)/.55)]">
      {visibleTabs.map((tab) => {
        const active = page === tab.page
        return (
          <button
            type="button"
            key={tab.page}
            aria-current={active ? 'page' : undefined}
            onClick={() => onChange(tab.page)}
            className={cn(
              'min-w-24 flex-1 rounded-full px-4 py-2 text-left text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-center',
              active && 'bg-[hsl(var(--pix-ink))] text-white dark:bg-[hsl(var(--pix-brand-purple))] dark:text-white',
            )}
          >
            <span className="block leading-tight">{t(tab.labelKey)}</span>
            <span className={cn('hidden text-[11px] text-muted-foreground lg:block', active && 'text-white/70')}>{t(tab.descriptionKey)}</span>
          </button>
        )
      })}
    </nav>
  )
}
