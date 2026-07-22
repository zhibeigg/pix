import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BadgeDollarSign, ChevronRight, CircleGauge, CreditCard, FileCheck2, Megaphone, PackageOpen, RefreshCw, ServerCog, Settings2, ShieldCheck, Sparkles, Tags, Users, Wrench } from 'lucide-react'
import { api } from '../../api'
import { useI18n } from '../../i18n'
import type { AdminUserCreatePayload, CreditPackage, GenerationJob, ImageProviderCreatePayload, ImageProviderUpdatePayload, MembershipPlan, PromoLinkPayload, SystemSetting } from '../../types'
import { Alert } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { AdminOrdersPanel } from '../../components/AdminOrdersPanel'
import { AdminSharesPanel } from '../../components/AdminSharesPanel'
import { PerformanceMonitorTab } from '../../components/PerformanceMonitorTab'
import { AdminCreditsPanel, AdminJobsPanel, AnnouncementEditor, EmailTestBox, MembershipPlanEditor, PackageEditor, PricingRow, PromoLinkManager, ProviderManager, SettingRow } from './LegacyPanels'
import { DashboardOverview } from './DashboardOverview'
import { dashboardRequestKey, dashboardRequestParams, parseDashboardQuery, writeDashboardQuery, type DashboardQueryState } from './dashboardQuery'
import { UpdatesPanel } from './UpdatesPanel'
import { buildAdminHash, normalizeAdminTab, parseAdminHash, type AdminTab } from './route'
import { useAdminResource } from './useAdminResource'

type NotifyVariant = 'info' | 'success' | 'error'
export type AdminConsoleProps = { token: string; onNotify?: (message: string, variant?: NotifyVariant) => void }

type NavItem = { tab: AdminTab; icon: typeof CircleGauge; labelKey: string }
type NavGroup = { labelKey: string; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  { labelKey: 'admin.groups.observability', items: [
    { tab: 'overview', icon: CircleGauge, labelKey: 'admin.tabs.overview' },
    { tab: 'jobs', icon: Activity, labelKey: 'admin.tabs.jobs' },
    { tab: 'performance', icon: Sparkles, labelKey: 'admin.tabs.performance' },
  ] },
  { labelKey: 'admin.groups.operations', items: [
    { tab: 'shares', icon: FileCheck2, labelKey: 'admin.tabs.shares' },
    { tab: 'users', icon: Users, labelKey: 'admin.tabs.users' },
    { tab: 'announcements', icon: Megaphone, labelKey: 'admin.tabs.announcements' },
  ] },
  { labelKey: 'admin.groups.commercial', items: [
    { tab: 'orders', icon: CreditCard, labelKey: 'admin.tabs.orders' },
    { tab: 'pricing', icon: BadgeDollarSign, labelKey: 'admin.tabs.pricing' },
    { tab: 'packages', icon: PackageOpen, labelKey: 'admin.tabs.packages' },
    { tab: 'membership', icon: ShieldCheck, labelKey: 'admin.tabs.membership' },
    { tab: 'promo', icon: Tags, labelKey: 'admin.tabs.promo' },
  ] },
  { labelKey: 'admin.groups.system', items: [
    { tab: 'providers', icon: ServerCog, labelKey: 'admin.tabs.providers' },
    { tab: 'settings', icon: Settings2, labelKey: 'admin.tabs.settings' },
    { tab: 'updates', icon: Wrench, labelKey: 'admin.tabs.updates' },
  ] },
]

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items)

export function AdminConsole({ token, onNotify }: AdminConsoleProps) {
  const { t } = useI18n()
  const initial = useMemo(() => parseAdminHash(), [])
  const [tab, setTab] = useState<AdminTab>(initial.tab)
  const [params, setParams] = useState(initial.params)

  useEffect(() => {
    const sync = () => {
      const next = parseAdminHash()
      setTab(next.tab)
      setParams(next.params)
      if (next.path === '/admin' && next.params.get('tab') !== next.tab) {
        window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${buildAdminHash(next.tab, next.params)}`)
      }
    }
    window.addEventListener('hashchange', sync)
    sync()
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  const notify = useCallback((key: string, variant: NotifyVariant = 'success') => onNotify?.(t(key), variant), [onNotify, t])
  const dashboardQuery = useMemo(() => parseDashboardQuery(params), [params])
  const dashboardKey = dashboardRequestKey(dashboardQuery)
  const loadDashboard = useCallback(() => api.adminDashboard(token, dashboardRequestParams(dashboardQuery)), [dashboardKey, token])
  const loadUpdateSummary = useCallback(() => api.adminUpdateStatus(token), [token])
  const loadUsers = useCallback(() => api.adminUsers(token), [token])
  const loadJobs = useCallback(() => api.adminJobs(token), [token])
  const loadPricing = useCallback(() => api.adminPricing(token), [token])
  const loadPackages = useCallback(() => api.adminPackages(token), [token])
  const loadMembership = useCallback(() => api.adminMembershipPlans(token), [token])
  const loadSettings = useCallback(() => api.adminSettings(token), [token])

  const dashboard = useAdminResource(tab === 'overview', loadDashboard)
  const updateSummary = useAdminResource(tab === 'overview', loadUpdateSummary)
  const users = useAdminResource(tab === 'users' || tab === 'jobs', loadUsers)
  const jobs = useAdminResource(tab === 'jobs', loadJobs)
  const pricing = useAdminResource(tab === 'pricing', loadPricing)
  const packages = useAdminResource(tab === 'packages', loadPackages)
  const membership = useAdminResource(tab === 'membership', loadMembership)
  const settings = useAdminResource(tab === 'settings', loadSettings)
  const dashboardKeyRef = useRef(dashboardKey)

  useEffect(() => {
    if (tab !== 'overview' || dashboardKeyRef.current === dashboardKey) return
    dashboardKeyRef.current = dashboardKey
    void dashboard.refresh()
  }, [dashboard.refresh, dashboardKey, tab])

  const refreshOverview = useCallback(
    () => refreshAdminOverview(dashboard.refresh, updateSummary.refresh),
    [dashboard.refresh, updateSummary.refresh],
  )

  useEffect(() => {
    if (tab !== 'overview') return
    const refreshVisible = () => {
      if (document.visibilityState === 'visible') void refreshOverview()
    }
    const timer = window.setInterval(refreshVisible, 30000)
    document.addEventListener('visibilitychange', refreshVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshVisible)
    }
  }, [refreshOverview, tab])

  const selectedNav = ALL_NAV_ITEMS.find((item) => item.tab === tab) ?? ALL_NAV_ITEMS[0]
  const refresh = currentRefresh(tab, refreshOverview, users.refresh, jobs.refresh, pricing.refresh, packages.refresh, membership.refresh, settings.refresh)
  const busy = tab === 'overview'
    ? dashboard.loading || dashboard.refreshing || updateSummary.loading || updateSummary.refreshing
    : currentBusy(tab, dashboard, users, jobs, pricing, packages, membership, settings)
  const error = tab === 'overview' && dashboard.data ? '' : currentError(tab, dashboard, users, jobs, pricing, packages, membership, settings)

  function navigate(nextTab: string, patch: Record<string, string | null> = {}) {
    const normalized = normalizeAdminTab(nextTab)
    const next = buildAdminHash(normalized, params, patch)
    window.location.hash = next.slice(1)
  }

  function updateDashboardQuery(nextQuery: DashboardQueryState) {
    const nextParams = writeDashboardQuery(params, nextQuery)
    window.location.hash = buildAdminHash('overview', nextParams).slice(1)
  }

  const groupedSettings = useMemo(() => groupSettings(settings.data ?? []), [settings.data])
  const settingCategories = Object.keys(groupedSettings)
  const requestedSection = params.get('section') || ''
  const settingSection = groupedSettings[requestedSection] ? requestedSection : settingCategories[0] || ''

  const createUser = async (payload: AdminUserCreatePayload) => {
    await api.createAdminUser(token, payload)
    await users.refresh()
    notify('admin.messages.userCreated')
  }
  const adjustSingle = async (userId: number, amount: number, note: string) => {
    await api.adjustCredits(token, userId, amount, note)
    await users.refresh()
    notify('admin.messages.creditsAdjusted')
  }
  const adjustBatch = async (payload: { userIds: number[]; allUsers: boolean; amount: number; note: string }) => {
    const result = await api.adjustCreditsBatch(token, { user_ids: payload.userIds, all_users: payload.allUsers, amount: payload.amount, note: payload.note })
    await users.refresh()
    notify('admin.messages.creditsAdjusted')
    return result
  }
  const retryJob = async (job: GenerationJob) => { await api.adminRetryJob(token, job.id); await jobs.refresh(); notify('admin.messages.jobRetried') }
  const cancelJob = async (job: GenerationJob) => { await api.adminCancelJob(token, job.id); await jobs.refresh(); notify('admin.messages.jobCancelled') }
  const refundJob = async (job: GenerationJob) => { await api.adminFailRefundJob(token, job.id); await jobs.refresh(); notify('admin.messages.jobRefunded') }
  const updatePricing = async (key: string, priceCredits: number, enabled: boolean) => { await api.updatePricing(token, key, priceCredits, enabled); await pricing.refresh(); notify('admin.messages.pricingUpdated') }
  const createPackage = async (payload: CreditPackage) => { await api.createAdminPackage(token, payload); await packages.refresh(); notify('admin.messages.packageCreated') }
  const updatePackage = async (key: string, payload: Omit<CreditPackage, 'key'>) => { await api.updateAdminPackage(token, key, payload); await packages.refresh(); notify('admin.messages.packageUpdated') }
  const createMembership = async (payload: MembershipPlan) => { await api.createAdminMembershipPlan(token, payload); await membership.refresh(); notify('admin.messages.membershipCreated') }
  const updateMembership = async (key: string, payload: Omit<MembershipPlan, 'key'>) => { await api.updateAdminMembershipPlan(token, key, payload); await membership.refresh(); notify('admin.messages.membershipUpdated') }
  const updateSetting = async (key: string, value: string, clear = false) => { await api.updateSetting(token, key, value, clear); await settings.refresh(); notify('admin.messages.settingUpdated') }
  const testEmail = async (email: string) => { const result = await api.testEmailSetting(token, email); onNotify?.(result.debug_code ? `${result.message}: ${result.debug_code}` : result.message, 'info') }

  return (
    <div data-admin-density="compact" className="admin-console grid min-w-0 gap-4 lg:grid-cols-[216px_minmax(0,1fr)]">
      <aside className="hidden self-start rounded-lg border border-border bg-card p-2 lg:sticky lg:top-20 lg:block" aria-label={t('admin.navigation')}>
        {NAV_GROUPS.map((group) => <div key={group.labelKey} className="mb-3 last:mb-0"><p className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground">{t(group.labelKey)}</p><div className="grid gap-0.5">{group.items.map((item) => <AdminNavButton key={item.tab} item={item} active={tab === item.tab} onSelect={() => navigate(item.tab)} />)}</div></div>)}
      </aside>

      <div className="min-w-0">
        <div className="mb-3 grid gap-3 rounded-lg border border-border bg-card p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground">{t('admin.consoleEyebrow')}</p><h1 className="truncate text-xl font-semibold">{t(selectedNav.labelKey)}</h1></div>
          <div className="flex gap-2">
            <Select value={tab} onValueChange={(value) => navigate(value)}><SelectTrigger className="min-w-0 flex-1 lg:hidden"><SelectValue /></SelectTrigger><SelectContent>{NAV_GROUPS.map((group) => group.items.map((item) => <SelectItem key={item.tab} value={item.tab}>{t(item.labelKey)}</SelectItem>))}</SelectContent></Select>
            {refresh && <Button type="button" variant="outline" size="sm" onClick={() => void refresh()} disabled={busy}><RefreshCw className={busy ? 'animate-spin' : ''} />{t('admin.common.refresh')}</Button>}
          </div>
        </div>

        {error && <Alert variant="destructive">{error}</Alert>}
        <div className="mt-3 min-w-0 rounded-lg border border-border bg-background p-3 sm:p-4">
          {tab === 'overview' && <ResourceBody state={dashboard}>{dashboard.data && <div className="grid gap-4"><DashboardOverview dashboard={dashboard.data} query={dashboardQuery} refreshing={dashboard.refreshing} error={dashboard.error} onQueryChange={updateDashboardQuery} onRetry={() => void dashboard.refresh()} /><section className="grid gap-3 rounded-lg border border-border bg-card p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{t('admin.updates.title')}</h2>{updateSummary.data && <Badge variant={updateSummary.data.update_available ? 'warning' : 'success'}>{updateSummary.data.update_available ? t('admin.updates.available') : t('admin.updates.upToDate')}</Badge>}</div><p className="mt-1 text-sm text-muted-foreground">{updateSummary.loading ? t('admin.common.loading') : updateSummary.error || updateSummary.data?.error || `${t('admin.updates.currentVersion')}: ${updateSummary.data?.current_version || '—'} · ${t('admin.updates.latestVersion')}: ${updateSummary.data?.latest_release?.version || '—'}`}</p></div><Button type="button" variant="outline" size="sm" onClick={() => navigate('updates')}>{t('admin.tabs.updates')}<ChevronRight className="h-3.5 w-3.5" /></Button></section></div>}</ResourceBody>}
          {tab === 'jobs' && <ResourceBody state={jobs}>{jobs.data && users.data && <AdminJobsPanel jobs={jobs.data} users={users.data} onRetry={retryJob} onCancel={cancelJob} onFailRefund={refundJob} />}</ResourceBody>}
          {tab === 'shares' && <AdminSharesPanel token={token} />}
          {tab === 'users' && <ResourceBody state={users}>{users.data && <AdminCreditsPanel users={users.data} onCreateUser={createUser} onAdjustSingle={adjustSingle} onAdjustBatch={adjustBatch} />}</ResourceBody>}
          {tab === 'orders' && <AdminOrdersPanel token={token} />}
          {tab === 'announcements' && <AnnouncementEditor onPublish={(payload) => api.publishAnnouncement(token, payload)} onTestEmail={testEmail} onListAnnouncements={() => api.adminAnnouncements(token)} onCreateAnnouncement={(payload) => api.createAnnouncement(token, payload)} onUpdateAnnouncement={(id, payload) => api.updateAnnouncement(token, id, payload)} onDeleteAnnouncement={(id) => api.deleteAnnouncement(token, id)} onTestAnnouncementEmail={(email, title, body) => api.testAnnouncementEmail(token, { email, title, body })} />}
          {tab === 'pricing' && <ResourceBody state={pricing}><div className="grid gap-3">{pricing.data?.map((rule) => <PricingRow rule={rule} onUpdate={updatePricing} key={rule.key} />)}</div></ResourceBody>}
          {tab === 'packages' && <ResourceBody state={packages}>{packages.data && <PackageEditor packages={packages.data} onCreate={createPackage} onUpdate={updatePackage} />}</ResourceBody>}
          {tab === 'membership' && <ResourceBody state={membership}>{membership.data && <MembershipPlanEditor plans={membership.data} onCreate={createMembership} onUpdate={updateMembership} />}</ResourceBody>}
          {tab === 'promo' && <PromoLinkManager onList={() => api.adminPromoLinks(token)} onCreate={(payload: PromoLinkPayload) => api.createAdminPromoLink(token, payload).then(() => undefined)} onUpdate={(id, payload) => api.updateAdminPromoLink(token, id, payload).then(() => undefined)} onDelete={(id) => api.deleteAdminPromoLink(token, id).then(() => undefined)} />}
          {tab === 'providers' && <ProviderManager onList={() => api.adminProviders(token)} onListPresets={() => api.adminProviderPresets(token)} onCreate={(payload: ImageProviderCreatePayload) => api.createAdminProvider(token, payload).then(() => undefined)} onUpdate={(id: string, payload: ImageProviderUpdatePayload) => api.updateAdminProvider(token, id, payload).then(() => undefined)} onDelete={(id: string) => api.deleteAdminProvider(token, id).then(() => undefined)} />}
          {tab === 'performance' && <PerformanceMonitorTab token={token} />}
          {tab === 'updates' && <UpdatesPanel token={token} />}
          {tab === 'settings' && <ResourceBody state={settings}><div className="grid gap-4 xl:grid-cols-[190px_minmax(0,1fr)]"><nav className="grid content-start gap-1" aria-label={t('admin.settings.categories')}>{settingCategories.map((category) => <button key={category} type="button" className={`flex items-center justify-between rounded-md px-3 py-2 text-left text-sm ${settingSection === category ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`} onClick={() => navigate('settings', { section: category })}><span className="truncate">{category}</span><ChevronRight className="h-3.5 w-3.5" /></button>)}</nav><div className="grid min-w-0 gap-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">{settingSection || t('admin.settings.empty')}</h2><p className="text-xs text-muted-foreground">{t('admin.settings.description')}</p></div>{settingSection === '邮件验证码' && <EmailTestBox onTest={testEmail} />}</div>{(groupedSettings[settingSection] ?? []).map((setting) => <SettingRow key={setting.key} setting={setting} onUpdate={updateSetting} />)}</div></div></ResourceBody>}
        </div>
      </div>
    </div>
  )
}

function AdminNavButton({ item, active, onSelect }: { item: NavItem; active: boolean; onSelect: () => void }) {
  const { t } = useI18n()
  const Icon = item.icon
  return <button type="button" aria-current={active ? 'page' : undefined} className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm ${active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`} onClick={onSelect}><Icon className="h-4 w-4" /><span>{t(item.labelKey)}</span></button>
}

function ResourceBody<T>({ state, children }: { state: { data: T | null; loading: boolean; error: string }; children: React.ReactNode }) {
  const { t } = useI18n()
  if (state.loading && !state.data) return <Alert variant="info">{t('admin.common.loading')}</Alert>
  if (state.error && !state.data) return <Alert variant="destructive">{state.error}</Alert>
  return <>{children}</>
}

function groupSettings(settings: SystemSetting[]) {
  return settings.reduce<Record<string, SystemSetting[]>>((groups, setting) => {
    const category = setting.category || 'Other'
    ;(groups[category] ||= []).push(setting)
    return groups
  }, {})
}

export async function refreshAdminOverview(
  dashboard: () => Promise<void>,
  updateSummary: () => Promise<void>,
) {
  await Promise.all([dashboard(), updateSummary()])
}

function currentRefresh(tab: AdminTab, dashboard: () => Promise<void>, users: () => Promise<void>, jobs: () => Promise<void>, pricing: () => Promise<void>, packages: () => Promise<void>, membership: () => Promise<void>, settings: () => Promise<void>) {
  if (tab === 'overview') return dashboard
  if (tab === 'users') return users
  if (tab === 'jobs') return async () => { await Promise.all([users(), jobs()]) }
  if (tab === 'pricing') return pricing
  if (tab === 'packages') return packages
  if (tab === 'membership') return membership
  if (tab === 'settings') return settings
  return null
}

function currentBusy(tab: AdminTab, ...states: Array<{ loading: boolean; refreshing: boolean }>) {
  const indexes: Partial<Record<AdminTab, number[]>> = { overview: [0], users: [1], jobs: [1, 2], pricing: [3], packages: [4], membership: [5], settings: [6] }
  return (indexes[tab] ?? []).some((index) => states[index].loading || states[index].refreshing)
}

function currentError(tab: AdminTab, ...states: Array<{ error: string }>) {
  const indexes: Partial<Record<AdminTab, number[]>> = { overview: [0], users: [1], jobs: [1, 2], pricing: [3], packages: [4], membership: [5], settings: [6] }
  return (indexes[tab] ?? []).map((index) => states[index].error).find(Boolean) || ''
}
