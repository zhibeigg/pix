import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { CheckCircle2, CircleAlert, Info, X } from 'lucide-react'
import type { PixLanguage, PixThemeMode, PixThemePreference } from './theme'
import { api, ApiError, TOKEN_KEY } from './api'
import { AppTabs, type AppPage } from './components/AppTabs'
import { AccountMenu } from './components/AccountMenu'
import { AppHero } from './components/AppHero'
import { AuthPanel } from './components/AuthPanel'
import { Button } from './components/ui/button'
import { HeaderUtilityBar } from './components/HeaderUtilityBar'
import { LandingSections } from './components/LandingSections'
import { SetupWizard } from './components/SetupWizard'
import { AdminPage } from './pages/AdminPage'
import { BillingPage } from './pages/BillingPage'
import { GalleryPage } from './pages/GalleryPage'
import { PacksPage } from './pages/PacksPage'
import { RawImagePage } from './pages/RawImagePage'
import { WorkspacePage, type WorkMode } from './pages/WorkspacePage'
import { buildGridDesign, defaultPixelize } from './pixelize'
import { useI18n } from './i18n'
import type { AdminDashboard, ContactSheetCandidate, CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, EmailCodeResponse, GenerationBatch, GenerationJob, JobCreateRequest, PaymentCheckout, PaymentOrder, PricingRule, SetupStatus, SystemSetting, User } from './types'

type ToastVariant = 'success' | 'info' | 'error'
type AppToastState = { id: number; message: string; variant: ToastVariant }

type AppProps = {
  themeMode: PixThemeMode
  themePreference: PixThemePreference
  systemThemeMode: PixThemeMode
  language: PixLanguage
  onThemePreferenceChange: (preference: PixThemePreference) => void
  onLanguageChange: (language: PixLanguage) => void
}

const PHOTO_RETENTION_LIMIT = 10

function pageFromHash(user: User | null): AppPage {
  const raw = window.location.hash.replace(/^#\/?/, '')
  if (!raw || raw === 'home') return 'home'
  const page = ['workspace', 'raw-image', 'gallery', 'packs', 'billing', 'admin'].includes(raw) ? raw as AppPage : 'home'
  if (page === 'admin' && user?.role !== 'admin') return 'workspace'
  return page
}

function retainedPhotoCount(jobs: GenerationJob[]) {
  return jobs.filter((job) => job.status === 'succeeded' && job.outputs.length > 0).length
}

export function App({ themeMode, themePreference, systemThemeMode, language, onThemePreferenceChange, onLanguageChange }: AppProps) {
  const { text, t } = useI18n()
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [user, setUser] = useState<User | null>(null)
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [transactions, setTransactions] = useState<CreditTransaction[]>([])
  const [packages, setPackages] = useState<CreditPackage[]>([])
  const [customRechargeOptions, setCustomRechargeOptions] = useState<CustomRechargeOptions | null>(null)
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
  const [toast, setToast] = useState<AppToastState | null>(null)
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null)
  const [setupLoading, setSetupLoading] = useState(true)
  const [page, setPage] = useState<AppPage>(() => pageFromHash(null))
  const [mode, setMode] = useState<WorkMode>('single')
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null)
  const [selectedBatchJobs, setSelectedBatchJobs] = useState<GenerationJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [selectedRawJobId, setSelectedRawJobId] = useState<number | null>(null)
  const pollFailuresRef = useRef(0)
  const jobStatusSnapshotRef = useRef<Map<number, string>>(new Map())
  const jobStatusSeededRef = useRef(false)

  const isAdmin = user?.role === 'admin'
  const selectedBatch = useMemo(() => batches.find((batch) => batch.id === selectedBatchId) ?? null, [batches, selectedBatchId])
  const selectedJobPool = page === 'packs' && selectedBatchId ? selectedBatchJobs : jobs
  const selectedJob = useMemo(() => selectedJobPool.find((job) => job.id === selectedJobId) ?? null, [selectedJobPool, selectedJobId])
  const retainedPhotos = useMemo(() => retainedPhotoCount(jobs), [jobs])
  const activeJobs = useMemo(() => jobs.filter((job) => ['pending', 'running'].includes(job.status)).length, [jobs])
  const completedJobs = useMemo(() => jobs.filter((job) => job.status === 'succeeded').length, [jobs])
  const failedJobs = useMemo(() => jobs.filter((job) => job.status === 'failed').length, [jobs])

  const dismissToast = useCallback(() => setToast(null), [])
  const setMessage = useCallback((message: string, variant: ToastVariant = 'success') => {
    setToast(message ? { id: Date.now(), message, variant } : null)
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), toast.variant === 'error' ? 5200 : 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  const notifyJobCompletions = useCallback((nextJobs: GenerationJob[]) => {
    const previous = jobStatusSnapshotRef.current
    const completed = jobStatusSeededRef.current
      ? nextJobs.filter((job) => job.status === 'succeeded' && previous.has(job.id) && previous.get(job.id) !== 'succeeded')
      : []
    jobStatusSnapshotRef.current = new Map(nextJobs.map((job) => [job.id, job.status]))
    jobStatusSeededRef.current = true
    if (completed.length === 0) return
    const title = completed.length === 1 ? text('生成完成', 'Generation complete') : text('批量生成完成', 'Batch complete')
    const body = completed.length === 1
      ? text(`任务 #${completed[0].id} 已生成完成。`, `Job #${completed[0].id} has finished generating.`)
      : text(`${completed.length} 个任务已生成完成。`, `${completed.length} jobs have finished generating.`)
    setMessage(body, 'success')
    showSystemNotification(title, body)
  }, [setMessage, text])

  const refreshSetupStatus = useCallback(async () => {
    try {
      setSetupStatus(await api.setupStatus())
    } finally {
      setSetupLoading(false)
    }
  }, [])

  const showError = useCallback((error: unknown) => {
    if (error instanceof ApiError) setMessage(error.message, 'error')
    else if (error instanceof Error) setMessage(error.message, 'error')
    else setMessage(text('发生未知错误', 'Unknown error'), 'error')
  }, [setMessage, text])

  const confirmPhotoRetentionBeforeCreate = useCallback((nextJobCount: number) => {
    const overflow = retainedPhotos + nextJobCount - PHOTO_RETENTION_LIMIT
    if (overflow <= 0) return true
    return window.confirm(text(
      `当前已保留 ${retainedPhotos} 张作品。继续生成后，系统会自动删除最旧的 ${overflow} 张作品，只保留最新 ${PHOTO_RETENTION_LIMIT} 张。是否继续？`,
      `You already keep ${retainedPhotos} works. Continuing will automatically delete the oldest ${overflow} works and keep only the latest ${PHOTO_RETENTION_LIMIT}. Continue?`,
    ))
  }, [retainedPhotos, text])

  const refreshCore = useCallback(async (activeToken = token) => {
    if (!activeToken) return
    const [me, nextBalance, nextTransactions, nextPackages, nextCustomRechargeOptions, nextOrders, nextJobs, nextBatches, nextPricing] = await Promise.all([
      api.me(activeToken),
      api.balance(activeToken),
      api.transactions(activeToken),
      api.packages(),
      api.customRechargeOptions(),
      api.orders(activeToken),
      api.jobs(activeToken),
      api.batches(activeToken),
      api.pricing(activeToken),
    ])
    setUser(me)
    setBalance(nextBalance)
    setTransactions(nextTransactions)
    setPackages(nextPackages)
    setCustomRechargeOptions(nextCustomRechargeOptions)
    setOrders(nextOrders)
    notifyJobCompletions(nextJobs)
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
  }, [notifyJobCompletions, selectedBatchId, token])

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
      const baseDelay = pollFailuresRef.current >= 4 ? 15000 : pollFailuresRef.current >= 2 ? 6000 : 3000
      const delay = document.visibilityState === 'hidden' ? Math.max(baseDelay, 15000) : baseDelay
      timer = window.setTimeout(poll, delay)
      try {
        const [nextJobs, nextBatches, nextBalance, nextOrders] = await Promise.all([
          api.jobs(token),
          api.batches(token),
          api.balance(token),
          api.orders(token),
        ])
        notifyJobCompletions(nextJobs)
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
  }, [notifyJobCompletions, token])

  async function login(email: string, password: string) {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.login(email, password)
      localStorage.setItem(TOKEN_KEY, result.access_token)
      setToken(result.access_token)
      await refreshCore(result.access_token)
      await refreshSetupStatus()
      setMessage(text('登录成功', 'Signed in'))
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function localTestLogin() {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.localTestLogin()
      localStorage.setItem(TOKEN_KEY, result.access_token)
      setToken(result.access_token)
      await refreshCore(result.access_token)
      await refreshSetupStatus()
      setMessage(text('已进入本地测试账号', 'Entered local test account'))
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
      setMessage(text('注册成功', 'Registered successfully'))
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
      setMessage(text('管理员账户已创建', 'Admin account created'))
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
    setMessage(text('已退出', 'Signed out'))
  }

  async function createJob(payload: JobCreateRequest) {
    if (!token) return
    if (!confirmPhotoRetentionBeforeCreate(1)) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setSelectedJobId(job.id)
      navigate('gallery')
      setMessage(text(`任务 #${job.id} 已入队`, `Job #${job.id} queued`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createJobs(payloads: JobCreateRequest[], batchName = '', mode = 'mixed') {
    if (!token || payloads.length === 0) return
    if (!confirmPhotoRetentionBeforeCreate(payloads.length)) return
    setBusy(true)
    setMessage('')
    try {
      const created = await api.createJobsBatch(token, payloads, batchName, mode)
      setSelectedJobId(created.jobs[0]?.id ?? null)
      navigate('packs')
      setMessage(text(`${created.jobs.length} 个任务已入队，冻结 ${created.total_price_credits} 点。`, `${created.jobs.length} jobs queued; ${created.total_price_credits} credits reserved.`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createRawImageJob(payload: JobCreateRequest) {
    if (!token) return
    if (!confirmPhotoRetentionBeforeCreate(1)) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setSelectedRawJobId(job.id)
      setSelectedJobId(job.id)
      setPage('raw-image')
      window.location.hash = '/raw-image'
      setMessage(text(`原始生图任务 #${job.id} 已入队`, `Raw image job #${job.id} queued`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createRawImageJobs(payloads: JobCreateRequest[], batchName = '', mode = 'raw_image') {
    if (!token || payloads.length === 0) return
    if (!confirmPhotoRetentionBeforeCreate(payloads.length)) return
    setBusy(true)
    setMessage('')
    try {
      const created = await api.createJobsBatch(token, payloads, batchName, mode)
      const firstJobId = created.jobs[0]?.id ?? null
      setSelectedRawJobId(firstJobId)
      setSelectedJobId(firstJobId)
      setPage('raw-image')
      window.location.hash = '/raw-image'
      setMessage(text(`${created.jobs.length} 张原始生图已入队，冻结 ${created.total_price_credits} 点。`, `${created.jobs.length} raw images queued; ${created.total_price_credits} credits reserved.`))
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
    setMessage(text(`已筛选素材包：${batch.name}`, `Filtered pack: ${batch.name}`), 'info')
  }

  function clearBatchFilter() {
    setSelectedBatchId(null)
    setSelectedBatchJobs([])
    setSelectedJobId(null)
    setMessage(text('已显示全部作品', 'Showing all works'), 'info')
  }

  async function renameBatch(batch: GenerationBatch) {
    if (!token) return
    const name = window.prompt(text('新的素材包名称', 'New pack name'), batch.name)
    if (name === null) return
    const trimmed = name.trim()
    if (!trimmed) {
      setMessage(text('素材包名称不能为空', 'Pack name cannot be empty'), 'error')
      return
    }
    try {
      await api.updateBatch(token, batch.id, { name: trimmed })
      await refreshCore(token)
      setMessage(text('素材包已重命名', 'Pack renamed'))
    } catch (error) {
      showError(error)
    }
  }

  async function toggleArchiveBatch(batch: GenerationBatch) {
    if (!token) return
    const nextStatus = batch.status === 'archived' ? 'active' : 'archived'
    if (nextStatus === 'archived' && !window.confirm(text(`归档「${batch.name}」？`, `Archive “${batch.name}”?`))) return
    try {
      await api.updateBatch(token, batch.id, { status: nextStatus })
      await refreshCore(token)
      setMessage(nextStatus === 'archived' ? text('素材包已归档', 'Pack archived') : text('素材包已恢复', 'Pack restored'))
    } catch (error) {
      showError(error)
    }
  }

  async function deleteBatch(batch: GenerationBatch) {
    if (!token) return
    if (!window.confirm(text(`删除空素材包「${batch.name}」？此操作无法撤销。`, `Delete empty pack “${batch.name}”? This cannot be undone.`))) return
    try {
      await api.deleteBatch(token, batch.id)
      if (selectedBatchId === batch.id) clearBatchFilter()
      await refreshCore(token)
      setMessage(text('素材包已删除', 'Pack deleted'))
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
      setMessage(text(`${batch.name} 开始下载`, `${batch.name} download started`), 'info')
    } catch (error) {
      showError(error)
    } finally {
      setDownloadingBatchId(null)
    }
  }

  async function retryJob(job: GenerationJob) {
    if (!token || job.status !== 'failed') return
    if (!confirmPhotoRetentionBeforeCreate(1)) return
    if (!window.confirm(text(`重试任务 #${job.id}？将按当前价格重新冻结点数。`, `Retry job #${job.id}? Credits will be reserved at the current price.`))) return
    setRetryingJobId(job.id)
    setMessage('')
    try {
      const created = await api.retryJob(token, job.id)
      setSelectedJobId(created.id)
      setPage('gallery')
      window.location.hash = '/gallery'
      setMessage(text(`任务 #${job.id} 已重试，新任务 #${created.id} 已入队。`, `Job #${job.id} retried; new job #${created.id} queued.`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setRetryingJobId(null)
    }
  }

  async function retryFailedBatch(batch: GenerationBatch) {
    if (!token) return
    if (!confirmPhotoRetentionBeforeCreate(batch.failed_count)) return
    if (!window.confirm(text(`重试「${batch.name}」的 ${batch.failed_count} 个失败项？`, `Retry ${batch.failed_count} failed items in “${batch.name}”?`))) return
    setRetryingBatchId(batch.id)
    setMessage('')
    try {
      const result = await api.retryFailedBatch(token, batch.id)
      setMessage(text(`${result.jobs.length} 个失败项已重试，冻结 ${result.total_price_credits} 点。`, `${result.jobs.length} failed items retried; ${result.total_price_credits} credits reserved.`))
      setSelectedBatchId(batch.id)
      setSelectedBatchJobs(await api.batchJobs(token, batch.id))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setRetryingBatchId(null)
    }
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
      const order = await api.createOrder(token, { package_key: packageKey, provider: 'mock' })
      setCheckout(null)
      await refreshCore(token)
      setMessage(text(`订单 #${order.id} 已创建`, `Order #${order.id} created`))
    } catch (error) {
      showError(error)
    }
  }

  async function startCheckout(packageKey: string, provider: string) {
    if (!token) return
    try {
      const result = await api.checkout(token, { package_key: packageKey, provider })
      setCheckout(result)
      if (result.payment_url) {
        window.open(result.payment_url, '_blank', 'noopener,noreferrer')
      }
      await refreshCore(token)
      setMessage(text(`订单 #${result.order.id} 已创建：${provider}`, `Order #${result.order.id} created: ${provider}`))
    } catch (error) {
      showError(error)
    }
  }

  async function createCustomPaymentOrder(customCredits: number) {
    if (!token) return
    try {
      const order = await api.createOrder(token, { custom_credits: customCredits, provider: 'mock' })
      setCheckout(null)
      await refreshCore(token)
      setMessage(text(`自定义订单 #${order.id} 已创建`, `Custom order #${order.id} created`))
    } catch (error) {
      showError(error)
    }
  }

  async function startCustomCheckout(customCredits: number, provider: string) {
    if (!token) return
    try {
      const result = await api.checkout(token, { custom_credits: customCredits, provider })
      setCheckout(result)
      if (result.payment_url) {
        window.open(result.payment_url, '_blank', 'noopener,noreferrer')
      }
      await refreshCore(token)
      setMessage(text(`自定义订单 #${result.order.id} 已创建：${provider}`, `Custom order #${result.order.id} created: ${provider}`))
    } catch (error) {
      showError(error)
    }
  }

  async function mockPayPaymentOrder(orderId: number) {
    if (!token) return
    try {
      await api.mockPayOrder(token, orderId)
      await refreshCore(token)
      setMessage(text('模拟支付成功，点数已到账', 'Mock payment succeeded; credits received'))
    } catch (error) {
      showError(error)
    }
  }

  async function adjustCredits(userId: number, amount: number, note: string) {
    if (!token) return
    await api.adjustCredits(token, userId, amount, note)
    await refreshCore(token)
    setMessage(text('点数已调整', 'Credits adjusted'))
  }

  async function updatePricing(key: string, priceCredits: number, enabled: boolean) {
    if (!token) return
    await api.updatePricing(token, key, priceCredits, enabled)
    await refreshCore(token)
    setMessage(text('价格规则已更新', 'Pricing rule updated'))
  }

  async function updateSetting(key: string, value: string, clear = false) {
    if (!token) return
    await api.updateSetting(token, key, value, clear)
    await refreshCore(token)
    setMessage(text('配置已更新', 'Settings updated'))
  }

  async function createAdminPackage(payload: CreditPackage) {
    if (!token) return
    await api.createAdminPackage(token, payload)
    await refreshCore(token)
    setMessage(text('充值套餐已创建', 'Credit package created'))
  }

  async function updateAdminPackage(key: string, payload: Omit<CreditPackage, 'key'>) {
    if (!token) return
    await api.updateAdminPackage(token, key, payload)
    await refreshCore(token)
    setMessage(text('充值套餐已更新', 'Credit package updated'))
  }

  async function testEmailSetting(email: string) {
    if (!token) return
    const result = await api.testEmailSetting(token, email)
    setMessage(result.debug_code ? `${result.message}：${result.debug_code}` : result.message, 'info')
  }

  const needsAdminSetup = setupStatus?.needs_admin && !user

  return (
    <main data-pix-theme={themeMode} className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur-xl dark:border-white/10 dark:bg-[hsl(var(--pix-navy-deep)/.95)]">
        <div className="mx-auto grid min-h-16 max-w-7xl grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 lg:grid-cols-[220px_minmax(0,1fr)_auto] lg:px-8">
          <a href="#/home" aria-label={t('app.backHome')} className="flex min-w-0 items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <img src="/pix-logo-64.png" alt="" className="h-9 w-9 shrink-0 [image-rendering:pixelated]" />
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-muted-foreground">Pix Forge</p>
              <h1 className="truncate text-xl font-semibold tracking-tight">{t('app.title')}</h1>
            </div>
          </a>
          {user && <div className="hidden min-w-0 lg:block" aria-hidden="true" />}
          <div className="flex justify-end gap-2">
            <HeaderUtilityBar language={language} themePreference={themePreference} resolvedMode={themeMode} systemMode={systemThemeMode} onLanguageChange={onLanguageChange} onThemePreferenceChange={onThemePreferenceChange} />
            {user ? (
              <>
                {page === 'home' && <Button asChild><a href="#/workspace">{t('app.workbench')}</a></Button>}
                <AccountMenu user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} isAdmin={isAdmin} onNavigate={navigate} onRefresh={() => refreshCore()} onLogout={logout} />
              </>
            ) : (
              <div className="flex gap-2">
                <Button variant="ghost" asChild><a href="#auth-panel">{t('app.signIn')}</a></Button>
                <Button asChild><a href="#auth-panel">{t('app.register')}</a></Button>
              </div>
            )}
          </div>
        </div>
      </header>

      <AppToast toast={toast} onDismiss={dismissToast} />

      {setupLoading ? (
        <div className="grid min-h-[calc(100vh-76px)] place-items-center px-4 text-muted-foreground">{t('app.checkingSetup')}</div>
      ) : needsAdminSetup && setupStatus ? (
        <SetupWizard status={setupStatus} loading={busy} onBootstrapAdmin={bootstrapAdmin} onLocalTestLogin={localTestLogin} />
      ) : user && page !== 'home' ? (
        <WorkspaceShell
          page={page}
          user={user}
          balance={balance}
          activeJobs={activeJobs}
          completedJobs={completedJobs}
          failedJobs={failedJobs}
          isAdmin={isAdmin}
          onNavigate={navigate}
        >
          {page === 'workspace' && <WorkspacePage mode={mode} pricing={pricing} balance={balance} jobs={jobs} loading={busy} token={token} onModeChange={setMode} onCreateJob={createJob} onCreateJobs={createJobs} onCandidatePixelize={pixelizeCandidate} onRefresh={() => refreshCore()} />}
          {page === 'raw-image' && <RawImagePage pricing={pricing} balance={balance} jobs={jobs} loading={busy} selectedJobId={selectedRawJobId} onSelectJob={setSelectedRawJobId} onCreateJob={createRawImageJob} onCreateJobs={createRawImageJobs} onRefresh={() => refreshCore()} />}
          {page === 'gallery' && <GalleryPage jobs={jobs} selectedJob={selectedJob} selectedJobId={selectedJobId} pricing={pricing} loading={busy} retryingJobId={retryingJobId} onSelectJob={(job) => setSelectedJobId(job.id)} onCandidatePixelize={pixelizeCandidate} onCreateJob={createJob} onRetryJob={retryJob} />}
          {page === 'packs' && <PacksPage batches={batches} selectedBatch={selectedBatch} selectedBatchId={selectedBatchId} selectedBatchJobs={selectedBatchJobs} selectedJobId={selectedJobId} retrying={retryingBatchId !== null} downloading={downloadingBatchId !== null} onSelectBatch={selectBatch} onClearSelection={clearBatchFilter} onRetryFailed={retryFailedBatch} onDownloadBatch={downloadBatch} onRenameBatch={renameBatch} onToggleArchive={toggleArchiveBatch} onDeleteBatch={deleteBatch} onSelectJob={(job) => setSelectedJobId(job.id)} onCandidatePixelize={pixelizeCandidate} onRefresh={() => refreshCore()} />}
          {page === 'billing' && <BillingPage balance={balance} transactions={transactions} packages={packages} customRechargeOptions={customRechargeOptions} orders={orders} checkout={checkout} isAdmin={isAdmin} onRefresh={() => refreshCore()} onCreateOrder={createPaymentOrder} onCheckout={startCheckout} onCreateCustomOrder={createCustomPaymentOrder} onCustomCheckout={startCustomCheckout} onMockPayOrder={mockPayPaymentOrder} />}
          {page === 'admin' && isAdmin && <AdminPage dashboard={adminDashboard} users={adminUsers} pricing={pricing} packages={adminPackages} settings={systemSettings} onRefresh={() => refreshCore()} onAdjustCredits={adjustCredits} onUpdatePricing={updatePricing} onCreatePackage={createAdminPackage} onUpdatePackage={updateAdminPackage} onUpdateSetting={updateSetting} onTestEmail={testEmailSetting} />}
        </WorkspaceShell>
      ) : (
        <div>
          <AppHero user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={batches.length} />
          <LandingSections authSlot={<AuthPanel user={user} onLogin={login} onRegister={register} onRequestRegisterCode={requestRegisterCode} onLocalTestLogin={localTestLogin} onLogout={logout} loading={busy} registrationBonusCredits={setupStatus?.registration_bonus_credits ?? 0} localTestLoginAvailable={setupStatus?.local_test_login_available ?? false} localTestAccountEmail={setupStatus?.local_test_account_email ?? null} />} />
          <SiteFooter />
        </div>
      )}
    </main>
  )
}

function showSystemNotification(title: string, body: string) {
  if (typeof window === 'undefined' || !('Notification' in window)) return
  const options: NotificationOptions = { body, icon: '/pix-logo-64.png', tag: 'pix-generation-complete' }
  if (Notification.permission === 'granted') {
    new Notification(title, options)
    return
  }
  if (Notification.permission === 'default') {
    void Notification.requestPermission().then((permission) => {
      if (permission === 'granted') new Notification(title, options)
    }).catch(() => undefined)
  }
}

function AppToast({ toast, onDismiss }: { toast: AppToastState | null; onDismiss: () => void }) {
  const { t } = useI18n()
  if (!toast) return null
  const Icon = toast.variant === 'error' ? CircleAlert : toast.variant === 'info' ? Info : CheckCircle2
  const tone = toast.variant === 'error'
    ? 'border-destructive/35 bg-destructive text-destructive-foreground dark:border-red-400/30 dark:bg-red-950 dark:text-red-100'
    : toast.variant === 'info'
      ? 'border-[hsl(var(--pix-link-blue))]/30 bg-[hsl(var(--pix-sky))] text-[hsl(var(--pix-navy))] dark:border-sky-300/25 dark:bg-[hsl(var(--pix-navy-deep))] dark:text-sky-100'
      : 'border-[hsl(var(--pix-brand-green))]/30 bg-[hsl(var(--pix-mint))] text-[hsl(var(--pix-navy))] dark:border-emerald-300/25 dark:bg-[hsl(var(--pix-navy-deep))] dark:text-emerald-100'
  const iconTone = toast.variant === 'error' ? 'text-red-100 dark:text-red-200' : toast.variant === 'info' ? 'text-[hsl(var(--pix-link-blue))] dark:text-sky-200' : 'text-emerald-700 dark:text-emerald-200'

  return (
    <div className="pointer-events-none fixed left-1/2 top-5 z-[100] w-[min(calc(100vw-32px),420px)] -translate-x-1/2 px-0">
      <div key={toast.id} role="status" aria-live="polite" className={`pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 text-sm font-medium shadow-[0_16px_48px_-8px_rgba(15,15,15,0.26)] ring-1 ring-black/5 animate-in fade-in slide-in-from-top-2 duration-200 ${tone}`}>
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconTone}`} />
        <p className="min-w-0 flex-1 leading-6">{toast.message}</p>
        <button type="button" onClick={onDismiss} aria-label={t('app.toastDismiss')} className="-mr-1 rounded-md p-1 opacity-72 transition hover:bg-black/5 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/10">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

function WorkspaceShell({ page, user, balance, activeJobs, completedJobs, failedJobs, isAdmin, children, onNavigate }: { page: AppPage; user: User; balance: CreditBalance | null; activeJobs: number; completedJobs: number; failedJobs: number; isAdmin: boolean; children: ReactNode; onNavigate: (page: AppPage) => void }) {
  const { t } = useI18n()
  return (
    <div className="grid min-h-[calc(100vh-65px)] bg-[hsl(var(--pix-cream)/.42)] lg:grid-cols-[260px_minmax(0,1fr)] dark:bg-[hsl(var(--pix-navy-deep))]">
      <aside className="border-b border-border bg-[hsl(var(--pix-paper-soft))] p-4 text-[hsl(var(--pix-ink))] lg:border-b-0 lg:border-r dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band))] dark:text-white">
        <div className="grid gap-6 lg:sticky lg:top-20 lg:min-h-[calc(100vh-97px)] lg:grid-rows-[auto_auto_1fr_auto]">
          <div>
            <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-[hsl(var(--pix-steel))] dark:text-white/58">{t('sidebar.workspace')}</p>
            <div className="mt-3 rounded-md border border-border bg-card p-3 shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))] dark:shadow-[0_18px_48px_-36px_rgba(0,0,0,0.85)]">
              <p className="truncate text-sm font-semibold">{user.display_name || user.email}</p>
              <p className="mt-1 truncate text-xs text-muted-foreground dark:text-white/45">{user.email}</p>
            </div>
          </div>
          <AppTabs page={page} user={user} onChange={onNavigate} orientation="side" />
          <div className="hidden lg:block" />
          <div className="grid grid-cols-3 gap-2 lg:grid-cols-1">
            <SidebarMetric label={t('sidebar.credits')} value={balance?.available_credits ?? '—'} />
            <SidebarMetric label={t('sidebar.queue')} value={activeJobs} />
            <SidebarMetric label={t('sidebar.done')} value={completedJobs} />
            {failedJobs > 0 && <SidebarMetric label={t('sidebar.failed')} value={failedJobs} tone="danger" />}
            {isAdmin && <SidebarMetric label={t('sidebar.role')} value={t('sidebar.admin')} />}
          </div>
        </div>
      </aside>
      <section className="min-w-0 bg-[linear-gradient(180deg,hsl(var(--pix-paper))_0%,hsl(var(--background))_36rem)] px-4 py-5 md:px-8 md:py-8 dark:bg-[linear-gradient(180deg,hsl(var(--pix-navy))_0%,hsl(var(--pix-navy-deep))_42rem)]">
        <div className="grid w-full gap-6">
          <div className="block lg:hidden">
            <AppTabs page={page} user={user} onChange={onNavigate} />
          </div>
          {children}
        </div>
      </section>
    </div>
  )
}

function SidebarMetric({ label, value, tone = 'default' }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'danger' }) {
  return (
    <div className={`rounded-md border px-3 py-2 shadow-[0_1px_2px_rgba(15,15,15,0.04)] ${tone === 'danger' ? 'border-red-200 bg-red-50 text-red-950 dark:border-red-300/30 dark:bg-red-500/10 dark:text-white' : 'border-border bg-card text-[hsl(var(--pix-ink))] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white'}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground dark:text-white/52">{label}</p>
      <p className="mt-1 text-lg font-semibold leading-tight">{value}</p>
    </div>
  )
}

function SiteFooter() {
  const { t } = useI18n()
  const groups = [
    { title: t('footer.product'), links: [t('footer.productionWorkspace'), t('footer.gallery'), t('footer.packs')] },
    { title: t('footer.resources'), links: [t('footer.pixelUi'), t('footer.spriteFrames'), t('footer.sampleAtlas')] },
    { title: t('footer.workspace'), links: [t('footer.billingCenter'), t('footer.jobQueue'), t('footer.batchExport')] },
    { title: t('footer.company'), links: [t('footer.pixForge'), t('footer.gameAssets')] },
  ]
  return (
    <footer className="border-t border-border bg-card px-4 py-16 md:px-8 dark:border-white/10 dark:bg-[hsl(var(--pix-navy-deep))]">
      <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-[1.2fr_2fr]">
        <div>
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <img src="/pix-logo-64.png" alt="" className="h-7 w-7 opacity-80 [image-rendering:pixelated]" />
            {t('footer.brand')}
          </div>
          <p className="mt-4 max-w-sm text-sm leading-6 text-muted-foreground">{t('footer.description')}</p>
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer" className="mt-4 inline-flex text-xs text-muted-foreground hover:text-foreground">鲁ICP备2022023963号</a>
        </div>
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {groups.map((group) => (
            <div key={group.title}>
              <p className="text-sm font-semibold text-foreground">{group.title}</p>
              <div className="mt-3 grid gap-2">
                {group.links.map((link) => <span key={link} className="text-sm text-muted-foreground">{link}</span>)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </footer>
  )
}
