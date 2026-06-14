import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { AdminBatchAdjustCreditsResponse, AdminDashboard, AnnouncementItem, AnnouncementListResponse, AnnouncementPublishPayload, AnnouncementPublishResponse, CreditPackage, GenerationJob, PricingRule, SystemSetting, User } from '../types'
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
import { useConfirm } from './ConfirmDialog'

type Props = { dashboard: AdminDashboard | null; users: User[]; jobs: GenerationJob[]; pricing: PricingRule[]; packages: CreditPackage[]; settings: SystemSetting[]; onRefresh: () => void; onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>; onAdjustCreditsBatch: (payload: { userIds: number[]; allUsers: boolean; amount: number; note: string }) => Promise<AdminBatchAdjustCreditsResponse | void>; onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>; onCreatePackage: (payload: CreditPackage) => Promise<void>; onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>; onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>; onPublishAnnouncement: (payload: AnnouncementPublishPayload) => Promise<AnnouncementPublishResponse>; onTestEmail: (email: string) => Promise<void>; onAdminRetryJob: (job: GenerationJob) => Promise<void>; onAdminCancelJob: (job: GenerationJob) => Promise<void>; onAdminFailRefundJob: (job: GenerationJob) => Promise<void>; onAdminAnnouncements?: () => Promise<AnnouncementListResponse>; onCreateAnnouncement?: (payload: { title: string; body: string; enabled: boolean; publish_now: boolean; notify: boolean }) => Promise<AnnouncementItem>; onUpdateAnnouncement?: (id: number, payload: { title?: string; body?: string; enabled?: boolean }) => Promise<AnnouncementItem>; onDeleteAnnouncement?: (id: number) => Promise<{ deleted: boolean }>; onTestAnnouncementEmail?: (email: string, title: string, body: string) => Promise<{ message: string }> }
const settingTabs = ['运营保护', '邮件验证码', '模型与 API', '素材默认值', '序列帧', '支付与站点', '存储 / 队列 / 安全']

export function AdminPanel({ dashboard, users, jobs, pricing, packages, settings, onRefresh, onAdjustCredits, onAdjustCreditsBatch, onUpdatePricing, onCreatePackage, onUpdatePackage, onUpdateSetting, onPublishAnnouncement, onTestEmail, onAdminRetryJob, onAdminCancelJob, onAdminFailRefundJob, onAdminAnnouncements, onCreateAnnouncement, onUpdateAnnouncement, onDeleteAnnouncement, onTestAnnouncementEmail }: Props) {
  const [tab, setTab] = useState('dashboard')
  const groups = useMemo(() => groupSettings(settings), [settings])
  const settingGroup = groups[tab]
  return (
    <PixPanel eyebrow="Control Room" title="管理后台" description="配置站点、模型、邮件、套餐和运营保护。高风险环境项只显示状态。" action={<Button variant="outline" onClick={onRefresh}>刷新</Button>}>
      <div className="grid gap-6">
        <Tabs value={tab} onValueChange={setTab}><TabsList className="h-auto flex-wrap justify-start"><TabsTrigger value="dashboard">概览</TabsTrigger><TabsTrigger value="jobs">任务操作</TabsTrigger><TabsTrigger value="users">用户与点数</TabsTrigger><TabsTrigger value="announcements">系统公告</TabsTrigger><TabsTrigger value="pricing">价格规则</TabsTrigger><TabsTrigger value="packages">充值套餐</TabsTrigger>{settingTabs.map((item) => <TabsTrigger key={item} value={item}>{item}</TabsTrigger>)}</TabsList></Tabs>
        {tab === 'dashboard' && dashboard && <DashboardGrid dashboard={dashboard} />}
        {tab === 'jobs' && <AdminJobsList jobs={jobs} onRetry={onAdminRetryJob} onCancel={onAdminCancelJob} onFailRefund={onAdminFailRefundJob} />}
        {tab === 'users' && <AdminCreditsPanel users={users} onAdjustSingle={onAdjustCredits} onAdjustBatch={onAdjustCreditsBatch} />}
        {tab === 'announcements' && <AnnouncementEditor onPublish={onPublishAnnouncement} onTestEmail={onTestEmail} onListAnnouncements={onAdminAnnouncements} onCreateAnnouncement={onCreateAnnouncement} onUpdateAnnouncement={onUpdateAnnouncement} onDeleteAnnouncement={onDeleteAnnouncement} onTestAnnouncementEmail={onTestAnnouncementEmail} />}
        {tab === 'pricing' && <div className="grid gap-3"><h3 className="text-lg font-semibold">价格规则</h3>{pricing.map((rule) => <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />)}</div>}
        {tab === 'packages' && <PackageEditor packages={packages} onCreate={onCreatePackage} onUpdate={onUpdatePackage} />}
        {settingGroup && <div className="grid gap-3"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">{tab}</h3><p className="text-sm text-muted-foreground">保存后只影响新请求/新任务；带"需重启"的项目请重启服务或 worker。</p></div>{tab === '邮件验证码' && <EmailTestBox onTest={onTestEmail} />}</div>{settingGroup.map((setting) => <SettingRow setting={setting} onUpdate={onUpdateSetting} key={setting.key} />)}</div>}
      </div>
    </PixPanel>
  )
}

function groupSettings(settings: SystemSetting[]) { return settings.reduce<Record<string, SystemSetting[]>>((acc, setting) => { const category = setting.category || '其他'; acc[category] = acc[category] || []; acc[category].push(setting); return acc }, {}) }

function AdminCreditsPanel({ users, onAdjustSingle, onAdjustBatch }: { users: User[]; onAdjustSingle: (userId: number, amount: number, note: string) => Promise<void>; onAdjustBatch: (payload: { userIds: number[]; allUsers: boolean; amount: number; note: string }) => Promise<AdminBatchAdjustCreditsResponse | void> }) {
  const confirm = useConfirm()
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [allUsers, setAllUsers] = useState(false)
  const [amount, setAmount] = useState(100)
  const [note, setNote] = useState('运营补点')
  const [quickUser, setQuickUser] = useState('0')
  const [submitting, setSubmitting] = useState(false)
  const [resultText, setResultText] = useState('')
  const pageUserIds = users.map((user) => user.id)
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
            <p className="text-sm text-muted-foreground">选择单个或多个用户后统一调整点数；需要覆盖所有账户时使用“全部活跃用户”。</p>
          </div>
          <Badge variant={allUsers || selectedIds.length > 0 ? 'info' : 'outline'}>{targetCountLabel}</Badge>
        </div>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
          <PixField label="快速选择单人">
            <Select value={quickUser} onValueChange={applyQuickUser}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="0">选择用户</SelectItem>{users.map((u) => <SelectItem value={String(u.id)} key={u.id}>{u.email} · {u.role}</SelectItem>)}</SelectContent>
            </Select>
          </PixField>
          <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
            <Checkbox checked={allPageSelected} onCheckedChange={(value) => toggleAllPage(Boolean(value))} />
            全选当前列表
          </label>
          <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
            <Checkbox checked={allUsers} onCheckedChange={(value) => { const checked = Boolean(value); setAllUsers(checked); if (checked) setSelectedIds([]) }} />
            全部活跃用户
          </label>
        </div>
        <div className="max-h-[360px] overflow-auto rounded-xl border border-border">
          {users.length === 0 ? <p className="p-4 text-sm text-muted-foreground">暂无用户。</p> : users.map((user) => {
            const selected = selectedSet.has(user.id)
            return (
              <label key={user.id} className={`grid cursor-pointer gap-2 border-b border-border px-4 py-3 last:border-b-0 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center ${selected ? 'bg-primary/10' : 'bg-card'}`}>
                <Checkbox checked={selected} onCheckedChange={(value) => toggleUser(user.id, Boolean(value))} />
                <span className="min-w-0">
                  <span className="block truncate font-medium">{user.display_name || user.email}</span>
                  <span className="block truncate text-xs text-muted-foreground">#{user.id} · {user.email}</span>
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
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><PixMetric label="今日任务" value={dashboard.jobs_today} tone="info" /><PixMetric label="成功 / 失败" value={`${dashboard.succeeded_today} / ${dashboard.failed_today}`} tone={dashboard.failed_today > 0 ? 'danger' : 'success'} /><PixMetric label="策略拦截" value={dashboard.policy_blocked_today} tone={dashboard.policy_blocked_today > 0 ? 'warning' : 'success'} /><PixMetric label="上游 / 超时" value={`${dashboard.upstream_errors_today} / ${dashboard.timeout_jobs_today}`} tone={(dashboard.upstream_errors_today + dashboard.timeout_jobs_today) > 0 ? 'danger' : 'success'} /><PixMetric label="Pipeline 异常" value={dashboard.pipeline_errors_today} tone={dashboard.pipeline_errors_today > 0 ? 'danger' : 'success'} /><PixMetric label="排队 / 运行" value={`${dashboard.pending_jobs} / ${dashboard.running_jobs}`} tone="info" /><PixMetric label="运行超 30 分钟" value={dashboard.running_over_30m_jobs} tone={dashboard.running_over_30m_jobs > 0 ? 'warning' : 'success'} /><PixMetric label="候选失败 / 警告" value={`${dashboard.candidate_failures_today} / ${dashboard.pipeline_warnings_today}`} tone={(dashboard.candidate_failures_today + dashboard.pipeline_warnings_today) > 0 ? 'warning' : 'success'} /><PixMetric label="平均耗时" value={`${Math.round(dashboard.average_generation_seconds_today)}s`} /><PixMetric label="P95 耗时" value={`${Math.round(dashboard.p95_generation_seconds_today)}s`} /><PixMetric label="今日充值" value={dashboard.credits_recharged_today} tone="success" /><PixMetric label="今日消费" value={dashboard.credits_consumed_today} tone="warning" /><PixMetric label="今日上传" value={dashboard.uploads_today} /><PixMetric label="总用户" value={dashboard.total_users} /><PixMetric label="失败率" value={`${Math.round(dashboard.failure_rate * 100)}%`} tone={dashboard.failure_rate > 0.1 ? 'danger' : 'success'} /></div>
}
function AdminJobsList({ jobs, onRetry, onCancel, onFailRefund }: { jobs: GenerationJob[]; onRetry: (job: GenerationJob) => Promise<void>; onCancel: (job: GenerationJob) => Promise<void>; onFailRefund: (job: GenerationJob) => Promise<void> }) {
  const confirm = useConfirm()
  if (!jobs.length) return <Alert variant="info">暂无任务记录。</Alert>
  return <div className="grid gap-3"><div><h3 className="text-lg font-semibold">任务操作</h3><p className="text-sm text-muted-foreground">显示最新 100 个任务；可重试失败任务，或取消/标记失败并退款排队中与运行中任务。</p></div>{jobs.map((job) => <div key={job.id} className="grid gap-3 rounded-lg border border-border bg-card p-4 xl:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">#{job.id} · {job.job_type}</p><Badge variant={job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'danger' : job.status === 'running' ? 'warning' : job.status === 'cancelled' ? 'muted' : 'info'}>{job.status}</Badge>{job.failure_type && <Badge variant="outline">{job.failure_type}</Badge>}{job.failure_source && <Badge variant="outline">{job.failure_source}</Badge>}{job.failure_code && <Badge variant="outline">{job.failure_code}</Badge>}</div><p className="mt-1 truncate text-sm text-muted-foreground">{job.prompt || '无 prompt'} · {formatDateTime(job.created_at)} · 运行 {formatRuntime(job)}</p><div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>点数 {job.price_credits}</span><span>冻结 {job.reserved_credits}</span><span>候选失败 {job.candidate_failure_count}</span><span>流水线警告 {job.pipeline_warning_count}</span></div>{job.error_message && <p className="mt-2 line-clamp-2 text-sm text-destructive">{job.error_message.slice(0, 220)}</p>}</div><div className="flex flex-wrap items-center gap-2 xl:justify-end">{job.status === 'failed' && <Button variant="outline" size="sm" onClick={async () => { if (await confirm({ title: '重试任务', description: `重试任务 #${job.id}？`, confirmText: '重试' })) void onRetry(job) }}>重试</Button>}{['pending', 'running'].includes(job.status) && <Button variant="outline" size="sm" onClick={async () => { if (await confirm({ title: '取消并退款', description: `取消任务 #${job.id} 并退款？`, confirmText: '取消并退款', tone: 'danger' })) void onCancel(job) }}>取消并退款</Button>}{['pending', 'running', 'failed'].includes(job.status) && <Button variant="soft" size="sm" onClick={async () => { if (await confirm({ title: '标记失败并退款', description: `标记任务 #${job.id} 失败并退款？`, confirmText: '标记失败退款', tone: 'danger' })) void onFailRefund(job) }}>标记失败退款</Button>}</div></div>)}</div>
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
