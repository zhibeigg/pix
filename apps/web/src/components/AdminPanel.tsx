import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { AdminBatchAdjustCreditsResponse, AdminDashboard, AnnouncementItem, AnnouncementListResponse, AnnouncementPublishPayload, AnnouncementPublishResponse, CreditPackage, GenerationJob, MembershipPlan, PricingRule, SystemSetting, User, ImageProvider, ImageProviderPreset, ImageProviderCreatePayload, ImageProviderUpdatePayload, ImageProviderModelPayload } from '../types'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Input } from './ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { Tabs, TabsList, TabsTrigger } from './ui/tabs'
import { PixField } from './pix/PixField'
import { PixMetric } from './pix/PixMetric'
import { PixPanel } from './pix/PixPanel'
import { api } from '../api'
import { PerformanceMonitorTab } from './PerformanceMonitorTab'
import { AdminSharesPanel } from './AdminSharesPanel'
import { AdminOrdersPanel } from './AdminOrdersPanel'
import { GalleryGrid } from './GalleryGrid'
import { useConfirm } from './ConfirmDialog'

type Props = { dashboard: AdminDashboard | null; users: User[]; jobs: GenerationJob[]; pricing: PricingRule[]; packages: CreditPackage[]; membershipPlans: MembershipPlan[]; settings: SystemSetting[]; onRefresh: () => void; onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>; onAdjustCreditsBatch: (payload: { userIds: number[]; allUsers: boolean; amount: number; note: string }) => Promise<AdminBatchAdjustCreditsResponse | void>; onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>; onCreatePackage: (payload: CreditPackage) => Promise<void>; onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>; onCreateMembershipPlan: (payload: MembershipPlan) => Promise<void>; onUpdateMembershipPlan: (key: string, payload: Omit<MembershipPlan, 'key'>) => Promise<void>; onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>; onPublishAnnouncement: (payload: AnnouncementPublishPayload) => Promise<AnnouncementPublishResponse>; onTestEmail: (email: string) => Promise<void>; onAdminRetryJob: (job: GenerationJob) => Promise<void>; onAdminCancelJob: (job: GenerationJob) => Promise<void>; onAdminFailRefundJob: (job: GenerationJob) => Promise<void>; onAdminAnnouncements?: () => Promise<AnnouncementListResponse>; onCreateAnnouncement?: (payload: { title: string; body: string; enabled: boolean; publish_now: boolean; notify: boolean }) => Promise<AnnouncementItem>; onUpdateAnnouncement?: (id: number, payload: { title?: string; body?: string; enabled?: boolean }) => Promise<AnnouncementItem>; onDeleteAnnouncement?: (id: number) => Promise<{ deleted: boolean }>; onTestAnnouncementEmail?: (email: string, title: string, body: string) => Promise<{ message: string }>; onListProviders?: () => Promise<ImageProvider[]>; onListProviderPresets?: () => Promise<ImageProviderPreset[]>; onCreateProvider?: (payload: ImageProviderCreatePayload) => Promise<void>; onUpdateProvider?: (id: string, payload: ImageProviderUpdatePayload) => Promise<void>; onDeleteProvider?: (id: string) => Promise<void>; token: string }
const settingTabs = ['价格折扣', '运营保护', '邮件验证码', '模型与 API', '素材默认值', '序列帧', '支付与站点', '存储 / 队列 / 安全']

export function AdminPanel({ dashboard, users, jobs, pricing, packages, membershipPlans, settings, onRefresh, onAdjustCredits, onAdjustCreditsBatch, onUpdatePricing, onCreatePackage, onUpdatePackage, onCreateMembershipPlan, onUpdateMembershipPlan, onUpdateSetting, onPublishAnnouncement, onTestEmail, onAdminRetryJob, onAdminCancelJob, onAdminFailRefundJob, onAdminAnnouncements, onCreateAnnouncement, onUpdateAnnouncement, onDeleteAnnouncement, onTestAnnouncementEmail, onListProviders, onListProviderPresets, onCreateProvider, onUpdateProvider, onDeleteProvider, token }: Props) {
  const [tab, setTab] = useState('dashboard')
  const groups = useMemo(() => groupSettings(settings), [settings])
  const settingGroup = groups[tab]
  // 概览自动刷新：在「概览」标签页时每 30s 拉取一次最新统计，解决「不是实时」。
  useEffect(() => {
    if (tab !== 'dashboard') return
    const id = window.setInterval(() => { onRefresh() }, 30000)
    return () => window.clearInterval(id)
  }, [tab, onRefresh])
  return (
    <PixPanel eyebrow="Control Room" title="管理后台" description="配置站点、模型、邮件、套餐和运营保护。高风险环境项只显示状态。" action={<Button variant="outline" onClick={onRefresh}>刷新</Button>}>
      <div className="grid gap-6">
        <Tabs value={tab} onValueChange={setTab}><TabsList className="h-auto flex-wrap justify-start"><TabsTrigger value="dashboard">概览</TabsTrigger><TabsTrigger value="jobs">任务与作品</TabsTrigger><TabsTrigger value="shares">内容审核</TabsTrigger><TabsTrigger value="users">用户与点数</TabsTrigger><TabsTrigger value="orders">订单</TabsTrigger><TabsTrigger value="announcements">系统公告</TabsTrigger><TabsTrigger value="pricing">价格规则</TabsTrigger><TabsTrigger value="packages">充值套餐</TabsTrigger><TabsTrigger value="membership">月卡档位</TabsTrigger><TabsTrigger value="providers">上游供应商</TabsTrigger><TabsTrigger value="performance">性能监控</TabsTrigger>{settingTabs.map((item) => <TabsTrigger key={item} value={item}>{item}</TabsTrigger>)}</TabsList></Tabs>
        {tab === 'dashboard' && dashboard && <DashboardGrid dashboard={dashboard} />}
        {tab === 'jobs' && <AdminJobsPanel jobs={jobs} users={users} onRetry={onAdminRetryJob} onCancel={onAdminCancelJob} onFailRefund={onAdminFailRefundJob} />}
        {tab === 'shares' && <AdminSharesPanel token={token} onRefresh={onRefresh} />}
        {tab === 'users' && <AdminCreditsPanel users={users} onAdjustSingle={onAdjustCredits} onAdjustBatch={onAdjustCreditsBatch} />}
        {tab === 'orders' && <AdminOrdersPanel token={token} />}
        {tab === 'announcements' && <AnnouncementEditor onPublish={onPublishAnnouncement} onTestEmail={onTestEmail} onListAnnouncements={onAdminAnnouncements} onCreateAnnouncement={onCreateAnnouncement} onUpdateAnnouncement={onUpdateAnnouncement} onDeleteAnnouncement={onDeleteAnnouncement} onTestAnnouncementEmail={onTestAnnouncementEmail} />}
        {tab === 'pricing' && <div className="grid gap-3"><h3 className="text-lg font-semibold">价格规则</h3>{pricing.map((rule) => <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />)}</div>}
        {tab === 'packages' && <PackageEditor packages={packages} onCreate={onCreatePackage} onUpdate={onUpdatePackage} />}
        {tab === 'membership' && <MembershipPlanEditor plans={membershipPlans} onCreate={onCreateMembershipPlan} onUpdate={onUpdateMembershipPlan} />}
        {tab === 'providers' && <ProviderManager onList={onListProviders} onListPresets={onListProviderPresets} onCreate={onCreateProvider} onUpdate={onUpdateProvider} onDelete={onDeleteProvider} />}
        {tab === 'performance' && <PerformanceMonitorTab token={token} />}
        {settingGroup && <div className="grid gap-3"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">{tab}</h3><p className="text-sm text-muted-foreground">保存后只影响新请求/新任务；带"需重启"的项目请重启服务或 worker。</p></div>{tab === '邮件验证码' && <EmailTestBox onTest={onTestEmail} />}</div>{settingGroup.map((setting) => <SettingRow setting={setting} onUpdate={onUpdateSetting} key={setting.key} />)}</div>}
      </div>
    </PixPanel>
  )
}

function groupSettings(settings: SystemSetting[]) { return settings.reduce<Record<string, SystemSetting[]>>((acc, setting) => { const category = setting.category || '其他'; acc[category] = acc[category] || []; acc[category].push(setting); return acc }, {}) }

type UserSortKey = 'available_credits' | 'total_consumed' | 'total_recharged' | 'created_at'
const USER_SORT_OPTIONS: { value: UserSortKey; label: string }[] = [
  { value: 'created_at', label: '按注册时间' },
  { value: 'available_credits', label: '按剩余点数' },
  { value: 'total_consumed', label: '按已消耗' },
  { value: 'total_recharged', label: '按已充值' },
]

function AdminCreditsPanel({ users, onAdjustSingle, onAdjustBatch }: { users: User[]; onAdjustSingle: (userId: number, amount: number, note: string) => Promise<void>; onAdjustBatch: (payload: { userIds: number[]; allUsers: boolean; amount: number; note: string }) => Promise<AdminBatchAdjustCreditsResponse | void> }) {
  const confirm = useConfirm()
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [allUsers, setAllUsers] = useState(false)
  const [amount, setAmount] = useState(100)
  const [note, setNote] = useState('运营补点')
  const [quickUser, setQuickUser] = useState('0')
  const [submitting, setSubmitting] = useState(false)
  const [resultText, setResultText] = useState('')
  const [userQuery, setUserQuery] = useState('')
  const [userSortKey, setUserSortKey] = useState<UserSortKey>('created_at')
  const [userSortDir, setUserSortDir] = useState<'asc' | 'desc'>('desc')

  const visibleUsers = useMemo(() => {
    const keyword = userQuery.trim().toLowerCase()
    const rows = users.filter((user) => {
      if (!keyword) return true
      return `${user.email} ${user.display_name} #${user.id}`.toLowerCase().includes(keyword)
    })
    const dir = userSortDir === 'asc' ? 1 : -1
    return rows.slice().sort((a, b) => {
      if (userSortKey === 'created_at') return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * dir
      return ((a[userSortKey] ?? 0) - (b[userSortKey] ?? 0)) * dir
    })
  }, [users, userQuery, userSortKey, userSortDir])

  const pageUserIds = visibleUsers.map((user) => user.id)
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])
  const allPageSelected = pageUserIds.length > 0 && pageUserIds.every((id) => selectedSet.has(id))
  const targetCountLabel = allUsers ? '全部活跃用户' : `${selectedIds.length} 个已选用户`
  const canSubmit = amount !== 0 && (allUsers || selectedIds.length > 0) && !submitting

  function toggleUser(userId: number, checked: boolean) {
    setAllUsers(false)
    setSelectedIds((current) => checked ? Array.from(new Set([...current, userId])) : current.filter((id) => id !== userId))
  }

  function toggleAllPage(checked: boolean) {
    setAllUsers(false)
    setSelectedIds(checked ? pageUserIds : [])
  }

  function applyQuickUser(value: string) {
    setQuickUser(value)
    const userId = Number(value)
    if (userId > 0) {
      setAllUsers(false)
      setSelectedIds([userId])
    }
  }

  async function submitBatch(event: FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    const targetText = allUsers ? '全部活跃用户' : `${selectedIds.length} 个用户`
    const sign = amount > 0 ? '+' : ''
    if (!(await confirm({ title: '批量调整点数', description: `确认给 ${targetText} 调整 ${sign}${amount} 点？`, confirmText: '确认调整', tone: 'danger', impactItems: [allUsers ? '影响全部活跃用户' : `影响 ${selectedIds.length} 个用户`, `每人 ${sign}${amount} 点`] }))) return
    setSubmitting(true)
    setResultText('')
    try {
      if (!allUsers && selectedIds.length === 1) {
        await onAdjustSingle(selectedIds[0], amount, note)
        setResultText(`已为 1 个用户调整 ${sign}${amount} 点。`)
      } else {
        const result = await onAdjustBatch({ userIds: selectedIds, allUsers, amount, note })
        const count = result?.adjusted_count ?? (allUsers ? 0 : selectedIds.length)
        setResultText(`已为 ${count} 个用户调整 ${sign}${amount} 点。`)
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]" onSubmit={submitBatch}>
      <div className="grid gap-4 rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">用户与点数</h3>
            <p className="text-sm text-muted-foreground">查看每个用户的剩余点数 / 已充值 / 已消耗与会员状态；选择用户后可统一调整点数。</p>
          </div>
          <Badge variant={allUsers || selectedIds.length > 0 ? 'info' : 'outline'}>{targetCountLabel}</Badge>
        </div>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]">
          <div className="relative">
            <Input value={userQuery} onChange={(event) => setUserQuery(event.target.value)} placeholder="搜索邮箱 / 昵称 / #ID" className="pl-3" />
          </div>
          <Select value={userSortKey} onValueChange={(value) => setUserSortKey(value as UserSortKey)}>
            <SelectTrigger className="min-w-[140px]"><SelectValue /></SelectTrigger>
            <SelectContent>{USER_SORT_OPTIONS.map((item) => <SelectItem value={item.value} key={item.value}>{item.label}</SelectItem>)}</SelectContent>
          </Select>
          <Button type="button" variant="outline" onClick={() => setUserSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))}>{userSortDir === 'asc' ? '升序 ↑' : '降序 ↓'}</Button>
          <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
            <Checkbox checked={allPageSelected} onCheckedChange={(value) => toggleAllPage(Boolean(value))} />
            全选当前
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <PixField label="快速选择单人">
            <Select value={quickUser} onValueChange={applyQuickUser}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="0">选择用户</SelectItem>{users.map((u) => <SelectItem value={String(u.id)} key={u.id}>{u.email} · {u.role}</SelectItem>)}</SelectContent>
            </Select>
          </PixField>
          <label className="flex items-center gap-2 self-end rounded-lg border border-border px-3 py-2 text-sm">
            <Checkbox checked={allUsers} onCheckedChange={(value) => { const checked = Boolean(value); setAllUsers(checked); if (checked) setSelectedIds([]) }} />
            全部活跃用户
          </label>
          <Badge variant="outline" className="self-end">{visibleUsers.length} / {users.length} 个用户</Badge>
        </div>
        <div className="max-h-[420px] overflow-auto rounded-xl border border-border">
          {visibleUsers.length === 0 ? <p className="p-4 text-sm text-muted-foreground">{users.length === 0 ? '暂无用户。' : '没有匹配的用户。'}</p> : visibleUsers.map((user) => {
            const selected = selectedSet.has(user.id)
            const membershipActive = user.membership_plan_key && user.membership_status === 'active'
            return (
              <label key={user.id} className={`grid cursor-pointer gap-2 border-b border-border px-4 py-3 last:border-b-0 sm:grid-cols-[auto_minmax(0,1fr)_auto_auto] sm:items-center ${selected ? 'bg-primary/10' : 'bg-card'}`}>
                <Checkbox checked={selected} onCheckedChange={(value) => toggleUser(user.id, Boolean(value))} />
                <span className="min-w-0">
                  <span className="block truncate font-medium">{user.display_name || user.email}</span>
                  <span className="block truncate text-xs text-muted-foreground">#{user.id} · {user.email}</span>
                </span>
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground sm:justify-end">
                  <span title="可用点数">剩余 <strong className="text-foreground">{user.available_credits ?? 0}</strong></span>
                  <span title="累计充值">充 {user.total_recharged ?? 0}</span>
                  <span title="累计消耗">耗 {user.total_consumed ?? 0}</span>
                  {membershipActive && <Badge variant="info">月卡·{user.membership_plan_key}</Badge>}
                </span>
                <Badge variant={user.role === 'admin' ? 'default' : user.status === 'active' ? 'secondary' : 'outline'}>{user.role} · {user.status}</Badge>
              </label>
            )
          })}
        </div>
      </div>
      <div className="grid content-start gap-4 rounded-xl border border-border bg-muted/40 p-4">
        <PixField label="点数变化"><Input type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} /></PixField>
        <PixField label="备注"><Input value={note} onChange={(event) => setNote(event.target.value)} /></PixField>
        <div className="rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">发送摘要</p>
          <p className="mt-1">对象：{targetCountLabel}</p>
          <p>每人：{amount > 0 ? '+' : ''}{amount} 点</p>
          <p className="truncate">备注：{note || '管理员批量调整点数'}</p>
        </div>
        <Button type="submit" disabled={!canSubmit}>{submitting ? '调整中…' : '批量调整点数'}</Button>
        {resultText && <Alert variant="success">{resultText}</Alert>}
      </div>
    </form>
  )
}

function DashboardGrid({ dashboard }: { dashboard: AdminDashboard }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <PixMetric label="今日任务" value={dashboard.jobs_today} tone="info" />
      <PixMetric label="成功 / 失败" value={`${dashboard.succeeded_today} / ${dashboard.failed_today}`} tone={dashboard.failed_today > 0 ? 'danger' : 'success'} />
      <PixMetric label="今日新增用户" value={dashboard.new_users_today} tone="info" />
      <PixMetric label="DAU" value={dashboard.active_users_today} tone="info" />
      <PixMetric label="今日付费用户" value={dashboard.paying_users_today} tone={dashboard.paying_users_today > 0 ? 'success' : 'default'} />
      <PixMetric label="订单充值" value={dashboard.credits_recharged_today} tone="success" />
      <PixMetric label="今日新订单" value={dashboard.orders_created_today ?? 0} tone="info" />
      <PixMetric label="付费订单" value={dashboard.orders_paid_today} tone={dashboard.orders_paid_today > 0 ? 'success' : 'default'} />
      <PixMetric label="今日消费" value={dashboard.credits_consumed_today} tone="warning" />
      <PixMetric label="今日上传" value={dashboard.uploads_today} />
      <PixMetric label="总用户" value={dashboard.total_users} />
      <PixMetric label="策略拦截" value={dashboard.policy_blocked_today} tone={dashboard.policy_blocked_today > 0 ? 'warning' : 'success'} />
      <PixMetric label="上游 / 超时" value={`${dashboard.upstream_errors_today} / ${dashboard.timeout_jobs_today}`} tone={(dashboard.upstream_errors_today + dashboard.timeout_jobs_today) > 0 ? 'danger' : 'success'} />
      <PixMetric label="Pipeline 异常" value={dashboard.pipeline_errors_today} tone={dashboard.pipeline_errors_today > 0 ? 'danger' : 'success'} />
      <PixMetric label="排队 / 运行" value={`${dashboard.pending_jobs} / ${dashboard.running_jobs}`} tone="info" />
      <PixMetric label="运行超 30 分钟" value={dashboard.running_over_30m_jobs} tone={dashboard.running_over_30m_jobs > 0 ? 'warning' : 'success'} />
      <PixMetric label="候选失败 / 警告" value={`${dashboard.candidate_failures_today} / ${dashboard.pipeline_warnings_today}`} tone={(dashboard.candidate_failures_today + dashboard.pipeline_warnings_today) > 0 ? 'warning' : 'success'} />
      <PixMetric label="平均耗时" value={`${Math.round(dashboard.average_generation_seconds_today)}s`} />
      <PixMetric label="P95 耗时" value={`${Math.round(dashboard.p95_generation_seconds_today)}s`} />
      <PixMetric label="失败率" value={`${Math.round(dashboard.failure_rate * 100)}%`} tone={dashboard.failure_rate > 0.1 ? 'danger' : 'success'} />
    </div>
  )
}

type AdminJobView = 'gallery' | 'operations'
type AdminJobStatusFilter = 'all' | 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'

function AdminJobsPanel({ jobs, users, onRetry, onCancel, onFailRefund }: { jobs: GenerationJob[]; users: User[]; onRetry: (job: GenerationJob) => Promise<void>; onCancel: (job: GenerationJob) => Promise<void>; onFailRefund: (job: GenerationJob) => Promise<void> }) {
  const [view, setView] = useState<AdminJobView>('gallery')
  const [status, setStatus] = useState<AdminJobStatusFilter>('all')
  const [userId, setUserId] = useState('all')
  const [query, setQuery] = useState('')
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const usersById = useMemo(() => new Map(users.map((user) => [user.id, user])), [users])
  const filteredJobs = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    const targetUserId = userId === 'all' ? null : Number(userId)
    return jobs.filter((job) => {
      if (status !== 'all' && job.status !== status) return false
      if (targetUserId && job.user_id !== targetUserId) return false
      if (!normalized) return true
      const owner = usersById.get(job.user_id)
      const haystack = [String(job.id), `#${job.id}`, job.job_type, job.status, job.prompt ?? '', job.batch_name ?? '', owner?.email ?? '', owner?.display_name ?? ''].join(' ').toLowerCase()
      return haystack.includes(normalized)
    })
  }, [jobs, query, status, userId, usersById])
  const statusSummary = useMemo(() => ({
    total: filteredJobs.length,
    active: filteredJobs.filter((job) => ['pending', 'running', 'waiting'].includes(job.status)).length,
    succeeded: filteredJobs.filter((job) => job.status === 'succeeded').length,
    failed: filteredJobs.filter((job) => job.status === 'failed').length,
  }), [filteredJobs])
  const renderOwnerBadge = (job: GenerationJob) => {
    const owner = usersById.get(job.user_id)
    const label = owner ? (owner.display_name || owner.email) : `用户 #${job.user_id}`
    return <Badge variant="outline" className="max-w-[180px] truncate" title={owner?.email ?? label}>{label}</Badge>
  }

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 rounded-xl border border-border bg-muted/35 p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">任务与作品</h3>
            <p className="text-sm text-muted-foreground">显示最新 500 个任务。作品视图可像用户作品库一样快速预览产物；操作列表保留退款与重试。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info">{statusSummary.total} 个匹配</Badge>
            <Badge variant={statusSummary.active > 0 ? 'warning' : 'outline'}>活跃 {statusSummary.active}</Badge>
            <Badge variant="success">完成 {statusSummary.succeeded}</Badge>
            <Badge variant={statusSummary.failed > 0 ? 'danger' : 'outline'}>失败 {statusSummary.failed}</Badge>
          </div>
        </div>
        <div className="grid gap-3 lg:grid-cols-[180px_220px_minmax(220px,1fr)_auto]">
          <PixField label="状态">
            <Select value={status} onValueChange={(value) => setStatus(value as AdminJobStatusFilter)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">全部状态</SelectItem><SelectItem value="pending">排队中</SelectItem><SelectItem value="running">生产中</SelectItem><SelectItem value="succeeded">已完成</SelectItem><SelectItem value="failed">失败</SelectItem><SelectItem value="cancelled">已取消</SelectItem></SelectContent>
            </Select>
          </PixField>
          <PixField label="用户">
            <Select value={userId} onValueChange={setUserId}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">全部用户</SelectItem>{users.map((user) => <SelectItem value={String(user.id)} key={user.id}>{user.display_name || user.email}</SelectItem>)}</SelectContent>
            </Select>
          </PixField>
          <PixField label="搜索">
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="任务 ID、prompt、批次或用户邮箱" />
          </PixField>
          <div className="grid content-end">
            <Button type="button" variant="outline" onClick={() => { setStatus('all'); setUserId('all'); setQuery(''); setSelectedJobId(null) }}>重置筛选</Button>
          </div>
        </div>
        <Tabs value={view} onValueChange={(value) => setView(value as AdminJobView)}>
          <TabsList className="h-auto flex-wrap justify-start"><TabsTrigger value="gallery">作品视图</TabsTrigger><TabsTrigger value="operations">操作列表</TabsTrigger></TabsList>
        </Tabs>
      </div>
      {view === 'gallery' ? (
        filteredJobs.length === 0
          ? <Alert variant="info">没有符合筛选条件的任务。</Alert>
          : <GalleryGrid jobs={filteredJobs} selectedJobId={selectedJobId} subtitle="全站任务产物预览；管理员使用当前登录凭证访问受保护文件。" showRetentionQuota={false} onSelect={(job) => setSelectedJobId(job.id)} renderJobBadges={renderOwnerBadge} />
      ) : <AdminJobsList jobs={filteredJobs} usersById={usersById} onRetry={onRetry} onCancel={onCancel} onFailRefund={onFailRefund} />}
    </div>
  )
}

function AdminJobsList({ jobs, usersById, onRetry, onCancel, onFailRefund }: { jobs: GenerationJob[]; usersById: Map<number, User>; onRetry: (job: GenerationJob) => Promise<void>; onCancel: (job: GenerationJob) => Promise<void>; onFailRefund: (job: GenerationJob) => Promise<void> }) {
  const confirm = useConfirm()
  if (!jobs.length) return <Alert variant="info">没有符合筛选条件的任务。</Alert>
  return (
    <div className="grid gap-3">
      <div><h3 className="text-lg font-semibold">任务操作</h3><p className="text-sm text-muted-foreground">当前显示筛选后的任务；可重试失败任务，或取消/标记失败并退款排队中与运行中任务。</p></div>
      {jobs.map((job) => {
        const owner = usersById.get(job.user_id)
        const ownerLabel = owner ? `${owner.display_name || owner.email} · #${owner.id}` : `用户 #${job.user_id}`
        return (
          <div key={job.id} className="grid gap-3 rounded-lg border border-border bg-card p-4 xl:grid-cols-[minmax(0,1fr)_auto]">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2"><p className="font-semibold">#{job.id} · {job.job_type}</p><Badge variant={job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'danger' : job.status === 'running' ? 'warning' : job.status === 'cancelled' ? 'muted' : 'info'}>{job.status}</Badge><Badge variant="outline" title={owner?.email ?? ownerLabel}>{ownerLabel}</Badge>{job.failure_type && <Badge variant="outline">{job.failure_type}</Badge>}{job.failure_source && <Badge variant="outline">{job.failure_source}</Badge>}{job.failure_code && <Badge variant="outline">{job.failure_code}</Badge>}</div>
              <p className="mt-1 truncate text-sm text-muted-foreground">{job.prompt || '无 prompt'} · {formatDateTime(job.created_at)} · 运行 {formatRuntime(job)}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>点数 {job.price_credits}</span><span>冻结 {job.reserved_credits}</span><span>候选失败 {job.candidate_failure_count}</span><span>流水线警告 {job.pipeline_warning_count}</span></div>
              {job.status === 'failed' && <AdminJobDiagnostics job={job} />}
            </div>
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              {job.status === 'failed' && <Button variant="outline" size="sm" onClick={async () => { if (await confirm({ title: '重试任务', description: `重试任务 #${job.id}？`, confirmText: '重试' })) void onRetry(job) }}>重试</Button>}
              {['pending', 'running', 'waiting'].includes(job.status) && <Button variant="outline" size="sm" onClick={async () => { if (await confirm({ title: '取消并退款', description: `取消任务 #${job.id} 并退款？`, confirmText: '取消并退款', tone: 'danger' })) void onCancel(job) }}>取消并退款</Button>}
              {['pending', 'running', 'failed'].includes(job.status) && <Button variant="destructive" size="sm" onClick={async () => { if (await confirm({ title: '标记失败并退款', description: `将任务 #${job.id} 标记为失败并退款？`, confirmText: '失败并退款', tone: 'danger' })) void onFailRefund(job) }}>失败并退款</Button>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

const DIAGNOSTIC_PREVIEW_LIMIT = 1800
const DIAGNOSTIC_ERROR_PREVIEW_LIMIT = 1200

function AdminJobDiagnostics({ job }: { job: GenerationJob }) {
  const [expanded, setExpanded] = useState(false)
  const [renderDetails, setRenderDetails] = useState(false)
  const [copied, setCopied] = useState('')
  const diagnostics = asRecord(job.error_diagnostics_json)
  const failure = asRecord(diagnostics?.failure)
  const exception = asRecord(diagnostics?.exception)
  const providerAttempts = Array.isArray(diagnostics?.provider_attempts) ? diagnostics.provider_attempts : []
  const failureType = toSummaryText(failure?.type)
  const failureSource = toSummaryText(failure?.source)
  const failureCode = toSummaryText(failure?.code)
  const exceptionType = toSummaryText(exception?.type)
  const userMessage = job.user_error_message || '—'
  const detailPreview = renderDetails ? truncateForPreview(job.error_message || '', DIAGNOSTIC_ERROR_PREVIEW_LIMIT) : ''
  const diagnosticSummary = renderDetails && diagnostics ? buildDiagnosticSummary(diagnostics) : ''

  useEffect(() => {
    if (!expanded) {
      setRenderDetails(false)
      return
    }
    const frame = window.requestAnimationFrame(() => setRenderDetails(true))
    return () => window.cancelAnimationFrame(frame)
  }, [expanded])

  const copyPayload = async (label: string, value: string) => {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopied(label)
    } catch {
      setCopied('复制失败')
    }
    window.setTimeout(() => setCopied(''), 1400)
  }

  const copyDiagnostics = async () => {
    if (!diagnostics) return
    await copyPayload('诊断 JSON', JSON.stringify(diagnostics, null, 2))
  }

  return (
    <div className="mt-2 grid gap-2 text-sm">
      <p className="text-destructive">{job.error_message ? job.error_message.slice(0, 220) : userMessage}</p>
      <div className="rounded-md border border-border bg-muted/30 text-xs">
        <button
          type="button"
          aria-expanded={expanded}
          className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left font-semibold"
          onClick={() => setExpanded((value) => !value)}
        >
          <span aria-hidden>{expanded ? '▼' : '▶'}</span>
          <span>诊断详情</span>
        </button>
        {expanded && (
          <div className="grid gap-2 border-t border-border px-3 py-2">
            {!renderDetails ? <p className="text-muted-foreground">正在加载诊断摘要…</p> : (
              <>
                <p><span className="font-semibold">用户提示：</span>{userMessage}</p>
                <div className="flex flex-wrap gap-2 text-muted-foreground">
                  {failureType && <span>类型：{failureType}</span>}
                  {failureSource && <span>来源：{failureSource}</span>}
                  {failureCode && <span>代码：{failureCode}</span>}
                  {exceptionType && <span>异常：{exceptionType}</span>}
                  {providerAttempts.length > 0 && <span>Provider 尝试：{providerAttempts.length}</span>}
                </div>
                <div className="flex flex-wrap gap-2">
                  {diagnostics && <Button type="button" variant="outline" size="sm" onClick={() => { void copyDiagnostics() }}>复制完整诊断 JSON</Button>}
                  {job.error_message && <Button type="button" variant="outline" size="sm" onClick={() => { void copyPayload('详细错误', job.error_message) }}>复制详细错误</Button>}
                  {copied && <span className="self-center text-xs text-muted-foreground">已复制：{copied}</span>}
                </div>
                {diagnosticSummary && <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-card p-2 font-mono text-[11px] leading-5 text-muted-foreground">{diagnosticSummary}</pre>}
                {detailPreview && <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-card p-2 font-mono text-[11px] leading-5 text-muted-foreground">{detailPreview}</pre>}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function buildDiagnosticSummary(diagnostics: Record<string, unknown>) {
  const lines: string[] = []
  const keys = Object.keys(diagnostics)
  if (keys.length) lines.push(`字段：${keys.slice(0, 18).join(', ')}${keys.length > 18 ? ` …共 ${keys.length} 项` : ''}`)

  const failure = asRecord(diagnostics.failure)
  if (failure) {
    lines.push(`failure: type=${toSummaryText(failure.type) || '—'} source=${toSummaryText(failure.source) || '—'} code=${toSummaryText(failure.code) || '—'}`)
  }

  const exception = asRecord(diagnostics.exception)
  if (exception) {
    const message = compactPreviewText(exception.message ?? exception.detail ?? exception.traceback, 360)
    lines.push(`exception: ${toSummaryText(exception.type) || '—'}${message ? ` · ${message}` : ''}`)
  }

  appendAttemptSummary(lines, 'provider_attempts', diagnostics.provider_attempts)
  appendAttemptSummary(lines, 'provider_history', diagnostics.provider_history)

  if (!lines.length) return '没有可展示的轻量摘要。完整内容请使用复制按钮。'
  lines.push('')
  lines.push('为避免展开时卡顿，此处只展示轻量摘要；完整诊断请点击“复制完整诊断 JSON”。')
  return truncateForPreview(lines.join('\n'), DIAGNOSTIC_PREVIEW_LIMIT)
}

function appendAttemptSummary(lines: string[], label: string, value: unknown) {
  if (!Array.isArray(value) || value.length === 0) return
  lines.push(`${label}: ${value.length} 条`)
  value.slice(0, 4).forEach((item, index) => {
    const record = asRecord(item)
    if (!record) {
      lines.push(`  #${index + 1}: ${compactPreviewText(item, 260)}`)
      return
    }
    const provider = toSummaryText(record.provider ?? record.provider_id ?? record.alias ?? record.name)
    const status = toSummaryText(record.status ?? record.error_type ?? record.type)
    const code = toSummaryText(record.code ?? record.status_code ?? record.http_status)
    const message = compactPreviewText(record.message ?? record.error ?? record.detail ?? record.response, 220)
    lines.push(`  #${index + 1}: ${[provider, status, code].filter(Boolean).join(' · ') || '—'}${message ? ` · ${message}` : ''}`)
  })
  if (value.length > 4) lines.push(`  …还有 ${value.length - 4} 条未预览`)
}

function compactPreviewText(value: unknown, limit: number) {
  if (value === null || value === undefined) return ''
  const text = typeof value === 'string'
    ? value
    : Array.isArray(value)
      ? `[array length=${value.length}]`
      : typeof value === 'object'
        ? `[object keys=${Object.keys(value as Record<string, unknown>).slice(0, 8).join(', ')}]`
        : String(value)
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function toSummaryText(value: unknown) {
  if (value === null || value === undefined) return ''
  return String(value)
}

function truncateForPreview(value: string, limit: number) {
  if (!value) return ''
  return value.length <= limit ? value : `${value.slice(0, limit)}\n…已截断预览，完整内容请使用复制按钮。`
}

function formatRuntime(job: GenerationJob) {
  if (!job.started_at) return '—'
  const start = new Date(job.started_at).getTime()
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '—'
  const seconds = Math.round((end - start) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes}m ${rest}s`
}

function formatDateTime(value: string) {
  try { return new Date(value).toLocaleString() } catch { return value }
}

function EmailTestBox({ onTest }: { onTest: (email: string) => Promise<void> }) { const [email, setEmail] = useState('admin@example.com'); return <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void onTest(email) }}><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /><Button type="submit" variant="outline">发送测试</Button></form> }

function AnnouncementEditor({ onPublish, onTestEmail, onListAnnouncements, onCreateAnnouncement, onUpdateAnnouncement, onDeleteAnnouncement, onTestAnnouncementEmail }: { onPublish: (payload: AnnouncementPublishPayload) => Promise<AnnouncementPublishResponse>; onTestEmail: (email: string) => Promise<void>; onListAnnouncements?: () => Promise<AnnouncementListResponse>; onCreateAnnouncement?: (payload: { title: string; body: string; enabled: boolean; publish_now: boolean; notify: boolean }) => Promise<AnnouncementItem>; onUpdateAnnouncement?: (id: number, payload: { title?: string; body?: string; enabled?: boolean }) => Promise<AnnouncementItem>; onDeleteAnnouncement?: (id: number) => Promise<{ deleted: boolean }>; onTestAnnouncementEmail?: (email: string, title: string, body: string) => Promise<{ message: string }> }) {
  const confirm = useConfirm()
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([])
  const [listLoading, setListLoading] = useState(false)
  const [listRefreshing, setListRefreshing] = useState(false)
  const listLoadedRef = useRef(false)
  const listRequestIdRef = useRef(0)
  const [editing, setEditing] = useState<AnnouncementItem | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [notify, setNotify] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [noticeVariant, setNoticeVariant] = useState<'info' | 'success' | 'warning'>('info')
  const [testEmail, setTestEmail] = useState('admin@example.com')
  const [testSending, setTestSending] = useState(false)
  const [announcementTestEmail, setAnnouncementTestEmail] = useState('')
  const [announcementTestSending, setAnnouncementTestSending] = useState(false)
  const [announcementTestNotice, setAnnouncementTestNotice] = useState('')
  const [previewTab, setPreviewTab] = useState<'announcement' | 'verification'>('announcement')

  const loadList = useCallback(async () => {
    if (!onListAnnouncements) return
    const requestId = listRequestIdRef.current + 1
    listRequestIdRef.current = requestId
    const showBlockingLoading = !listLoadedRef.current
    if (showBlockingLoading) setListLoading(true)
    else setListRefreshing(true)
    try {
      const res = await onListAnnouncements()
      if (listRequestIdRef.current !== requestId) return
      setAnnouncements(res.items)
      listLoadedRef.current = true
    } catch {
      // 保留已有列表，避免短暂网络抖动让公告界面闪烁或清空。
    } finally {
      if (listRequestIdRef.current === requestId) {
        setListLoading(false)
        setListRefreshing(false)
      }
    }
  }, [onListAnnouncements])

  useEffect(() => { void loadList() }, [loadList])

  function startCreate() {
    setEditing(null)
    setTitle('')
    setBody('')
    setEnabled(true)
    setNotify(true)
    setShowCreate(true)
    setNotice('')
  }

  function startEdit(item: AnnouncementItem) {
    setEditing(item)
    setTitle(item.title)
    setBody(item.body)
    setEnabled(item.enabled)
    setNotify(true)
    setShowCreate(true)
    setNotice('')
  }

  function cancelForm() {
    setShowCreate(false)
    setEditing(null)
    setTitle('')
    setBody('')
    setEnabled(true)
    setNotify(true)
    setNotice('')
  }

  async function save(publishNow: boolean) {
    setSaving(true)
    setNotice('')
    try {
      if (editing && onUpdateAnnouncement) {
        await onUpdateAnnouncement(editing.id, { title, body, enabled })
        setNotice(publishNow ? '公告已更新并发送通知。' : '公告已更新。')
        setNoticeVariant('success')
      } else if (onCreateAnnouncement) {
        await onCreateAnnouncement({ title, body, enabled, publish_now: publishNow, notify })
        setNotice(publishNow ? '公告已发布并发送通知。' : '公告已保存为草稿。')
        setNoticeVariant(publishNow ? 'success' : 'info')
      } else if (onPublish) {
        const result = await onPublish({ title, body, enabled })
        setNotice(announcementPublishNotice(result))
        setNoticeVariant(result.email_notification_queued ? 'success' : result.email_skipped_reason === 'unchanged' ? 'info' : 'warning')
      }
      setShowCreate(false)
      setEditing(null)
      setTitle('')
      setBody('')
      setEnabled(true)
      setNotify(true)
      void loadList()
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存失败，请重试'
      setNotice(message)
      setNoticeVariant('warning')
    } finally {
      setSaving(false)
    }
  }

  async function toggleEnabled(item: AnnouncementItem) {
    if (!onUpdateAnnouncement) return
    try {
      await onUpdateAnnouncement(item.id, { enabled: !item.enabled })
      void loadList()
    } catch { /* ignore */ }
  }

  async function removeItem(item: AnnouncementItem) {
    if (!onDeleteAnnouncement) return
    if (!(await confirm({ title: '删除公告', description: `确定删除公告「${item.title || '无标题'}」？`, confirmText: '删除', tone: 'danger' }))) return
    try {
      await onDeleteAnnouncement(item.id)
      void loadList()
    } catch { /* ignore */ }
  }

  async function sendTest() {
    setTestSending(true)
    try {
      await onTestEmail(testEmail)
    } finally {
      setTestSending(false)
    }
  }

  async function sendAnnouncementTest() {
    if (!onTestAnnouncementEmail || !announcementTestEmail.trim()) return
    setAnnouncementTestSending(true)
    setAnnouncementTestNotice('')
    try {
      const result = await onTestAnnouncementEmail(announcementTestEmail, title, body)
      setAnnouncementTestNotice(result.message || '测试邮件已发送')
    } catch (error) {
      const message = error instanceof Error ? error.message : '发送失败'
      setAnnouncementTestNotice(message)
    } finally {
      setAnnouncementTestSending(false)
    }
  }

  function statusBadge(item: AnnouncementItem) {
    if (!item.enabled) return <Badge variant="muted">已下线</Badge>
    if (item.published_at) return <Badge variant="success">已发布</Badge>
    return <Badge variant="info">草稿</Badge>
  }

  function renderBodyPreview(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return '公告正文会显示在这里。'
    return trimmed.split('\n').map((line, i) => <span key={i}>{i > 0 && <br />}{line}</span>)
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="grid gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">系统公告</h3>
              <p className="mt-1 text-sm text-muted-foreground">发布后会显示在顶部铃铛弹窗中；新内容上线时会向所有活跃用户邮箱发送通知。</p>
            </div>
            {!showCreate && <Button type="button" onClick={startCreate}>新建公告</Button>}
          </div>
        </div>

        {showCreate && (
          <form className="grid gap-4 rounded-lg border border-border bg-card p-4" onSubmit={(event) => { event.preventDefault(); void save(true) }}>
            <PixField label="公告标题"><Input value={title} maxLength={80} placeholder="例如：维护通知 / 新功能上线" onChange={(event) => setTitle(event.target.value)} /></PixField>
            <PixField label="公告正文"><Textarea value={body} rows={6} maxLength={2000} placeholder="写清楚影响范围、时间和用户需要做什么。" onChange={(event) => setBody(event.target.value)} /></PixField>
            <label className="flex items-center gap-2 text-sm"><Checkbox checked={enabled} onCheckedChange={(value) => setEnabled(Boolean(value))} />启用公告</label>
            <label className="flex items-center gap-2 text-sm"><Checkbox checked={notify} onCheckedChange={(value) => setNotify(Boolean(value))} />发送邮箱通知</label>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={saving || (!title.trim() && !body.trim())}>{saving ? '保存中…' : editing ? (notify ? '更新并通知' : '更新') : (notify ? '发布并通知' : '发布')}</Button>
              {!editing && <Button type="button" variant="soft" disabled={saving} onClick={() => void save(false)}>保存草稿</Button>}
              <Button type="button" variant="outline" disabled={saving} onClick={cancelForm}>取消</Button>
            </div>
            {notice && <Alert variant={noticeVariant}>{notice}</Alert>}
          </form>
        )}

        <div className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <p className="text-sm font-semibold">公告列表</p>
            {listRefreshing && <span className="text-xs text-muted-foreground">刷新中…</span>}
          </div>
          {listLoading ? (
            <div className="grid place-items-center py-8 text-sm text-muted-foreground">加载中…</div>
          ) : announcements.length === 0 ? (
            <div className="grid place-items-center py-8 text-sm text-muted-foreground">暂无公告</div>
          ) : (
            <div className="divide-y divide-border">
              {announcements.map((item) => (
                <div key={item.id} className="flex items-start gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold">{item.title || '无标题'}</span>
                      {statusBadge(item)}
                    </div>
                    {item.body && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.body}</p>}
                    {item.published_at && <p className="mt-1 text-xs text-muted-foreground">发布于 {new Date(item.published_at).toLocaleString()}</p>}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button type="button" variant="ghost" size="sm" onClick={() => startEdit(item)}>编辑</Button>
                    <Button type="button" variant="ghost" size="sm" onClick={() => void toggleEnabled(item)}>{item.enabled ? '下线' : '上线'}</Button>
                    <Button type="button" variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => void removeItem(item)}>删除</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-4">
        <div className="rounded-lg border border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper-soft))] p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">邮件预览</p>
            <div className="flex rounded-full border border-border bg-card p-0.5 text-xs">
              <button type="button" className={`rounded-full px-3 py-1 font-semibold transition ${previewTab === 'announcement' ? 'bg-slate-950 text-white' : 'text-muted-foreground hover:text-foreground'}`} onClick={() => setPreviewTab('announcement')}>公告卡片</button>
              <button type="button" className={`rounded-full px-3 py-1 font-semibold transition ${previewTab === 'verification' ? 'bg-slate-950 text-white' : 'text-muted-foreground hover:text-foreground'}`} onClick={() => setPreviewTab('verification')}>验证码卡片</button>
            </div>
          </div>
          {/* 邮件卡片预览：以下刻意使用硬编码颜色（hex / 裸 Tailwind 调色板）以 1:1 还原真实邮件 HTML 的渲染效果，
              不接入前端 design token 与暗色主题；修改时请与后端邮件模板保持一致，勿替换为 token。 */}
          {previewTab === 'announcement' ? (
            <div className="mt-3 overflow-hidden rounded-2xl border border-border bg-card shadow-[0_18px_44px_-28px_rgba(15,15,15,0.42)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
              <div className="bg-gradient-to-br from-slate-950 to-slate-700 p-4 text-white">
                <p className="text-[10px] font-semibold uppercase tracking-[1px] text-white/60">Pix Announcement</p>
                <h4 className="mt-2 text-base font-semibold">{title.trim() || '公告标题预览'}</h4>
              </div>
              <div className="p-4">
                <div className="whitespace-pre-wrap rounded-xl bg-muted/50 p-3 text-sm leading-6 text-muted-foreground">{renderBodyPreview(body)}</div>
                <div className="mt-4 inline-flex rounded-full bg-slate-950 px-4 py-2 text-xs font-semibold text-white">打开 Pix 网站</div>
                <div className="mt-4"><Badge variant={enabled ? 'success' : 'muted'}>{enabled ? '当前启用' : '当前下线'}</Badge></div>
              </div>
            </div>
          ) : (
            <div className="mt-3 overflow-hidden rounded-2xl border border-border bg-card shadow-[0_18px_44px_-28px_rgba(15,15,15,0.42)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
              <div className="bg-[#121826] p-4 text-white">
                <div className="mb-3 inline-block rounded-xl border border-white/20 bg-white/10 p-2">
                  <div className="grid grid-cols-3 gap-1">
                    {['#a78bfa','#facc15','#67e8f9','#86efac','#fb7185','#f97316','#fde68a','#c4b5fd','#99f6e4'].map((c) => (
                      <div key={c} className="h-2.5 w-2.5 rounded" style={{ backgroundColor: c }} />
                    ))}
                  </div>
                </div>
                <p className="text-[10px] font-semibold uppercase tracking-[1px] text-indigo-200">Pix Forge</p>
                <h4 className="mt-2 text-base font-semibold">你的注册通行名片</h4>
                <p className="mt-1 text-xs text-indigo-200/80">这组验证码会帮你完成注册。</p>
              </div>
              <div className="p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[1px] text-muted-foreground">Verification Code</p>
                <p className="mt-1 text-sm font-semibold">输入这组验证码完成注册</p>
                <div className="mt-3 rounded-2xl bg-[#f7f0e4] p-3 text-center">
                  <div className="flex justify-center gap-1.5">
                    {'123456'.split('').map((d, i) => (
                      <div key={i} className="flex h-10 w-9 items-center justify-center rounded-xl border border-[#d9cdbb] bg-[#fffdf7] text-lg font-extrabold shadow-sm">{d}</div>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-[#7a7165]">验证码：<span className="font-semibold tracking-wider text-foreground">123456</span></p>
                </div>
                <div className="mt-3 flex gap-1.5">
                  <span className="rounded-xl border border-blue-200 bg-blue-50 px-2.5 py-1.5 text-[11px] font-semibold text-blue-700">仅用于注册</span>
                  <span className="rounded-xl border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] font-semibold text-amber-700">不要转发</span>
                  <span className="rounded-xl border border-purple-200 bg-purple-50 px-2.5 py-1.5 text-[11px] font-semibold text-purple-700">一次验证</span>
                </div>
                <div className="mt-3 inline-flex rounded-full bg-slate-950 px-4 py-2 text-xs font-semibold text-white">回到 Pix</div>
              </div>
            </div>
          )}
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm font-semibold">发送公告测试邮件</p>
          <p className="mt-1 text-xs text-muted-foreground">输入邮箱地址，发送当前编辑中的公告内容到指定邮箱，检查邮件卡片效果。</p>
          <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); void sendAnnouncementTest() }}>
            <Input type="email" placeholder="your@email.com" value={announcementTestEmail} onChange={(e) => setAnnouncementTestEmail(e.target.value)} />
            <Button type="submit" variant="outline" disabled={announcementTestSending || !announcementTestEmail.trim()}>{announcementTestSending ? '发送中…' : '发送测试'}</Button>
          </form>
          {announcementTestNotice && <p className="mt-2 text-xs text-muted-foreground">{announcementTestNotice}</p>}
        </div>
      </div>
    </div>
  )
}

function announcementPublishNotice(result: AnnouncementPublishResponse) {
  if (result.email_notification_queued) return `公告已发布，正在向 ${result.email_recipient_count} 个邮箱发送通知。`
  if (result.email_skipped_reason === 'unchanged') return '公告已保存；内容未变化，不重复发送邮件。'
  if (result.email_skipped_reason === 'no_recipients') return '公告已发布，但暂无可通知的活跃用户邮箱。'
  if (result.email_skipped_reason === 'smtp_not_configured') return '公告已发布，但 SMTP 未配置，邮件未发送。请先在「邮件验证码」标签中配置 SMTP。'
  if (result.email_skipped_reason === 'disabled') return '公告已保存为草稿或已下线，未发送邮件。'
  return '公告已保存。'
}

const PROVIDER_CUSTOM_PRESET = '__custom__'

function ProviderManager({ onList, onListPresets, onCreate, onUpdate, onDelete }: { onList?: () => Promise<ImageProvider[]>; onListPresets?: () => Promise<ImageProviderPreset[]>; onCreate?: (payload: ImageProviderCreatePayload) => Promise<void>; onUpdate?: (id: string, payload: ImageProviderUpdatePayload) => Promise<void>; onDelete?: (id: string) => Promise<void> }) {
  const confirm = useConfirm()
  const [providers, setProviders] = useState<ImageProvider[]>([])
  const [presets, setPresets] = useState<ImageProviderPreset[]>([])
  const [listLoading, setListLoading] = useState(false)
  const [listRefreshing, setListRefreshing] = useState(false)
  const listLoadedRef = useRef(false)
  const listRequestIdRef = useRef(0)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ImageProvider | null>(null)
  const [id, setId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiKeyEnv, setApiKeyEnv] = useState('')
  const [priority, setPriority] = useState(100)
  const [enabled, setEnabled] = useState(true)
  const [discoverModels, setDiscoverModels] = useState(false)
  const [protocols, setProtocols] = useState<string[]>([])
  const [modelsText, setModelsText] = useState('[]')
  const [clearKey, setClearKey] = useState(false)
  const [presetKey, setPresetKey] = useState(PROVIDER_CUSTOM_PRESET)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [noticeVariant, setNoticeVariant] = useState<'info' | 'success' | 'warning'>('info')

  const loadList = useCallback(async () => {
    if (!onList) return
    const requestId = listRequestIdRef.current + 1
    listRequestIdRef.current = requestId
    const showBlockingLoading = !listLoadedRef.current
    if (showBlockingLoading) setListLoading(true)
    else setListRefreshing(true)
    try {
      const res = await onList()
      if (listRequestIdRef.current !== requestId) return
      setProviders(res)
      listLoadedRef.current = true
      if (onListPresets) {
        try {
          const presetRes = await onListPresets()
          if (listRequestIdRef.current === requestId) setPresets(presetRes)
        } catch {
          // 预设拉取失败时保留已有预设，不阻塞供应商列表展示。
        }
      }
    } catch {
      // 保留已有列表，避免短暂网络抖动让供应商界面闪烁或清空。
    } finally {
      if (listRequestIdRef.current === requestId) {
        setListLoading(false)
        setListRefreshing(false)
      }
    }
  }, [onList, onListPresets])

  useEffect(() => { void loadList() }, [loadList])

  function resetForm() {
    setEditing(null)
    setId('')
    setDisplayName('')
    setBaseUrl('')
    setApiKey('')
    setApiKeyEnv('')
    setPriority(100)
    setEnabled(true)
    setDiscoverModels(false)
    setProtocols([])
    setModelsText('[]')
    setClearKey(false)
    setPresetKey(PROVIDER_CUSTOM_PRESET)
    setNotice('')
  }

  function startCreate() {
    resetForm()
    setShowForm(true)
  }

  function applyPreset(value: string) {
    setPresetKey(value)
    if (value === PROVIDER_CUSTOM_PRESET) {
      setId('')
      setDisplayName('')
      setBaseUrl('')
      setApiKeyEnv('')
      setProtocols([])
      setDiscoverModels(false)
      setModelsText('[]')
      return
    }
    const preset = presets.find((item) => item.key === value)
    if (!preset) return
    setId(preset.key)
    setDisplayName(preset.display_name)
    setBaseUrl(preset.base_url)
    setApiKeyEnv(preset.api_key_env)
    setProtocols(preset.protocols)
    setDiscoverModels(preset.discover_models)
    setModelsText(JSON.stringify(preset.models, null, 2))
  }

  function startEdit(item: ImageProvider) {
    setEditing(item)
    setId(item.id)
    setDisplayName(item.display_name)
    setBaseUrl(item.base_url)
    setApiKey('')
    setApiKeyEnv(item.api_key_env)
    setPriority(item.priority)
    setEnabled(item.enabled)
    setDiscoverModels(item.discover_models)
    setProtocols(item.protocols)
    setModelsText(JSON.stringify(item.models, null, 2))
    setClearKey(false)
    setPresetKey(item.preset_key ?? PROVIDER_CUSTOM_PRESET)
    setNotice('')
    setShowForm(true)
  }

  function cancelForm() {
    setShowForm(false)
    resetForm()
  }

  async function save() {
    let models: ImageProviderModelPayload[]
    try {
      const parsed = JSON.parse(modelsText)
      if (!Array.isArray(parsed)) throw new Error('not array')
      models = parsed as ImageProviderModelPayload[]
    } catch {
      setNotice('模型 JSON 格式不正确')
      setNoticeVariant('warning')
      return
    }
    setSaving(true)
    setNotice('')
    try {
      if (editing && onUpdate) {
        await onUpdate(editing.id, { display_name: displayName, enabled, base_url: baseUrl, api_key: apiKey, clear_api_key: clearKey, api_key_env: apiKeyEnv, priority, discover_models: discoverModels, protocols, models })
      } else if (onCreate) {
        await onCreate({ id, display_name: displayName, enabled, base_url: baseUrl, api_key: apiKey, api_key_env: apiKeyEnv, priority, discover_models: discoverModels, protocols, models, preset_key: presetKey === PROVIDER_CUSTOM_PRESET ? null : presetKey })
      }
      await loadList()
      setShowForm(false)
      resetForm()
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存失败，请重试'
      setNotice(message)
      setNoticeVariant('warning')
    } finally {
      setSaving(false)
    }
  }

  async function toggleEnabled(item: ImageProvider) {
    if (!onUpdate) return
    try {
      await onUpdate(item.id, { display_name: item.display_name, enabled: !item.enabled, base_url: item.base_url, api_key: '', clear_api_key: false, api_key_env: item.api_key_env, priority: item.priority, discover_models: item.discover_models, protocols: item.protocols, models: item.models })
      void loadList()
    } catch { /* ignore */ }
  }

  async function removeItem(item: ImageProvider) {
    if (!onDelete) return
    if (!(await confirm({ title: '删除供应商', description: `确定删除供应商「${item.display_name || item.id}」？`, confirmText: '删除', tone: 'danger' }))) return
    try {
      await onDelete(item.id)
      void loadList()
    } catch { /* ignore */ }
  }

  return (
    <div className="grid gap-4">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">上游供应商</h3>
            <p className="mt-1 text-sm text-muted-foreground">管理生图上游供应商：从预设快速创建，或手动配置接入地址、协议与模型。密钥写入后只展示状态，不回显明文。</p>
          </div>
          {!showForm && <Button type="button" onClick={startCreate}>新增供应商</Button>}
        </div>
      </div>

      {showForm && (
        <form className="grid gap-4 rounded-lg border border-border bg-card p-4" onSubmit={(event) => { event.preventDefault(); void save() }}>
          {!editing && (
            <PixField label="预设模板">
              <Select value={presetKey} onValueChange={applyPreset}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={PROVIDER_CUSTOM_PRESET}>自定义（手动填写）</SelectItem>
                  {presets.map((preset) => <SelectItem key={preset.key} value={preset.key}>{preset.display_name}</SelectItem>)}
                </SelectContent>
              </Select>
            </PixField>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            <PixField label="供应商 ID"><Input value={id} disabled={Boolean(editing)} placeholder="例如：openai" onChange={(event) => setId(event.target.value)} /></PixField>
            <PixField label="显示名称"><Input value={displayName} placeholder="例如：OpenAI" onChange={(event) => setDisplayName(event.target.value)} /></PixField>
            <PixField label="接入地址 Base URL"><Input value={baseUrl} placeholder="https://api.example.com/v1" onChange={(event) => setBaseUrl(event.target.value)} /></PixField>
            <PixField label="密钥环境变量"><Input value={apiKeyEnv} placeholder="例如：OPENAI_API_KEY" onChange={(event) => setApiKeyEnv(event.target.value)} /></PixField>
            <PixField label="协议（逗号分隔）"><Input value={protocols.join(', ')} placeholder="例如：openai, responses" onChange={(event) => setProtocols(event.target.value.split(',').map((part) => part.trim()).filter(Boolean))} /></PixField>
            <PixField label="优先级"><Input type="number" value={priority} onChange={(event) => setPriority(Number(event.target.value))} /></PixField>
          </div>
          <PixField label={editing ? `API 密钥（当前${editing.has_api_key ? '已配置' : '未配置'}，留空保持不变）` : 'API 密钥'}>
            <Input type="password" value={apiKey} disabled={clearKey} placeholder={editing ? '留空保持当前密钥' : '可留空，改用环境变量'} onChange={(event) => setApiKey(event.target.value)} />
          </PixField>
          {editing && <label className="flex items-center gap-2 text-xs text-muted-foreground"><Checkbox checked={clearKey} onCheckedChange={(value) => setClearKey(Boolean(value))} />清空当前值</label>}
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={enabled} onCheckedChange={(value) => setEnabled(Boolean(value))} />启用供应商</label>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={discoverModels} onCheckedChange={(value) => setDiscoverModels(Boolean(value))} />自动发现模型</label>
          <PixField label="模型配置（JSON 数组）"><Textarea value={modelsText} rows={10} className="font-mono text-xs" placeholder='[{"id":"...","provider_model":"...","label":"...","protocol":"...","operations":[],"sizes":[],"qualities":[],"output_formats":[],"edit_mode":""}]' onChange={(event) => setModelsText(event.target.value)} /></PixField>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={saving || !displayName.trim() || (!editing && !id.trim())}>{saving ? '保存中…' : editing ? '保存修改' : '新增供应商'}</Button>
            <Button type="button" variant="outline" disabled={saving} onClick={cancelForm}>取消</Button>
          </div>
          {notice && <Alert variant={noticeVariant}>{notice}</Alert>}
        </form>
      )}

      <div className="rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <p className="text-sm font-semibold">供应商列表</p>
          {listRefreshing && <span className="text-xs text-muted-foreground">刷新中…</span>}
        </div>
        {listLoading ? (
          <div className="grid place-items-center py-8 text-sm text-muted-foreground">加载中…</div>
        ) : providers.length === 0 ? (
          <div className="grid place-items-center py-8 text-sm text-muted-foreground">暂无供应商</div>
        ) : (
          <div className="divide-y divide-border">
            {providers.map((item) => (
              <div key={item.id} className="flex items-start gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-semibold">{item.display_name || item.id}</span>
                    <span className="text-xs text-muted-foreground">{item.id}</span>
                    <Badge variant={item.enabled ? 'success' : 'muted'}>{item.enabled ? '已启用' : '已停用'}</Badge>
                    {item.protocols.map((protocol) => <Badge key={protocol} variant="outline">{protocol}</Badge>)}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>优先级 {item.priority}</span>
                    <span>密钥{item.has_api_key ? '已配置' : '未配置'}</span>
                    <span>来源 {item.preset_key || '自定义'}</span>
                    <span>模型 {item.models.length}</span>
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button type="button" variant="ghost" size="sm" onClick={() => startEdit(item)}>编辑</Button>
                  <Button type="button" variant="ghost" size="sm" onClick={() => void toggleEnabled(item)}>{item.enabled ? '下线' : '上线'}</Button>
                  <Button type="button" variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => void removeItem(item)}>删除</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SettingRow({ setting, onUpdate }: { setting: SystemSetting; onUpdate: (key: string, value: string, clear?: boolean) => Promise<void> }) {
  const [value, setValue] = useState(setting.value)
  const [clearSecret, setClearSecret] = useState(false)
  const disabled = !setting.editable
  const isSecret = setting.type === 'secret'
  return <div className="grid gap-3 rounded-lg border border-border bg-card p-4 lg:grid-cols-[minmax(0,1fr)_minmax(240px,360px)_auto]"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{setting.label || setting.key}</p>{setting.restart_required && <Badge variant="warning">需重启</Badge>}{setting.secret && <Badge variant="info">Secret</Badge>}{!setting.editable && <Badge variant="muted">只读</Badge>}</div><p className="mt-1 text-xs text-muted-foreground">{setting.key}</p>{setting.help && <p className="mt-2 text-sm text-muted-foreground">{setting.help}</p>}</div>{setting.type === 'status' ? <p className="font-bold">{setting.masked ? '已配置' : setting.value || '未配置'}</p> : setting.type === 'boolean' ? <label className="flex items-center gap-2 text-sm"><Checkbox disabled={disabled} checked={value === 'true'} onCheckedChange={(v) => setValue(Boolean(v) ? 'true' : 'false')} />启用</label> : setting.type === 'select' ? <Select disabled={disabled} value={value} onValueChange={setValue}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{setting.options.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}</SelectContent></Select> : setting.type === 'textarea' ? <Textarea disabled={disabled || clearSecret} value={value} rows={3} onChange={(e) => setValue(e.target.value)} /> : <div className="grid gap-2"><Input disabled={disabled || clearSecret} type={isSecret ? 'password' : setting.type === 'number' ? 'number' : 'text'} placeholder={isSecret && setting.masked ? '留空保持当前密钥' : undefined} value={value} onChange={(e) => setValue(e.target.value)} />{isSecret && <label className="flex items-center gap-2 text-xs text-muted-foreground"><Checkbox checked={clearSecret} onCheckedChange={(v) => setClearSecret(Boolean(v))} />清空当前值</label>}</div>}{setting.editable && <Button variant="outline" onClick={() => onUpdate(setting.key, clearSecret ? '' : value, clearSecret)}>保存</Button>}</div>
}

function PricingRow({ rule, onUpdate }: { rule: PricingRule; onUpdate: (key: string, priceCredits: number, enabled: boolean) => Promise<void> }) { const [price, setPrice] = useState(rule.price_credits); const [enabled, setEnabled] = useState(rule.enabled); const isSprite = rule.key === 'sprite_sheet'; return <div className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-[minmax(0,1fr)_140px_auto_auto]"><div><p className="font-semibold">{isSprite ? 'sprite_sheet · 序列帧单帧基础价' : rule.key}</p><p className="text-xs text-muted-foreground">{isSprite ? '总价 = 用户帧数 × 该基础价，帧数最多 12。' : rule.enabled ? '启用' : '停用'}</p></div><Input type="number" value={price} onChange={(e) => setPrice(Number(e.target.value))} /><label className="flex items-center gap-2 text-sm"><Checkbox checked={enabled} onCheckedChange={(v) => setEnabled(Boolean(v))} />启用</label><Button variant="outline" onClick={() => onUpdate(rule.key, price, enabled)}>保存</Button></div> }

function PackageEditor({ packages, onCreate, onUpdate }: { packages: CreditPackage[]; onCreate: (payload: CreditPackage) => Promise<void>; onUpdate: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void> }) { const [draft, setDraft] = useState<CreditPackage>({ key: 'custom', name: 'Custom', credits: 100, amount_cents: 990, currency: 'cny', enabled: true, sort_order: 40 }); return <div className="grid gap-3"><h3 className="text-lg font-semibold">充值套餐</h3><Alert variant="info">历史订单会引用套餐 ID，因此这里不提供删除；不需要的套餐请停用。</Alert>{packages.map((item) => <PackageRow key={item.key} item={item} onUpdate={onUpdate} />)}<div className="grid gap-2 rounded-lg border border-border bg-card p-4 lg:grid-cols-4"><Input placeholder="key" value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} /><Input placeholder="名称" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /><Input type="number" placeholder="点数" value={draft.credits} onChange={(e) => setDraft({ ...draft, credits: Number(e.target.value) })} /><Input type="number" placeholder="金额（分）" value={draft.amount_cents} onChange={(e) => setDraft({ ...draft, amount_cents: Number(e.target.value) })} /><Input placeholder="币种" value={draft.currency} onChange={(e) => setDraft({ ...draft, currency: e.target.value })} /><Input type="number" placeholder="排序" value={draft.sort_order} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) })} /><label className="flex items-center gap-2 text-sm"><Checkbox checked={draft.enabled} onCheckedChange={(v) => setDraft({ ...draft, enabled: Boolean(v) })} />启用</label><Button onClick={() => onCreate(draft)}>新增</Button></div></div> }

function PackageRow({ item, onUpdate }: { item: CreditPackage; onUpdate: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void> }) { const [name, setName] = useState(item.name); const [credits, setCredits] = useState(item.credits); const [amount, setAmount] = useState(item.amount_cents); const [currency, setCurrency] = useState(item.currency); const [enabled, setEnabled] = useState(item.enabled); const [sortOrder, setSortOrder] = useState(item.sort_order); return <div className="grid gap-2 rounded-lg border border-border bg-card p-4 lg:grid-cols-4"><div><p className="font-semibold">{item.key}</p><p className="text-xs text-muted-foreground">{item.enabled ? '公开展示' : '已停用'}</p></div><Input value={name} onChange={(e) => setName(e.target.value)} /><Input type="number" value={credits} onChange={(e) => setCredits(Number(e.target.value))} /><Input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} /><Input value={currency} onChange={(e) => setCurrency(e.target.value)} /><Input type="number" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value))} /><label className="flex items-center gap-2 text-sm"><Checkbox checked={enabled} onCheckedChange={(v) => setEnabled(Boolean(v))} />启用</label><Button variant="outline" onClick={() => onUpdate(item.key, { name, credits, amount_cents: amount, currency, enabled, sort_order: sortOrder })}>保存</Button></div> }

function MembershipPlanEditor({ plans, onCreate, onUpdate }: { plans: MembershipPlan[]; onCreate: (payload: MembershipPlan) => Promise<void>; onUpdate: (key: string, payload: Omit<MembershipPlan, 'key'>) => Promise<void> }) { const [draft, setDraft] = useState<MembershipPlan>({ key: 'new_monthly', name: '新月卡', daily_quota: 100, amount_cents: 9900, currency: 'cny', duration_days: 30, enabled: true, sort_order: 40 }); return <div className="grid gap-3"><h3 className="text-lg font-semibold">月卡档位</h3><Alert variant="info">月卡仅用于生成任务临时额度；用户购买后按业务时区每天刷新。历史订单会引用档位 key，不需要的档位请停用。</Alert>{plans.map((item) => <MembershipPlanRow key={item.key} item={item} onUpdate={onUpdate} />)}<div className="grid gap-2 rounded-lg border border-border bg-card p-4 lg:grid-cols-4"><Input placeholder="key" value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} /><Input placeholder="名称" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /><Input type="number" placeholder="每日额度" value={draft.daily_quota} onChange={(e) => setDraft({ ...draft, daily_quota: Number(e.target.value) })} /><Input type="number" placeholder="金额（分）" value={draft.amount_cents} onChange={(e) => setDraft({ ...draft, amount_cents: Number(e.target.value) })} /><Input type="number" placeholder="天数" value={draft.duration_days} onChange={(e) => setDraft({ ...draft, duration_days: Number(e.target.value) })} /><Input placeholder="币种" value={draft.currency} onChange={(e) => setDraft({ ...draft, currency: e.target.value })} /><Input type="number" placeholder="排序" value={draft.sort_order} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) })} /><label className="flex items-center gap-2 text-sm"><Checkbox checked={draft.enabled} onCheckedChange={(v) => setDraft({ ...draft, enabled: Boolean(v) })} />启用</label><Button onClick={() => onCreate(draft)}>新增</Button></div></div> }

function MembershipPlanRow({ item, onUpdate }: { item: MembershipPlan; onUpdate: (key: string, payload: Omit<MembershipPlan, 'key'>) => Promise<void> }) { const [name, setName] = useState(item.name); const [dailyQuota, setDailyQuota] = useState(item.daily_quota); const [amount, setAmount] = useState(item.amount_cents); const [durationDays, setDurationDays] = useState(item.duration_days); const [currency, setCurrency] = useState(item.currency); const [enabled, setEnabled] = useState(item.enabled); const [sortOrder, setSortOrder] = useState(item.sort_order); return <div className="grid gap-2 rounded-lg border border-border bg-card p-4 lg:grid-cols-4"><div><p className="font-semibold">{item.key}</p><p className="text-xs text-muted-foreground">{item.enabled ? '公开展示' : '已停用'}</p></div><Input value={name} onChange={(e) => setName(e.target.value)} /><Input type="number" value={dailyQuota} onChange={(e) => setDailyQuota(Number(e.target.value))} /><Input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} /><Input type="number" value={durationDays} onChange={(e) => setDurationDays(Number(e.target.value))} /><Input value={currency} onChange={(e) => setCurrency(e.target.value)} /><Input type="number" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value))} /><label className="flex items-center gap-2 text-sm"><Checkbox checked={enabled} onCheckedChange={(v) => setEnabled(Boolean(v))} />启用</label><Button variant="outline" onClick={() => onUpdate(item.key, { name, daily_quota: dailyQuota, amount_cents: amount, currency, duration_days: durationDays, enabled, sort_order: sortOrder })}>保存</Button></div> }
