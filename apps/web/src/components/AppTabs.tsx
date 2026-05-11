import type { User } from '../types'

export type AppPage = 'workspace' | 'gallery' | 'packs' | 'billing' | 'admin'

const tabs: Array<{ page: AppPage; label: string; description: string; adminOnly?: boolean }> = [
  { page: 'workspace', label: '生产工作台', description: '单图与批量创建' },
  { page: 'gallery', label: '作品库', description: '查看结果与微调' },
  { page: 'packs', label: '素材包', description: '管理批量生产' },
  { page: 'billing', label: '点数中心', description: '充值与流水' },
  { page: 'admin', label: '管理后台', description: '运营与配置', adminOnly: true },
]

interface AppTabsProps {
  page: AppPage
  user: User | null
  onChange: (page: AppPage) => void
}

export function AppTabs({ page, user, onChange }: AppTabsProps) {
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.role === 'admin')
  return (
    <nav className="app-tabs" aria-label="主导航">
      {visibleTabs.map((tab) => (
        <button
          className={page === tab.page ? 'active' : ''}
          type="button"
          key={tab.page}
          aria-current={page === tab.page ? 'page' : undefined}
          onClick={() => onChange(tab.page)}
        >
          <strong>{tab.label}</strong>
          <span>{tab.description}</span>
        </button>
      ))}
    </nav>
  )
}
