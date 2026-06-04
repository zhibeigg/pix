import { FormEvent, useEffect, useMemo, useState } from 'react'
import type { AdminDashboard, CreditPackage, GenerationJob, PricingRule, SystemSetting, User } from '../types'
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

type Props = { dashboard: AdminDashboard | null; users: User[]; jobs: GenerationJob[]; pricing: PricingRule[]; packages: CreditPackage[]; settings: SystemSetting[]; onRefresh: () => void; onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>; onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>; onCreatePackage: (payload: CreditPackage) => Promise<void>; onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>; onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>; onTestEmail: (email: string) => Promise<void>; onAdminRetryJob: (job: GenerationJob) => Promise<void>; onAdminCancelJob: (job: GenerationJob) => Promise<void>; onAdminFailRefundJob: (job: GenerationJob) => Promise<void> }
const settingTabs = ['运营保护', '邮件验证码', '模型与 API', '素材默认值', '序列帧', '支付与站点', '存储 / 队列 / 安全']
const announcementSettingKeys = {
  enabled: 'site.announcement.enabled',
  title: 'site.announcement.title',
  body: 'site.announcement.body',
} as const

export function AdminPanel({ dashboard, users, jobs, pricing, packages, settings, onRefresh, onAdjustCredits, onUpdatePricing, onCreatePackage, onUpdatePackage, onUpdateSetting, onTestEmail, onAdminRetryJob, onAdminCancelJob, onAdminFailRefundJob }: Props) {
  const [tab, setTab] = useState('dashboard')
  const [selectedUser, setSelectedUser] = useState('0')
  const [amount, setAmount] = useState(100)
  const [note, setNote] = useState('运营补点')
  const groups = useMemo(() => groupSettings(settings), [settings])
  const settingGroup = groups[tab]
  async function submitAdjust(event: FormEvent) { event.preventDefault(); if (Number(selectedUser)) await onAdjustCredits(Number(selectedUser), amount, note) }
  return (
    <PixPanel eyebrow="Control Room" title="管理后台" description="配置站点、模型、邮件、套餐和运营保护。高风险环境项只显示状态。" action={<Button variant="outline" onClick={onRefresh}>刷新</Button>}>
      <div className="grid gap-6">
        <Tabs value={tab} onValueChange={setTab}><TabsList className="h-auto flex-wrap justify-start"><TabsTrigger value="dashboard">概览</TabsTrigger><TabsTrigger value="jobs">任务操作</TabsTrigger><TabsTrigger value="users">用户与点数</TabsTrigger><TabsTrigger value="announcements">系统公告</TabsTrigger><TabsTrigger value="pricing">价格规则</TabsTrigger><TabsTrigger value="packages">充值套餐</TabsTrigger>{settingTabs.map((item) => <TabsTrigger key={item} value={item}>{item}</TabsTrigger>)}</TabsList></Tabs>
        {tab === 'dashboard' && dashboard && <DashboardGrid dashboard={dashboard} />}
        {tab === 'jobs' && <AdminJobsList jobs={jobs} onRetry={onAdminRetryJob} onCancel={onAdminCancelJob} onFailRefund={onAdminFailRefundJob} />}
        {tab === 'users' && <form className="grid max-w-xl gap-4" onSubmit={submitAdjust}><PixField label="用户"><Select value={selectedUser} onValueChange={setSelectedUser}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="0">选择用户</SelectItem>{users.map((u) => <SelectItem value={String(u.id)} key={u.id}>{u.email} · {u.role}</SelectItem>)}</SelectContent></Select></PixField><PixField label="点数变化"><Input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} /></PixField><PixField label="备注"><Input value={note} onChange={(e) => setNote(e.target.value)} /></PixField><Button type="submit">调整点数</Button></form>}
        {tab === 'announcements' && <AnnouncementEditor settings={settings} onUpdate={onUpdateSetting} />}
        {tab === 'pricing' && <div className="grid gap-3"><h3 className="text-lg font-semibold">价格规则</h3>{pricing.map((rule) => <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />)}</div>}
        {tab === 'packages' && <PackageEditor packages={packages} onCreate={onCreatePackage} onUpdate={onUpdatePackage} />}
        {settingGroup && <div className="grid gap-3"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">{tab}</h3><p className="text-sm text-muted-foreground">保存后只影响新请求/新任务；带“需重启”的项目请重启服务或 worker。</p></div>{tab === '邮件验证码' && <EmailTestBox onTest={onTestEmail} />}</div>{settingGroup.map((setting) => <SettingRow setting={setting} onUpdate={onUpdateSetting} key={setting.key} />)}</div>}
      </div>
    </PixPanel>
  )
}

function groupSettings(settings: SystemSetting[]) { return settings.reduce<Record<string, SystemSetting[]>>((acc, setting) => { const category = setting.category || '其他'; acc[category] = acc[category] || []; acc[category].push(setting); return acc }, {}) }
function DashboardGrid({ dashboard }: { dashboard: AdminDashboard }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><PixMetric label="今日任务" value={dashboard.jobs_today} tone="info" /><PixMetric label="成功 / 失败" value={`${dashboard.succeeded_today} / ${dashboard.failed_today}`} tone={dashboard.failed_today > 0 ? 'danger' : 'success'} /><PixMetric label="策略拦截" value={dashboard.policy_blocked_today} tone={dashboard.policy_blocked_today > 0 ? 'warning' : 'success'} /><PixMetric label="上游 / 超时" value={`${dashboard.upstream_errors_today} / ${dashboard.timeout_jobs_today}`} tone={(dashboard.upstream_errors_today + dashboard.timeout_jobs_today) > 0 ? 'danger' : 'success'} /><PixMetric label="Pipeline 异常" value={dashboard.pipeline_errors_today} tone={dashboard.pipeline_errors_today > 0 ? 'danger' : 'success'} /><PixMetric label="排队 / 运行" value={`${dashboard.pending_jobs} / ${dashboard.running_jobs}`} tone="info" /><PixMetric label="运行超 30 分钟" value={dashboard.running_over_30m_jobs} tone={dashboard.running_over_30m_jobs > 0 ? 'warning' : 'success'} /><PixMetric label="候选失败 / 警告" value={`${dashboard.candidate_failures_today} / ${dashboard.pipeline_warnings_today}`} tone={(dashboard.candidate_failures_today + dashboard.pipeline_warnings_today) > 0 ? 'warning' : 'success'} /><PixMetric label="平均耗时" value={`${Math.round(dashboard.average_generation_seconds_today)}s`} /><PixMetric label="P95 耗时" value={`${Math.round(dashboard.p95_generation_seconds_today)}s`} /><PixMetric label="今日充值" value={dashboard.credits_recharged_today} tone="success" /><PixMetric label="今日消费" value={dashboard.credits_consumed_today} tone="warning" /><PixMetric label="今日上传" value={dashboard.uploads_today} /><PixMetric label="总用户" value={dashboard.total_users} /><PixMetric label="失败率" value={`${Math.round(dashboard.failure_rate * 100)}%`} tone={dashboard.failure_rate > 0.1 ? 'danger' : 'success'} /></div>
}
function AdminJobsList({ jobs, onRetry, onCancel, onFailRefund }: { jobs: GenerationJob[]; onRetry: (job: GenerationJob) => Promise<void>; onCancel: (job: GenerationJob) => Promise<void>; onFailRefund: (job: GenerationJob) => Promise<void> }) {
  if (!jobs.length) return <Alert variant="info">暂无任务记录。</Alert>
  return <div className="grid gap-3"><div><h3 className="text-lg font-semibold">任务操作</h3><p className="text-sm text-muted-foreground">显示最新 100 个任务；可重试失败任务，或取消/标记失败并退款排队中与运行中任务。</p></div>{jobs.map((job) => <div key={job.id} className="grid gap-3 rounded-lg border border-border bg-card p-4 xl:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">#{job.id} · {job.job_type}</p><Badge variant={job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'danger' : job.status === 'running' ? 'warning' : job.status === 'cancelled' ? 'muted' : 'info'}>{job.status}</Badge>{job.failure_type && <Badge variant="outline">{job.failure_type}</Badge>}{job.failure_source && <Badge variant="outline">{job.failure_source}</Badge>}{job.failure_code && <Badge variant="outline">{job.failure_code}</Badge>}</div><p className="mt-1 truncate text-sm text-muted-foreground">{job.prompt || '无 prompt'} · {formatDateTime(job.created_at)} · 运行 {formatRuntime(job)}</p><div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>点数 {job.price_credits}</span><span>冻结 {job.reserved_credits}</span><span>候选失败 {job.candidate_failure_count}</span><span>流水线警告 {job.pipeline_warning_count}</span></div>{job.error_message && <p className="mt-2 line-clamp-2 text-sm text-destructive">{job.error_message.slice(0, 220)}</p>}</div><div className="flex flex-wrap items-center gap-2 xl:justify-end">{job.status === 'failed' && <Button variant="outline" size="sm" onClick={() => { if (window.confirm(`重试任务 #${job.id}？`)) void onRetry(job) }}>重试</Button>}{['pending', 'running'].includes(job.status) && <Button variant="outline" size="sm" onClick={() => { if (window.confirm(`取消任务 #${job.id} 并退款？`)) void onCancel(job) }}>取消并退款</Button>}{['pending', 'running', 'failed'].includes(job.status) && <Button variant="soft" size="sm" onClick={() => { if (window.confirm(`标记任务 #${job.id} 失败并退款？`)) void onFailRefund(job) }}>标记失败退款</Button>}</div></div>)}</div>
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

function settingValue(settings: SystemSetting[], key: string, fallback = '') {
  return settings.find((setting) => setting.key === key)?.value ?? fallback
}

function AnnouncementEditor({ settings, onUpdate }: { settings: SystemSetting[]; onUpdate: (key: string, value: string, clear?: boolean) => Promise<void> }) {
  const [title, setTitle] = useState(() => settingValue(settings, announcementSettingKeys.title, ''))
  const [body, setBody] = useState(() => settingValue(settings, announcementSettingKeys.body, ''))
  const [enabled, setEnabled] = useState(() => settingValue(settings, announcementSettingKeys.enabled, 'false') === 'true')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setTitle(settingValue(settings, announcementSettingKeys.title, ''))
    setBody(settingValue(settings, announcementSettingKeys.body, ''))
    setEnabled(settingValue(settings, announcementSettingKeys.enabled, 'false') === 'true')
  }, [settings])

  async function save(nextEnabled = enabled) {
    setSaving(true)
    try {
      await onUpdate(announcementSettingKeys.title, title)
      await onUpdate(announcementSettingKeys.body, body)
      await onUpdate(announcementSettingKeys.enabled, nextEnabled ? 'true' : 'false')
      setEnabled(nextEnabled)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <form className="grid gap-4 rounded-lg border border-border bg-card p-4" onSubmit={(event) => { event.preventDefault(); void save(true) }}>
        <div>
          <h3 className="text-lg font-semibold">系统公告</h3>
          <p className="mt-1 text-sm text-muted-foreground">发布后会显示在顶部铃铛的系统公告弹窗中，访客和登录用户都能看到。</p>
        </div>
        <PixField label="公告标题"><Input value={title} maxLength={80} placeholder="例如：维护通知 / 新功能上线" onChange={(event) => setTitle(event.target.value)} /></PixField>
        <PixField label="公告正文"><Textarea value={body} rows={6} maxLength={1200} placeholder="写清楚影响范围、时间和用户需要做什么。" onChange={(event) => setBody(event.target.value)} /></PixField>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={enabled} onCheckedChange={(value) => setEnabled(Boolean(value))} />启用公告</label>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={saving || (!title.trim() && !body.trim())}>{saving ? '发布中…' : '发布公告'}</Button>
          <Button type="button" variant="outline" disabled={saving} onClick={() => void save(false)}>下线公告</Button>
          <Button type="button" variant="soft" disabled={saving} onClick={() => void save(enabled)}>保存草稿</Button>
        </div>
      </form>
      <aside className="rounded-lg border border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper-soft))] p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]">
        <p className="text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Preview</p>
        <div className="mt-3 rounded-lg border border-border bg-card p-4 shadow-[0_12px_32px_-26px_rgba(15,15,15,0.42)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
          <p className="text-xs font-semibold text-primary">系统公告</p>
          <h4 className="mt-2 text-base font-semibold">{title.trim() || '公告标题预览'}</h4>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{body.trim() || '公告正文会显示在这里。'}</p>
          <Badge variant={enabled ? 'success' : 'muted'}>{enabled ? '当前启用' : '当前下线'}</Badge>
        </div>
      </aside>
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
