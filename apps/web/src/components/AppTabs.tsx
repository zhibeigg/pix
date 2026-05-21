import { cn } from '../lib/utils'
import type { User } from '../types'

export type AppPage = 'workspace' | 'raw-image' | 'gallery' | 'packs' | 'billing' | 'admin'

const tabs: Array<{ page: AppPage; label: string; description: string; adminOnly?: boolean }> = [
  { page: 'workspace', label: '生产', description: '单图 / 批量' },
  { page: 'raw-image', label: '原始生图', description: '只出原图' },
  { page: 'gallery', label: '作品库', description: '查看与微调' },
  { page: 'packs', label: '素材包', description: '批量管理' },
  { page: 'billing', label: '点数', description: '充值流水' },
  { page: 'admin', label: '后台', description: '运营配置', adminOnly: true },
]

interface AppTabsProps {
  page: AppPage
  user: User | null
  onChange: (page: AppPage) => void
}

export function AppTabs({ page, user, onChange }: AppTabsProps) {
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.role === 'admin')
  return (
    <nav aria-label="主导航" className="flex w-full gap-1 overflow-x-auto rounded-2xl border border-border bg-muted/60 p-1">
      {visibleTabs.map((tab) => {
        const active = page === tab.page
        return (
          <button
            type="button"
            key={tab.page}
            aria-current={active ? 'page' : undefined}
            onClick={() => onChange(tab.page)}
            className={cn(
              'min-w-28 flex-1 rounded-xl px-3 py-2 text-left transition-all hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active && 'bg-card text-foreground shadow-sm',
            )}
          >
            <span className="block text-sm font-bold leading-tight">{tab.label}</span>
            <span className={cn('block text-[11px] text-muted-foreground', active && 'text-primary')}>{tab.description}</span>
          </button>
        )
      })}
    </nav>
  )
}
