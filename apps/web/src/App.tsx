import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { PixLanguage, PixThemeMode, PixThemePreference } from './theme'
import { api, ApiError, TOKEN_KEY } from './api'
import { AppTabs, type AppPage } from './components/AppTabs'
import { AccountMenu } from './components/AccountMenu'
import { AppHero } from './components/AppHero'
import { AppToast, DeleteConfirmDialog, GalleryExpandConfirmDialog, PackExpandConfirmDialog, showSystemNotification, SiteFooter, WorkspaceShell, type AppToastState, type DeleteConfirmState, type GalleryExpandConfirmState, type PackExpandConfirmState, type ToastVariant } from './components/AppOverlays'
import { AuthPanel } from './components/AuthPanel'
import { useConfirm } from './components/ConfirmDialog'
import { Button } from './components/ui/button'
import { HeaderUtilityBar } from './components/HeaderUtilityBar'
import { LandingSections } from './components/LandingSections'
import { NotFoundPage } from './components/NotFoundPage'
import { SetupWizard } from './components/SetupWizard'
import { GalleryPage } from './pages/GalleryPage'
import { WorkspacePage, type WorkMode } from './pages/WorkspacePage'

const AdminPage = lazy(() => import('./pages/AdminPage').then((m) => ({ default: m.AdminPage })))
const BillingPage = lazy(() => import('./pages/BillingPage').then((m) => ({ default: m.BillingPage })))
const PacksPage = lazy(() => import('./pages/PacksPage').then((m) => ({ default: m.PacksPage })))
const RawImagePage = lazy(() => import('./pages/RawImagePage').then((m) => ({ default: m.RawImagePage })))
const RewardsPage = lazy(() => import('./pages/RewardsPage').then((m) => ({ default: m.RewardsPage })))
import { buildGridDesign, defaultPixelize } from './pixelize'
import { useI18n } from './i18n'
import { useToast } from './hooks/useToast'
import { useHashRoute } from './hooks/useHashRoute'
import { useReferralCode, LEGACY_REFERRAL_CODE_KEY } from './hooks/useReferralCode'
import { useBillingActions } from './hooks/useBillingActions'
import { useAdminActions } from './hooks/useAdminActions'
import { applyPageSeo } from './lib/seo'
import type { AdminDashboard, AnnouncementPublishPayload, AnnouncementPublishResponse, AssetPack, AssetPackQuota, ContactSheetCandidate, CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, EmailCodeResponse, GalleryQuota, GenerationJob, ImageModelsResponse, JobCreateRequest, PaymentCheckout, PaymentOrder, PricingRule, SequenceAlignmentRequest, SetupStatus, SystemSetting, User } from './types'

type AppProps = {
  themeMode: PixThemeMode
  themePreference: PixThemePreference
  systemThemeMode: PixThemeMode
  language: PixLanguage
  onThemePreferenceChange: (preference: PixThemePreference) => void
  onLanguageChange: (language: PixLanguage) => void
}

const DEFAULT_PHOTO_RETENTION_LIMIT = 10

type PaymentReturnInfo = { provider: string; status: string; orderId: string }

function paymentReturnFromHash(): PaymentReturnInfo | null {
  if (typeof window === 'undefined') return null
  const hash = window.location.hash || ''
  const queryIndex = hash.indexOf('?')
  if (queryIndex < 0) return null
  const params = new URLSearchParams(hash.slice(queryIndex + 1))
  const provider = params.get('payment') ?? ''
  if (!provider) return null
  return { provider, status: params.get('status') ?? '', orderId: params.get('order_id') ?? '' }
}

function clearPaymentReturnHash() {
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/billing`)
}

function retainedPhotoCount(jobs: GenerationJob[]) {
  return jobs.filter((job) => job.status === 'succeeded' && job.outputs.length > 0).length
}

export function App({ themeMode, themePreference, systemThemeMode, language, onThemePreferenceChange, onLanguageChange }: AppProps) {
  const { text, t } = useI18n()
  const confirm = useConfirm()
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
  const [packs, setPacks] = useState<AssetPack[]>([])
  const [packQuota, setPackQuota] = useState<AssetPackQuota | null>(null)
  const [galleryQuota, setGalleryQuota] = useState<GalleryQuota | null>(null)
  const [packExpandConfirm, setPackExpandConfirm] = useState<PackExpandConfirmState | null>(null)
  const [galleryExpandConfirm, setGalleryExpandConfirm] = useState<GalleryExpandConfirmState | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<DeleteConfirmState | null>(null)
  const [expandingPackLimit, setExpandingPackLimit] = useState(false)
  const [expandingGalleryQuota, setExpandingGalleryQuota] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [pricing, setPricing] = useState<PricingRule[]>([])
  const [imageModels, setImageModels] = useState<ImageModelsResponse>({ default: 'image2', models: ['image2'], items: [] })
  const [adminUsers, setAdminUsers] = useState<User[]>([])
  const [adminJobs, setAdminJobs] = useState<GenerationJob[]>([])
  const [systemSettings, setSystemSettings] = useState<SystemSetting[]>([])
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null)
  const [busy, setBusy] = useState(false)
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null)
  const [downloadingPackId, setDownloadingPackId] = useState<number | null>(null)
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null)
  const [setupLoading, setSetupLoading] = useState(true)
  const [mode, setMode] = useState<WorkMode>('single')
  const [selectedPackId, setSelectedPackId] = useState<number | null>(null)
  const [selectedPackJobs, setSelectedPackJobs] = useState<GenerationJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [selectedRawJobId, setSelectedRawJobId] = useState<number | null>(null)
  const pollFailuresRef = useRef(0)
  const handledPaymentReturnRef = useRef('')
  const jobStatusSnapshotRef = useRef<Map<number, string>>(new Map())
  const jobStatusSeededRef = useRef(false)
  const pollSigRef = useRef('')

  const { toast, setMessage, showError, dismissToast } = useToast(text)
  const { page, setPage, navigate } = useHashRoute(user, language)
  const { referralCode, setReferralCode } = useReferralCode()

  const isAdmin = user?.role === 'admin'
  const selectedPack = useMemo(() => packs.find((pack) => pack.id === selectedPackId) ?? null, [packs, selectedPackId])
  const selectedJobPool = page === 'packs' && selectedPackId ? selectedPackJobs : jobs
  const selectedJob = useMemo(() => selectedJobPool.find((job) => job.id === selectedJobId) ?? null, [selectedJobPool, selectedJobId])
  const retainedPhotos = useMemo(() => retainedPhotoCount(jobs), [jobs])
  const galleryRetentionLimit = galleryQuota?.retained_limit ?? DEFAULT_PHOTO_RETENTION_LIMIT
  const activeJobs = useMemo(() => jobs.filter((job) => ['pending', 'running'].includes(job.status)).length, [jobs])
  const completedJobs = useMemo(() => jobs.filter((job) => job.status === 'succeeded').length, [jobs])
  const failedJobs = useMemo(() => jobs.filter((job) => job.status === 'failed').length, [jobs])

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

  const confirmPhotoRetentionBeforeCreate = useCallback((nextJobCount: number) => {
    const overflow = retainedPhotos + nextJobCount - galleryRetentionLimit
    if (overflow <= 0) return Promise.resolve(true)
    return confirm({
      title: text('作品库将自动清理', 'Gallery will auto-clean'),
      description: text(
        `当前已保留 ${retainedPhotos} 张作品。继续生成后，系统会自动删除最旧的 ${overflow} 张作品，只保留最新 ${galleryRetentionLimit} 张。是否继续？`,
        `You already keep ${retainedPhotos} works. Continuing will automatically delete the oldest ${overflow} works and keep only the latest ${galleryRetentionLimit}. Continue?`,
      ),
      confirmText: text('继续生成', 'Continue'),
    })
  }, [confirm, galleryRetentionLimit, retainedPhotos, text])

  const refreshCore = useCallback(async (activeToken = token) => {
    if (!activeToken) return
    const [me, nextBalance, nextTransactions, nextPackages, nextCustomRechargeOptions, nextOrders, nextJobs, nextGalleryQuota, nextPacks, nextPackQuota, nextPricing, nextImageModels] = await Promise.all([
      api.me(activeToken),
      api.balance(activeToken),
      api.transactions(activeToken),
      api.packages(),
      api.customRechargeOptions(),
      api.orders(activeToken),
      api.jobs(activeToken),
      api.galleryQuota(activeToken),
      api.packs(activeToken),
      api.packQuota(activeToken),
      api.pricing(activeToken),
      api.imageModels().catch(() => ({ default: 'image2', models: ['image2'], items: [] })),
    ])
    setUser(me)
    setBalance(nextBalance)
    setTransactions(nextTransactions)
    setPackages(nextPackages)
    setCustomRechargeOptions(nextCustomRechargeOptions)
    setOrders(nextOrders)
    notifyJobCompletions(nextJobs)
    setJobs(nextJobs)
    setGalleryQuota(nextGalleryQuota)
    setPacks(nextPacks)
    setPackQuota(nextPackQuota)
    setPricing(nextPricing)
    setImageModels(nextImageModels)
    if (selectedPackId) {
      setSelectedPackJobs(await api.packJobs(activeToken, selectedPackId))
    }
    if (me.role === 'admin') {
      const [users, settings, dashboard, nextAdminPackages, nextAdminJobs] = await Promise.all([
        api.adminUsers(activeToken),
        api.adminSettings(activeToken),
        api.adminDashboard(activeToken),
        api.adminPackages(activeToken),
        api.adminJobs(activeToken),
      ])
      setAdminUsers(users)
      setSystemSettings(settings)
      setAdminDashboard(dashboard)
      setAdminPackages(nextAdminPackages)
      setAdminJobs(nextAdminJobs)
    }
  }, [notifyJobCompletions, selectedPackId, token])

  const refreshCurrent = useCallback(() => { void refreshCore() }, [refreshCore])
  const selectJobById = useCallback((job: GenerationJob) => { setSelectedJobId(job.id) }, [])
  const cancelPackExpand = useCallback(() => { setPackExpandConfirm(null) }, [])
  const cancelGalleryExpand = useCallback(() => { setGalleryExpandConfirm(null) }, [])
  const cancelDelete = useCallback(() => { setDeleteConfirm(null) }, [])
  const confirmPackExpand = useCallback(() => { void confirmExpandPackLimit() }, [confirmExpandPackLimit])
  const confirmGalleryExpand = useCallback(() => { void confirmExpandGalleryQuota() }, [confirmExpandGalleryQuota])
  const confirmDeleteAction = useCallback(() => { void confirmDelete() }, [confirmDelete])

  const { createPaymentOrder, startCheckout, createCustomPaymentOrder, startCustomCheckout, mockPayPaymentOrder, createAdminPackage, updateAdminPackage } = useBillingActions({ token, refreshCore, setMessage, showError, text, setCheckout })
  const { adjustCredits, adjustCreditsBatch, updatePricing, updateSetting, testEmailSetting, adminRetryJob, adminCancelJob, adminFailRefundJob, publishAnnouncement, adminAnnouncements, createAnnouncement, updateAnnouncement, deleteAnnouncement, testAnnouncementEmail, listProviders, listProviderPresets, createProvider, updateProvider, deleteProvider } = useAdminActions({ token, refreshCore, setMessage, text })

  useEffect(() => {
    refreshSetupStatus().catch(showError)
  }, [refreshSetupStatus, showError])

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
    const returned = paymentReturnFromHash()
    if (page !== 'billing' || !returned) return
    const key = `${returned.provider}:${returned.orderId}:${returned.status}`
    if (handledPaymentReturnRef.current === key) return
    handledPaymentReturnRef.current = key
    if (token) void refreshCore(token).catch(showError)
    setMessage(
      returned.orderId
        ? text(`已返回充值页，正在刷新订单 #${returned.orderId} 状态。`, `Returned to billing; refreshing order #${returned.orderId}.`)
        : text('已返回充值页，正在刷新订单状态。', 'Returned to billing; refreshing order status.'),
      'info',
    )
    clearPaymentReturnHash()
  }, [page, refreshCore, setMessage, showError, text, token])

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
        const [nextJobs, nextGalleryQuota, nextPacks, nextPackQuota, nextBalance] = await Promise.all([
          api.jobs(token),
          api.galleryQuota(token),
          api.packs(token),
          api.packQuota(token),
          api.balance(token),
        ])
        // 轮询签名：仅在 jobs/packs/balance/quota 实际变化时提交，稳定期完全不 setState、不触发重渲染。
        // orders 变动低频，已移出 3 秒轮询，由 refreshCore（登录 / 写操作 / 支付返回）按需刷新。
        const sig = JSON.stringify([
          nextJobs.map((job) => [job.id, job.status, job.outputs?.length ?? 0, job.error_message ?? '']),
          nextPacks.map((pack) => [pack.id, pack.status, pack.item_count]),
          nextBalance?.available_credits, nextBalance?.reserved_credits,
          nextGalleryQuota?.retained_count, nextGalleryQuota?.retained_limit,
          nextPackQuota?.pack_count, nextPackQuota?.pack_limit,
        ])
        if (sig !== pollSigRef.current) {
          pollSigRef.current = sig
          notifyJobCompletions(nextJobs)
          setJobs(nextJobs)
          setGalleryQuota(nextGalleryQuota)
          setPacks(nextPacks)
          setPackQuota(nextPackQuota)
          setBalance(nextBalance)
        }
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

  async function requestResetCode(email: string, turnstileToken: string) {
    return api.requestResetCode(email, turnstileToken)
  }

  async function resetAndLogin(email: string, newPassword: string, verificationCode: string) {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.resetPassword(email, newPassword, verificationCode)
      localStorage.setItem(TOKEN_KEY, result.access_token)
      setToken(result.access_token)
      await refreshCore(result.access_token)
      await refreshSetupStatus()
      setMessage(text('密码重置成功，已自动登录', 'Password reset successfully. Logged in automatically.'))
    } catch (error) {
      showError(error)
      throw error
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

  async function register(email: string, password: string, displayName: string, verificationCode: string, nextReferralCode = referralCode) {
    setBusy(true)
    setMessage('')
    try {
      await api.register(email, password, displayName, verificationCode, nextReferralCode)
      try { localStorage.removeItem(LEGACY_REFERRAL_CODE_KEY) } catch { /* ignore */ }
      setReferralCode('')
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

  function requestRegisterCode(email: string, turnstileToken: string): Promise<EmailCodeResponse> {
    return api.requestRegisterCode(email, turnstileToken)
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
    setPacks([])
    setPackQuota(null)
    setGalleryQuota(null)
    setSelectedPackId(null)
    setSelectedPackJobs([])
    setPricing([])
    setAdminUsers([])
    setAdminJobs([])
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
    if (!(await confirmPhotoRetentionBeforeCreate(1))) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setSelectedJobId(job.id)
      navigate('gallery')
      setMessage(text(`任务 #${job.id} 已提交，空闲时会立即生成`, `Job #${job.id} submitted and will run as soon as a slot is free`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createJobs(payloads: JobCreateRequest[], batchName = '', mode = 'mixed') {
    if (!token || payloads.length === 0) return
    if (!(await confirmPhotoRetentionBeforeCreate(payloads.length))) return
    setBusy(true)
    setMessage('')
    try {
      const created = await api.createJobsBatch(token, payloads, batchName, mode)
      setSelectedJobId(created.jobs[0]?.id ?? null)
      navigate('gallery')
      setMessage(text(`${created.jobs.length} 个任务已提交到作品库，空闲槽位会并发生成，冻结 ${created.total_price_credits} 点。`, `${created.jobs.length} jobs submitted to the gallery; free slots will run concurrently; ${created.total_price_credits} credits reserved.`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createRawImageJob(payload: JobCreateRequest) {
    if (!token) return
    if (!(await confirmPhotoRetentionBeforeCreate(1))) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setSelectedRawJobId(job.id)
      setSelectedJobId(job.id)
      setPage('raw-image')
      window.location.hash = '/raw-image'
      setMessage(text(`原始生图任务 #${job.id} 已提交，空闲时会立即生成`, `Raw image job #${job.id} submitted and will run as soon as a slot is free`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function createPack(name: string) {
    if (!token) return
    try {
      const pack = await api.createPack(token, name)
      setSelectedPackId(pack.id)
      setSelectedPackJobs([])
      await refreshCore(token)
      setMessage(text('素材包已创建', 'Pack created'))
    } catch (error) {
      showError(error)
    }
  }

  async function selectPack(pack: AssetPack) {
    if (!token) return
    setSelectedPackId(pack.id)
    setSelectedPackJobs(await api.packJobs(token, pack.id))
    setSelectedJobId(null)
    navigate('packs')
    setMessage(text(`已打开素材包：${pack.name}`, `Opened pack: ${pack.name}`), 'info')
  }

  function clearPackSelection() {
    setSelectedPackId(null)
    setSelectedPackJobs([])
    setSelectedJobId(null)
    setMessage(text('已取消素材包选择', 'Pack selection cleared'), 'info')
  }

  async function renamePack(pack: AssetPack, name: string) {
    if (!token) return
    const trimmed = name.trim()
    if (!trimmed) {
      setMessage(text('素材包名称不能为空', 'Pack name cannot be empty'), 'error')
      return
    }
    try {
      await api.updatePack(token, pack.id, { name: trimmed })
      await refreshCore(token)
      setMessage(text('素材包已重命名', 'Pack renamed'))
    } catch (error) {
      showError(error)
    }
  }

  async function toggleArchivePack(pack: AssetPack) {
    if (!token) return
    const nextStatus = pack.status === 'archived' ? 'active' : 'archived'
    if (nextStatus === 'archived' && !(await confirm({ title: text('归档素材包', 'Archive pack'), description: text(`归档「${pack.name}」？`, `Archive “${pack.name}”?`), confirmText: text('归档', 'Archive') }))) return
    try {
      await api.updatePack(token, pack.id, { status: nextStatus })
      await refreshCore(token)
      setMessage(nextStatus === 'archived' ? text('素材包已归档', 'Pack archived') : text('素材包已恢复', 'Pack restored'))
    } catch (error) {
      showError(error)
    }
  }

  function deletePack(pack: AssetPack) {
    if (!token) return
    setDeleteConfirm({ kind: 'pack', pack })
  }

  async function downloadPack(pack: AssetPack) {
    if (!token) return
    setDownloadingPackId(pack.id)
    setMessage('')
    try {
      const blob = await api.downloadPack(token, pack.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `pix-pack-${pack.id}.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setMessage(text(`${pack.name} 开始下载`, `${pack.name} download started`), 'info')
    } catch (error) {
      showError(error)
    } finally {
      setDownloadingPackId(null)
    }
  }

  function expandPackLimit() {
    if (!token) return
    const price = packQuota?.expand_price_credits ?? 99
    const currentLimit = packQuota?.pack_limit ?? Math.max(1, packs.length)
    setPackExpandConfirm({
      price,
      currentCount: packQuota?.pack_count ?? packs.length,
      currentLimit,
      nextLimit: currentLimit + 1,
      availableCredits: balance?.available_credits ?? null,
    })
  }

  function expandGalleryQuota() {
    if (!token) return
    const price = galleryQuota?.expand_price_credits ?? 60
    const slots = galleryQuota?.expand_slots ?? 10
    const currentLimit = galleryQuota?.retained_limit ?? galleryRetentionLimit
    setGalleryExpandConfirm({
      price,
      slots,
      currentCount: galleryQuota?.retained_count ?? retainedPhotos,
      currentLimit,
      nextLimit: currentLimit + slots,
      availableCredits: balance?.available_credits ?? null,
    })
  }

  async function confirmExpandPackLimit() {
    if (!token || !packExpandConfirm) return
    setExpandingPackLimit(true)
    try {
      const quota = await api.expandPackLimit(token)
      setPackQuota(quota)
      setPackExpandConfirm(null)
      await refreshCore(token)
      setMessage(text('素材包数量上限已扩容', 'Pack slot limit expanded'))
    } catch (error) {
      showError(error)
    } finally {
      setExpandingPackLimit(false)
    }
  }

  async function confirmExpandGalleryQuota() {
    if (!token || !galleryExpandConfirm) return
    setExpandingGalleryQuota(true)
    try {
      const quota = await api.expandGalleryQuota(token)
      setGalleryQuota(quota)
      setGalleryExpandConfirm(null)
      await refreshCore(token)
      setMessage(text(`作品库已扩容至 ${quota.retained_limit} 格`, `Gallery expanded to ${quota.retained_limit} slots`))
    } catch (error) {
      showError(error)
    } finally {
      setExpandingGalleryQuota(false)
    }
  }

  async function addJobToPack(pack: AssetPack, job: GenerationJob) {
    if (!token) return
    try {
      await api.addJobToPack(token, pack.id, job.id)
      setSelectedPackId(pack.id)
      setSelectedPackJobs(await api.packJobs(token, pack.id))
      await refreshCore(token)
      setMessage(text('作品已保存到素材包', 'Work saved to pack'))
    } catch (error) {
      showError(error)
    }
  }

  async function removeJobFromPack(pack: AssetPack, job: GenerationJob) {
    if (!token) return
    try {
      await api.removeJobFromPack(token, pack.id, job.id)
      setSelectedPackJobs(await api.packJobs(token, pack.id))
      await refreshCore(token)
      setMessage(text('作品已从素材包移除', 'Work removed from pack'))
    } catch (error) {
      showError(error)
    }
  }

  async function deleteJob(job: GenerationJob) {
    if (!token) return
    setDeleteConfirm({ kind: 'job', job })
  }

  async function confirmDelete() {
    if (!token || !deleteConfirm) return
    const target = deleteConfirm
    setDeleting(true)
    setMessage('')
    try {
      if (target.kind === 'pack') {
        await api.deletePack(token, target.pack.id)
        if (selectedPackId === target.pack.id) {
          setSelectedPackId(null)
          setSelectedPackJobs([])
          setSelectedJobId(null)
        }
        await refreshCore(token)
        setMessage(text('素材包已删除', 'Pack deleted'))
      } else {
        await api.deleteJob(token, target.job.id)
        if (selectedJobId === target.job.id) setSelectedJobId(null)
        if (selectedRawJobId === target.job.id) setSelectedRawJobId(null)
        setSelectedPackJobs((current) => current.filter((item) => item.id !== target.job.id))
        await refreshCore(token)
        setMessage(text('作品已删除', 'Work deleted'))
      }
      setDeleteConfirm(null)
    } catch (error) {
      showError(error)
    } finally {
      setDeleting(false)
    }
  }

  async function retryJob(job: GenerationJob) {
    if (!token || job.status !== 'failed') return
    if (!(await confirmPhotoRetentionBeforeCreate(1))) return
    if (!(await confirm({ title: text('重试任务', 'Retry job'), description: text(`重试任务 #${job.id}？将按当前价格重新冻结点数。`, `Retry job #${job.id}? Credits will be reserved at the current price.`), confirmText: text('确认重试', 'Retry') }))) return
    setRetryingJobId(job.id)
    setMessage('')
    try {
      const created = await api.retryJob(token, job.id)
      setSelectedJobId(created.id)
      setPage('gallery')
      window.location.hash = '/gallery'
      setMessage(text(`任务 #${job.id} 已重试，新任务 #${created.id} 已提交。`, `Job #${job.id} retried; new job #${created.id} submitted.`))
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setRetryingJobId(null)
    }
  }

  async function saveSequenceAlignment(job: GenerationJob, payload: SequenceAlignmentRequest) {
    if (!token) return
    setMessage('')
    try {
      const updated = await api.saveSequenceAlignment(token, job.id, payload)
      setSelectedJobId(updated.id)
      await refreshCore(token)
      setMessage(text('序列帧已保存（含帧率与每帧偏移/缩放），作品库已切换到调整版本。', 'Sequence saved (fps, per-frame offset and scale); gallery now uses the aligned version.'))
    } catch (error) {
      showError(error)
      throw error
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

  const needsAdminSetup = setupStatus?.needs_admin && !user

  return (
    <main data-pix-theme={themeMode} className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur-xl dark:border-white/10 dark:bg-[hsl(var(--pix-navy-deep)/.95)]">
        <div className="mx-auto grid min-h-16 max-w-7xl grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 lg:grid-cols-[220px_minmax(0,1fr)_auto] lg:px-8">
          <a href="#/home" aria-label={t('app.backHome')} className="flex min-w-0 items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <img src="/pix-logo-64.png" alt="" className="h-9 w-9 shrink-0 [image-rendering:pixelated]" />
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-muted-foreground">Pix Forge</p>
              <p className="truncate text-xl font-semibold tracking-tight">{t('app.title')}</p>
            </div>
          </a>
          {user && <div className="hidden min-w-0 lg:block" aria-hidden="true" />}
          <div className="flex justify-end gap-2">
            <HeaderUtilityBar language={language} themePreference={themePreference} resolvedMode={themeMode} systemMode={systemThemeMode} autoOpenAnnouncement={page === 'home'} onLanguageChange={onLanguageChange} onThemePreferenceChange={onThemePreferenceChange} />
            {user ? (
              <>
                {page === 'home' && <Button asChild><a href="#/workspace">{t('app.workbench')}</a></Button>}
                <AccountMenu user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} isAdmin={isAdmin} onNavigate={navigate} onRefresh={refreshCurrent} onLogout={logout} />
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
      <PackExpandConfirmDialog
        state={packExpandConfirm}
        loading={expandingPackLimit}
        onCancel={cancelPackExpand}
        onConfirm={confirmPackExpand}
      />
      <GalleryExpandConfirmDialog
        state={galleryExpandConfirm}
        loading={expandingGalleryQuota}
        onCancel={cancelGalleryExpand}
        onConfirm={confirmGalleryExpand}
      />
      <DeleteConfirmDialog
        state={deleteConfirm}
        loading={deleting}
        onCancel={cancelDelete}
        onConfirm={confirmDeleteAction}
      />

      {setupLoading ? (
        <div className="grid min-h-[calc(100vh-76px)] place-items-center px-4 text-muted-foreground">{t('app.checkingSetup')}</div>
      ) : needsAdminSetup && setupStatus ? (
        <SetupWizard status={setupStatus} loading={busy} onBootstrapAdmin={bootstrapAdmin} onLocalTestLogin={localTestLogin} />
      ) : page === 'not-found' ? (
        <div>
          <NotFoundPage user={user} />
          <SiteFooter />
        </div>
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
          <Suspense fallback={<div className="grid min-h-[calc(100vh-160px)] place-items-center px-4 text-sm text-muted-foreground">{t('app.checkingSetup')}</div>}>
            {page === 'workspace' && <WorkspacePage mode={mode} pricing={pricing} balance={balance} jobs={jobs} loading={busy} token={token} imageModels={imageModels} onModeChange={setMode} onCreateJob={createJob} onCreateJobs={createJobs} onCandidatePixelize={pixelizeCandidate} onRefresh={refreshCurrent} />}
            {page === 'raw-image' && <RawImagePage pricing={pricing} balance={balance} jobs={jobs} loading={busy} token={token} imageModels={imageModels} selectedJobId={selectedRawJobId} onSelectJob={setSelectedRawJobId} onCreateJob={createRawImageJob} onRefresh={refreshCurrent} />}
            {page === 'gallery' && <GalleryPage jobs={jobs} selectedJob={selectedJob} selectedJobId={selectedJobId} pricing={pricing} loading={busy} retryingJobId={retryingJobId} galleryQuota={galleryQuota} onExpandGalleryQuota={expandGalleryQuota} onSelectJob={selectJobById} onCandidatePixelize={pixelizeCandidate} onCreateJob={createJob} onRetryJob={retryJob} onDeleteJob={deleteJob} onSaveSequenceAlignment={saveSequenceAlignment} />}
            {page === 'packs' && <PacksPage packs={packs} packQuota={packQuota} selectedPack={selectedPack} selectedPackId={selectedPackId} selectedPackJobs={selectedPackJobs} jobs={jobs} selectedJobId={selectedJobId} downloading={downloadingPackId !== null} onSelectPack={selectPack} onClearSelection={clearPackSelection} onCreatePack={createPack} onRenamePack={renamePack} onToggleArchive={toggleArchivePack} onDeletePack={deletePack} onExpandPackLimit={expandPackLimit} onDownloadPack={downloadPack} onAddJobToPack={addJobToPack} onRemoveJobFromPack={removeJobFromPack} onSelectJob={selectJobById} onCandidatePixelize={pixelizeCandidate} onRefresh={refreshCurrent} />}
            {page === 'billing' && <BillingPage balance={balance} transactions={transactions} packages={packages} customRechargeOptions={customRechargeOptions} orders={orders} checkout={checkout} isAdmin={isAdmin} onRefresh={refreshCurrent} onCreateOrder={createPaymentOrder} onCheckout={startCheckout} onCreateCustomOrder={createCustomPaymentOrder} onCustomCheckout={startCustomCheckout} onMockPayOrder={mockPayPaymentOrder} />}
            {page === 'rewards' && <RewardsPage token={token} onRefresh={refreshCurrent} />}
            {page === 'admin' && isAdmin && <AdminPage dashboard={adminDashboard} users={adminUsers} jobs={adminJobs} pricing={pricing} packages={adminPackages} settings={systemSettings} onRefresh={refreshCurrent} onAdjustCredits={adjustCredits} onAdjustCreditsBatch={adjustCreditsBatch} onUpdatePricing={updatePricing} onCreatePackage={createAdminPackage} onUpdatePackage={updateAdminPackage} onUpdateSetting={updateSetting} onPublishAnnouncement={publishAnnouncement} onTestEmail={testEmailSetting} onAdminRetryJob={adminRetryJob} onAdminCancelJob={adminCancelJob} onAdminFailRefundJob={adminFailRefundJob} onAdminAnnouncements={adminAnnouncements} onCreateAnnouncement={createAnnouncement} onUpdateAnnouncement={updateAnnouncement} onDeleteAnnouncement={deleteAnnouncement} onTestAnnouncementEmail={testAnnouncementEmail} onListProviders={listProviders} onListProviderPresets={listProviderPresets} onCreateProvider={createProvider} onUpdateProvider={updateProvider} onDeleteProvider={deleteProvider} token={token} />}
          </Suspense>
        </WorkspaceShell>
      ) : (
        <div>
          <AppHero user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={packs.length} />
          <LandingSections authSlot={<AuthPanel user={user} onLogin={login} onRegister={register} onRequestRegisterCode={requestRegisterCode} onRequestResetCode={requestResetCode} onResetPassword={resetAndLogin} onLocalTestLogin={localTestLogin} onLogout={logout} loading={busy} registrationBonusCredits={setupStatus?.registration_bonus_credits ?? 0} referralCode={referralCode} localTestLoginAvailable={setupStatus?.local_test_login_available ?? false} localTestAccountEmail={setupStatus?.local_test_account_email ?? null} turnstileEnabled={setupStatus?.turnstile_enabled ?? false} turnstileSiteKey={setupStatus?.turnstile_site_key ?? ''} />} />
          <SiteFooter />
        </div>
      )}
    </main>
  )
}

/* overlay components moved to ./components/AppOverlays.tsx */

