import { cn } from '../lib/utils'
import { localText, useI18n } from '../i18n'
import type { User } from '../types'

export type AppPage = 'home' | 'workspace' | 'raw-image' | 'gallery' | 'packs' | 'billing' | 'admin'

type AppTab = { page: AppPage; label: { zh: string; en: string }; description: { zh: string; en: string }; adminOnly?: boolean }

const tabs: AppTab[] = [
  { page: 'workspace', label: { zh: '生产', en: 'Production' }, description: { zh: '单图 / 批量', en: 'Single / Batch' } },
  { page: 'raw-image', label: { zh: '原始生图', en: 'Raw Image' }, description: { zh: '只出原图', en: 'Source only' } },
  { page: 'gallery', label: { zh: '作品库', en: 'Gallery' }, description: { zh: '查看与微调', en: 'Review & Tune' } },
  { page: 'packs', label: { zh: '素材包', en: 'Packs' }, description: { zh: '批量管理', en: 'Batch manage' } },
  { page: 'billing', label: { zh: '点数', en: 'Billing' }, description: { zh: '充值流水', en: 'Credits & Orders' } },
  { page: 'admin', label: { zh: '后台', en: 'Admin' }, description: { zh: '运营配置', en: 'Operations' }, adminOnly: true },
]

interface AppTabsProps {
  page: AppPage
  user: User | null
  onChange: (page: AppPage) => void
  orientation?: 'top' | 'side'
}

export function AppTabs({ page, user, onChange, orientation = 'top' }: AppTabsProps) {
  const { language, text } = useI18n()
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.role === 'admin')

  if (orientation === 'side') {
    return (
      <nav aria-label={text('工作区导航', 'Workspace navigation')} className="grid gap-1">
        {visibleTabs.map((tab) => {
          const active = page === tab.page
          const label = localText(language, tab.label.zh, tab.label.en)
          const description = localText(language, tab.description.zh, tab.description.en)
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
              <span className="block text-sm font-semibold leading-tight">{label}</span>
              <span className={cn('mt-0.5 block text-[11px]', active ? 'text-[hsl(var(--pix-steel))] dark:text-white/58' : 'text-[hsl(var(--pix-muted))] group-hover:text-[hsl(var(--pix-steel))] dark:text-white/38 dark:group-hover:text-white/62')}>{description}</span>
            </button>
          )
        })}
      </nav>
    )
  }

  return (
    <nav aria-label={text('主导航', 'Main navigation')} className="flex w-full gap-1 overflow-x-auto rounded-full border border-border bg-transparent p-1 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card)/.55)]">
      {visibleTabs.map((tab) => {
        const active = page === tab.page
        const label = localText(language, tab.label.zh, tab.label.en)
        const description = localText(language, tab.description.zh, tab.description.en)
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
            <span className="block leading-tight">{label}</span>
            <span className={cn('hidden text-[11px] text-muted-foreground lg:block', active && 'text-white/70')}>{description}</span>
          </button>
        )
      })}
    </nav>
  )
}
