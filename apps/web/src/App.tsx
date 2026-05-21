import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { PixThemeMode, PixThemePreference } from './theme'
import { api, ApiError } from './api'
import { AppTabs, type AppPage } from './components/AppTabs'
import { AccountMenu } from './components/AccountMenu'
import { AppHero } from './components/AppHero'
import { AuthPanel } from './components/AuthPanel'
import { Alert } from './components/ui/alert'
import { Button } from './components/ui/button'
import { ThemeModeMenu } from './components/ThemeModeMenu'
import { LandingSections } from './components/LandingSections'
import { SetupWizard } from './components/SetupWizard'
import { AdminPage } from './pages/AdminPage'
import { BillingPage } from './pages/BillingPage'
import { GalleryPage } from './pages/GalleryPage'
import { PacksPage } from './pages/PacksPage'
import { RawImagePage } from './pages/RawImagePage'
import { WorkspacePage, type WorkMode } from './pages/WorkspacePage'
import { buildGridDesign, defaultPixelize } from './pixelize'
import type { AdminDashboard, ContactSheetCandidate, CreditBalance, CreditPackage, CreditTransaction, EmailCodeResponse, GenerationBatch, GenerationJob, JobCreateRequest, PaymentCheckout, PaymentOrder, PricingRule, SetupStatus, SystemSetting, User } from './types'

const TOKEN_KEY = 'pix_web_token'

type AppProps = {
  themeMode: PixThemeMode
  themePreference: PixThemePreference
  systemThemeMode: PixThemeMode
  onThemePreferenceChange: (preference: PixThemePreference) => void
}

function pageFromHash(user: User | null): AppPage {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const page = ['workspace', 'raw-image', 'gallery', 'packs', 'billing', 'admin'].includes(raw) ? raw as AppPage : 'workspace'
  if (page === 'admin' && user?.role !== 'admin') return 'workspace'
  return page
}

export function App({ themeMode, themePreference, systemThemeMode, onThemePreferenceChange }: AppProps) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [user, setUser] = useState<User | null>(null)
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [transactions, setTransactions] = useState<CreditTransaction[]>([])
  const [packages, setPackages] = useState<CreditPackage[]>([])
  const [adminPackages, setAdminPackages] = useState<CreditPackage[]>([])
  const [orders, setOrders] = useState<PaymentOrder[]>([])
  const [checkout, setCheckout] = useState<PaymentCheckout | null>(null)
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [batches, setBatches] = useState<GenerationBatch[]>([])
  const [pricing, setPricing] = useState<PricingRule[]>([])
  const [adminUsers, setAdminUsers] = useState<User[]>([])
  const [systemSettings, setSystemSettings] = useState<SystemSetting[]>([])
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null)
  const [busy, setBusy] = useState(false)
  const [retryingBatchId, setRetryingBatchId] = useState<number | null>(null)
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null)
  const [downloadingBatchId, setDownloadingBatchId] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null)
  const [setupLoading, setSetupLoading] = useState(true)
  const [page, setPage] = useState<AppPage>(() => pageFromHash(null))
  const [mode, setMode] = useState<WorkMode>('single')
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null)
  const [selectedBatchJobs, setSelectedBatchJobs] = useState<GenerationJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [selectedRawJobId, setSelectedRawJobId] = useState<number | null>(null)
  const pollFailuresRef = useRef(0)

  const isAdmin = user?.role === 'admin'
  const selectedBatch = useMemo(() => batches.find((batch) => batch.id === selectedBatchId) ?? null, [batches, selectedBatchId])
  const selectedJobPool = page === 'packs' && selectedBatchId ? selectedBatchJobs : jobs
  const selectedJob = useMemo(() => selectedJobPool.find((job) => job.id === selectedJobId) ?? null, [selectedJobPool, selectedJobId])
  const activeJobs = useMemo(() => jobs.filter((job) => ['pending', 'running'].includes(job.status)).length, [jobs])
  const completedJobs = useMemo(() => jobs.filter((job) => job.status === 'succeeded').length, [jobs])
  const failedJobs = useMemo(() => jobs.filter((job) => job.status === 'failed').length, [jobs])

  const refreshSetupStatus = useCallback(async () => {
    try {
      setSetupStatus(await api.setupStatus())
    } finally {
      setSetupLoading(false)
    }
  }, [])

  const showError = useCallback((error: unknown) => {
    if (error instanceof ApiError) setMessage(error.message)
    else if (error instanceof Error) setMessage(error.message)
    else setMessage('发生未知错误')
  }, [])

  const refreshCore = useCallback(async (activeToken = token) => {
    if (!activeToken) return
    const [me, nextBalance, nextTransactions, nextPackages, nextOrders, nextJobs, nextBatches, nextPricing] = await Promise.all([
      api.me(activeToken),
      api.balance(activeToken),
      api.transactions(activeToken),
      api.packages(),
      api.orders(activeToken),
      api.jobs(activeToken),
      api.batches(activeToken),
      api.pricing(activeToken),
    ])
    setUser(me)
    setBalance(nextBalance)
    setTransactions(nextTransactions)
    setPackages(nextPackages)
    setOrders(nextOrders)
    setJobs(nextJobs)
    setBatches(nextBatches)
    setPricing(nextPricing)
    if (selectedBatchId) {
      setSelectedBatchJobs(await api.batchJobs(activeToken, selectedBatchId))
    }
    if (me.role === 'admin') {
      const [users, settings, dashboard, nextAdminPackages] = await Promise.all([
        api.adminUsers(activeToken),
        api.adminSettings(activeToken),
        api.adminDashboard(activeToken),
        api.adminPackages(activeToken),
      ])
      setAdminUsers(users)
      setSystemSettings(settings)
      setAdminDashboard(dashboard)
      setAdminPackages(nextAdminPackages)
    }
  }, [selectedBatchId, token])

  useEffect(() => {
    refreshSetupStatus().catch(showError)
  }, [refreshSetupStatus, showError])

  useEffect(() => {
    function syncHash() {
      setPage(pageFromHash(user))
    }
    window.addEventListener('hashchange', syncHash)
    syncHash()
    return () => window.removeEventListener('hashchange', syncHash)
  }, [user])

  useEffect(() => {
    if (!token) return
    refreshCore(token).catch((error) => {
      localStorage.removeItem(TOKEN_KEY)
      setToken('')
      setUser(null)
      showError(error)
    })
  }, [refreshCore, showError, token])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    let timer = 0

    async function poll() {
      if (cancelled) return
      const delay = pollFailuresRef.current >= 4 ? 15000 : pollFailuresRef.current >= 2 ? 6000 : 3000
      timer = window.setTimeout(poll, delay)
      if (document.visibilityState === 'hidden') return
      try {
        const [nextJobs, nextBatches, nextBalance, nextOrders] = await Promise.all([
          api.jobs(token),
          api.batches(token),
          api.balance(token),
          api.orders(token),
        ])
        setJobs(nextJobs)
        setBatches(nextBatches)
        setBalance(nextBalance)
        setOrders(nextOrders)
        pollFailuresRef.current = 0
      } catch {
        pollFailuresRef.current += 1
      }
    }

    poll()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [token])

  async function login(email: string, password: string) {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.login(email, password)
      localStorage.setItem(TOKEN_KEY, result.access_token)
      setToken(result.access_token)
      await refreshCore(result.access_token)
      await refreshSetupStatus()
      setMessage('登录成功')
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function register(email: string, password: string, displayName: string, verificationCode: string) {
    setBusy(true)
    setMessage('')
    try {
      await api.register(email, password, displayName, verificationCode)
      await login(email, password)
      await refreshSetupStatus()
      setMessage('注册成功')
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function bootstrapAdmin(email: string, password: string, displayName: string) {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.bootstrapAdmin(email, password, displayName)
      localStorage.setItem(TOKEN_KEY, result.access_token)
      setToken(result.access_token)
      setUser(result.user)
      window.location.hash = '/admin'
      setPage('admin')
      await refreshSetupStatus()
      await refreshCore(result.access_token)
      setMessage('管理员账户已创建')
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  function requestRegisterCode(email: string): Promise<EmailCodeResponse> {
    return api.requestRegisterCode(email)
  }

  function navigate(nextPage: AppPage) {
    window.location.hash = `/${nextPage}`
    setPage(nextPage)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken('')
    setUser(null)
    setBalance(null)
    setTransactions([])
    setPackages([])
    setOrders([])
    setJobs([])
    setBatches([])
    setSelectedBatchId(null)
    setSelectedBatchJobs([])
    setPricing([])
    setAdminUsers([])
    setAdminPackages([])
    setSystemSettings([])
    setAdminDashboard(null)
    setSelectedJobId(null)
    setSelectedRawJobId(null)
    setRetryingJobId(null)
    setMessage('已退出')
  }

  async function createJob(payload: JobCreateRequest) {
    if (!token) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setSelectedJobId(job.id)
      navigate('gallery')
      setMessage(`任务 #${job.id} 已入队`)
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createJobs(payloads: JobCreateRequest[], batchName = '', mode = 'mixed') {
    if (!token || payloads.length === 0) return
    setBusy(true)
    setMessage('')
    try {
      const created = await api.createJobsBatch(token, payloads, batchName, mode)
      setSelectedJobId(created.jobs[0]?.id ?? null)
      navigate('packs')
      setMessage(`${created.jobs.length} 个任务已入队，冻结 ${created.total_price_credits} 点。`)
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createRawImageJob(payload: JobCreateRequest) {
    if (!token) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setSelectedRawJobId(job.id)
      setSelectedJobId(job.id)
      setPage('raw-image')
      window.location.hash = '/raw-image'
      setMessage(`原始生图任务 #${job.id} 已入队`)
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createRawImageJobs(payloads: JobCreateRequest[], batchName = '', mode = 'raw_image') {
    if (!token || payloads.length === 0) return
    setBusy(true)
    setMessage('')
    try {
      const created = await api.createJobsBatch(token, payloads, batchName, mode)
      const firstJobId = created.jobs[0]?.id ?? null
      setSelectedRawJobId(firstJobId)
      setSelectedJobId(firstJobId)
      setPage('raw-image')
      window.location.hash = '/raw-image'
      setMessage(`${created.jobs.length} 张原始生图已入队，冻结 ${created.total_price_credits} 点。`)
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function selectBatch(batch: GenerationBatch) {
    if (!token) return
    setSelectedBatchId(batch.id)
    setSelectedBatchJobs(await api.batchJobs(token, batch.id))
    setSelectedJobId(null)
    navigate('packs')
    setMessage(`已筛选素材包：${batch.name}`)
  }

  function clearBatchFilter() {
    setSelectedBatchId(null)
    setSelectedBatchJobs([])
    setSelectedJobId(null)
    setMessage('已显示全部作品')
  }

  async function renameBatch(batch: GenerationBatch) {
    if (!token) return
    const name = window.prompt('新的素材包名称', batch.name)
    if (name === null) return
    const trimmed = name.trim()
    if (!trimmed) {
      setMessage('素材包名称不能为空')
      return
    }
    try {
      await api.updateBatch(token, batch.id, { name: trimmed })
      await refreshCore(token)
      setMessage('素材包已重命名')
    } catch (error) {
      showError(error)
    }
  }

  async function toggleArchiveBatch(batch: GenerationBatch) {
    if (!token) return
    const nextStatus = batch.status === 'archived' ? 'active' : 'archived'
    if (nextStatus === 'archived' && !window.confirm(`归档「${batch.name}」？`)) return
    try {
      await api.updateBatch(token, batch.id, { status: nextStatus })
      await refreshCore(token)
      setMessage(nextStatus === 'archived' ? '素材包已归档' : '素材包已恢复')
    } catch (error) {
      showError(error)
    }
  }

  async function deleteBatch(batch: GenerationBatch) {
    if (!token) return
    if (!window.confirm(`删除空素材包「${batch.name}」？此操作无法撤销。`)) return
    try {
      await api.deleteBatch(token, batch.id)
      if (selectedBatchId === batch.id) clearBatchFilter()
      await refreshCore(token)
      setMessage('素材包已删除')
    } catch (error) {
      showError(error)
    }
  }

  async function downloadBatch(batch: GenerationBatch) {
    if (!token) return
    setDownloadingBatchId(batch.id)
    setMessage('')
    try {
      const blob = await api.downloadBatch(token, batch.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `pix-batch-${batch.id}.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setMessage(`${batch.name} 开始下载`)
    } catch (error) {
      showError(error)
    } finally {
      setDownloadingBatchId(null)
    }
  }

  async function retryJob(job: GenerationJob) {
    if (!token || job.status !== 'failed') return
    if (!window.confirm(`重试任务 #${job.id}？将按当前价格重新冻结点数。`)) return
    setRetryingJobId(job.id)
    setMessage('')
    try {
      const created = await api.retryJob(token, job.id)
      setSelectedJobId(created.id)
      setPage('gallery')
      window.location.hash = '/gallery'
      setMessage(`任务 #${job.id} 已重试，新任务 #${created.id} 已入队。`)
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setRetryingJobId(null)
    }
  }

  async function retryFailedBatch(batch: GenerationBatch) {
    if (!token) return
    if (!window.confirm(`重试「${batch.name}」的 ${batch.failed_count} 个失败项？`)) return
    setRetryingBatchId(batch.id)
    setMessage('')
    try {
      const result = await api.retryFailedBatch(token, batch.id)
      setMessage(`${result.jobs.length} 个失败项已重试，冻结 ${result.total_price_credits} 点。`)
      setSelectedBatchId(batch.id)
      setSelectedBatchJobs(await api.batchJobs(token, batch.id))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setRetryingBatchId(null)
    }
  }

  async function copyPath(path: string) {
    await navigator.clipboard.writeText(path)
    setMessage('输出路径已复制')
  }

  async function pixelizeCandidate(job: GenerationJob, candidate: ContactSheetCandidate) {
    const pixelize = (job.params_json?.pixelize as JobCreateRequest['pixelize'] | undefined) ?? defaultPixelize
    const grid = (job.params_json?.grid as JobCreateRequest['grid'] | undefined) ?? buildGridDesign()
    await createJob({
      job_type: 'local_pixelize',
      prompt: null,
      input_image_path: candidate.path,
      client_request_id: crypto.randomUUID(),
      skip_vl: true,
      pixelize,
      grid,
    })
  }

  async function createPaymentOrder(packageKey: string) {
    if (!token) return
    try {
      const order = await api.createOrder(token, packageKey)
      setCheckout(null)
      await refreshCore(token)
      setMessage(`订单 #${order.id} 已创建`)
    } catch (error) {
      showError(error)
    }
  }

  async function startCheckout(packageKey: string, provider: string) {
    if (!token) return
    try {
      const result = await api.checkout(token, packageKey, provider)
      setCheckout(result)
      if (result.payment_url) {
        window.open(result.payment_url, '_blank', 'noopener,noreferrer')
      }
      await refreshCore(token)
      setMessage(`订单 #${result.order.id} 已创建：${provider}`)
    } catch (error) {
      showError(error)
    }
  }

  async function mockPayPaymentOrder(orderId: number) {
    if (!token) return
    try {
      await api.mockPayOrder(token, orderId)
      await refreshCore(token)
      setMessage('模拟支付成功，点数已到账')
    } catch (error) {
      showError(error)
    }
  }

  async function adjustCredits(userId: number, amount: number, note: string) {
    if (!token) return
    await api.adjustCredits(token, userId, amount, note)
    await refreshCore(token)
    setMessage('点数已调整')
  }

  async function updatePricing(key: string, priceCredits: number, enabled: boolean) {
    if (!token) return
    await api.updatePricing(token, key, priceCredits, enabled)
    await refreshCore(token)
    setMessage('价格规则已更新')
  }

  async function updateSetting(key: string, value: string, clear = false) {
    if (!token) return
    await api.updateSetting(token, key, value, clear)
    await refreshCore(token)
    setMessage('配置已更新')
  }

  async function createAdminPackage(payload: CreditPackage) {
    if (!token) return
    await api.createAdminPackage(token, payload)
    await refreshCore(token)
    setMessage('充值套餐已创建')
  }

  async function updateAdminPackage(key: string, payload: Omit<CreditPackage, 'key'>) {
    if (!token) return
    await api.updateAdminPackage(token, key, payload)
    await refreshCore(token)
    setMessage('充值套餐已更新')
  }

  async function testEmailSetting(email: string) {
    if (!token) return
    const result = await api.testEmailSetting(token, email)
    setMessage(result.debug_code ? `${result.message}：${result.debug_code}` : result.message)
  }

  const needsAdminSetup = setupStatus?.needs_admin && !user

  return (
    <main data-pix-theme={themeMode} className="min-h-screen text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/80 bg-background/88 backdrop-blur-xl">
        <div className="mx-auto grid max-w-[1440px] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 lg:grid-cols-[220px_minmax(0,1fr)_auto] lg:px-8">
          <a href="/" aria-label="返回首页" className="flex min-w-0 items-center gap-3 rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <img src="/pix-logo-64.png" alt="" className="h-10 w-10 shrink-0 [image-rendering:pixelated]" />
            <div className="min-w-0">
              <p className="text-[11px] font-bold uppercase tracking-[.16em] text-muted-foreground">Pix Forge</p>
              <h1 className="truncate text-xl font-black tracking-tight">像素素材工坊</h1>
            </div>
          </a>
          {user && <div className="col-span-2 min-w-0 lg:col-span-1"><AppTabs page={page} user={user} onChange={navigate} /></div>}
          <div className="flex justify-end gap-2">
            <ThemeModeMenu preference={themePreference} resolvedMode={themeMode} systemMode={systemThemeMode} onChange={onThemePreferenceChange} />
            {user ? (
              <AccountMenu user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} isAdmin={isAdmin} onNavigate={navigate} onRefresh={() => refreshCore()} onLogout={logout} />
            ) : (
              <div className="flex gap-2">
                <Button variant="ghost" asChild><a href="#auth-panel">登录</a></Button>
                <Button asChild><a href="#auth-panel">注册</a></Button>
              </div>
            )}
          </div>
        </div>
      </header>

      {setupLoading ? (
        <div className="grid min-h-[calc(100vh-76px)] place-items-center px-4 text-muted-foreground">正在检查站点初始化状态…</div>
      ) : needsAdminSetup && setupStatus ? (
        <SetupWizard status={setupStatus} loading={busy} onBootstrapAdmin={bootstrapAdmin} />
      ) : user ? (
        <div className="mx-auto max-w-[1320px] px-4 py-6 md:px-8 md:py-9">
          <div className="grid gap-6">
            {message && <Alert variant="info" role="status" aria-live="polite">{message}</Alert>}
            {page === 'workspace' && <WorkspacePage mode={mode} pricing={pricing} balance={balance} jobs={jobs} loading={busy} token={token} onModeChange={setMode} onCreateJob={createJob} onCreateJobs={createJobs} onCandidatePixelize={pixelizeCandidate} onRefresh={() => refreshCore()} />}
            {page === 'raw-image' && <RawImagePage pricing={pricing} balance={balance} jobs={jobs} loading={busy} selectedJobId={selectedRawJobId} onSelectJob={setSelectedRawJobId} onCreateJob={createRawImageJob} onCreateJobs={createRawImageJobs} onRefresh={() => refreshCore()} />}
            {page === 'gallery' && <GalleryPage jobs={jobs} selectedJob={selectedJob} selectedJobId={selectedJobId} pricing={pricing} loading={busy} retryingJobId={retryingJobId} onSelectJob={(job) => setSelectedJobId(job.id)} onCopyPath={copyPath} onCandidatePixelize={pixelizeCandidate} onCreateJob={createJob} onRetryJob={retryJob} />}
            {page === 'packs' && <PacksPage batches={batches} selectedBatch={selectedBatch} selectedBatchId={selectedBatchId} selectedBatchJobs={selectedBatchJobs} selectedJobId={selectedJobId} retrying={retryingBatchId !== null} downloading={downloadingBatchId !== null} onSelectBatch={selectBatch} onClearSelection={clearBatchFilter} onRetryFailed={retryFailedBatch} onDownloadBatch={downloadBatch} onRenameBatch={renameBatch} onToggleArchive={toggleArchiveBatch} onDeleteBatch={deleteBatch} onSelectJob={(job) => setSelectedJobId(job.id)} onCopyPath={copyPath} onCandidatePixelize={pixelizeCandidate} onRefresh={() => refreshCore()} />}
            {page === 'billing' && <BillingPage balance={balance} transactions={transactions} packages={packages} orders={orders} checkout={checkout} isAdmin={isAdmin} onRefresh={() => refreshCore()} onCreateOrder={createPaymentOrder} onCheckout={startCheckout} onMockPayOrder={mockPayPaymentOrder} />}
            {page === 'admin' && isAdmin && <AdminPage dashboard={adminDashboard} users={adminUsers} pricing={pricing} packages={adminPackages} settings={systemSettings} onRefresh={() => refreshCore()} onAdjustCredits={adjustCredits} onUpdatePricing={updatePricing} onCreatePackage={createAdminPackage} onUpdatePackage={updateAdminPackage} onUpdateSetting={updateSetting} onTestEmail={testEmailSetting} />}
            <SiteFooter />
          </div>
        </div>
      ) : (
        <div>
          <AppHero user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={batches.length} />
          {message && <div className="mx-auto max-w-6xl px-4 py-3"><Alert variant="info" role="status" aria-live="polite">{message}</Alert></div>}
          <LandingSections authSlot={<AuthPanel user={user} onLogin={login} onRegister={register} onRequestRegisterCode={requestRegisterCode} onLogout={logout} loading={busy} registrationBonusCredits={setupStatus?.registration_bonus_credits ?? 0} />} />
          <SiteFooter />
        </div>
      )}
    </main>
  )
}

function SiteFooter() {
  return (
    <footer className="border-t border-border/70 bg-card/80 px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 text-center text-sm text-muted-foreground">
        <div className="flex items-center gap-2 font-semibold">
          <img src="/pix-logo-64.png" alt="" className="h-6 w-6 opacity-70 [image-rendering:pixelated]" />
          Pix Forge · 像素素材工坊
        </div>
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer" className="text-xs opacity-70 hover:text-foreground hover:opacity-100">鲁ICP备2022023963号</a>
      </div>
    </footer>
  )
}
