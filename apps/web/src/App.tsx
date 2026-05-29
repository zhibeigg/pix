import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { CheckCircle2, CircleAlert, Coins, Info, PackagePlus, Trash2, X } from 'lucide-react'
import type { PixLanguage, PixThemeMode, PixThemePreference } from './theme'
import { api, ApiError, TOKEN_KEY } from './api'
import { AppTabs, type AppPage } from './components/AppTabs'
import { AccountMenu } from './components/AccountMenu'
import { AppHero } from './components/AppHero'
import { AuthPanel } from './components/AuthPanel'
import { Button } from './components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogOverlay, DialogPortal, DialogTitle } from './components/ui/dialog'
import { HeaderUtilityBar } from './components/HeaderUtilityBar'
import { LandingSections } from './components/LandingSections'
import { SetupWizard } from './components/SetupWizard'
import { AdminPage } from './pages/AdminPage'
import { BillingPage } from './pages/BillingPage'
import { GalleryPage } from './pages/GalleryPage'
import { PacksPage } from './pages/PacksPage'
import { RawImagePage } from './pages/RawImagePage'
import { RewardsPage } from './pages/RewardsPage'
import { WorkspacePage, type WorkMode } from './pages/WorkspacePage'
import { buildGridDesign, defaultPixelize } from './pixelize'
import { useI18n } from './i18n'
import type { AdminDashboard, AssetPack, AssetPackQuota, ContactSheetCandidate, CreditBalance, CreditPackage, CreditTransaction, CustomRechargeOptions, EmailCodeResponse, GenerationJob, JobCreateRequest, PaymentCheckout, PaymentOrder, PricingRule, SequenceAlignmentRequest, SetupStatus, SystemSetting, User } from './types'

type ToastVariant = 'success' | 'info' | 'error'
type AppToastState = { id: number; message: string; variant: ToastVariant }
type PackExpandConfirmState = { price: number; currentCount: number; currentLimit: number; nextLimit: number; availableCredits: number | null }
type DeleteConfirmState = { kind: 'job'; job: GenerationJob } | { kind: 'pack'; pack: AssetPack }

type AppProps = {
  themeMode: PixThemeMode
  themePreference: PixThemePreference
  systemThemeMode: PixThemeMode
  language: PixLanguage
  onThemePreferenceChange: (preference: PixThemePreference) => void
  onLanguageChange: (language: PixLanguage) => void
}

const PHOTO_RETENTION_LIMIT = 10
const REFERRAL_CODE_KEY = 'pix_referral_code'

function referralCodeFromLocation() {
  const candidates: string[] = []
  if (typeof window === 'undefined') return ''
  candidates.push(new URLSearchParams(window.location.search).get('aff') ?? '')
  const hash = window.location.hash || ''
  const queryIndex = hash.indexOf('?')
  if (queryIndex >= 0) candidates.push(new URLSearchParams(hash.slice(queryIndex + 1)).get('aff') ?? '')
  return candidates.map((item) => item.trim().toUpperCase()).find(Boolean) ?? ''
}

function pageFromHash(user: User | null): AppPage {
  const raw = window.location.hash.replace(/^#\/?/, '').split('?', 1)[0]
  if (!raw || raw === 'home') return 'home'
  const page = ['workspace', 'raw-image', 'gallery', 'packs', 'billing', 'rewards', 'admin'].includes(raw) ? raw as AppPage : 'home'
  if (page === 'admin' && user?.role !== 'admin') return 'workspace'
  return page
}

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
  const [packExpandConfirm, setPackExpandConfirm] = useState<PackExpandConfirmState | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<DeleteConfirmState | null>(null)
  const [expandingPackLimit, setExpandingPackLimit] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [pricing, setPricing] = useState<PricingRule[]>([])
  const [adminUsers, setAdminUsers] = useState<User[]>([])
  const [systemSettings, setSystemSettings] = useState<SystemSetting[]>([])
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null)
  const [busy, setBusy] = useState(false)
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null)
  const [downloadingPackId, setDownloadingPackId] = useState<number | null>(null)
  const [toast, setToast] = useState<AppToastState | null>(null)
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null)
  const [setupLoading, setSetupLoading] = useState(true)
  const [page, setPage] = useState<AppPage>(() => pageFromHash(null))
  const [mode, setMode] = useState<WorkMode>('single')
  const [referralCode, setReferralCode] = useState(() => referralCodeFromLocation() || localStorage.getItem(REFERRAL_CODE_KEY) || '')
  const [selectedPackId, setSelectedPackId] = useState<number | null>(null)
  const [selectedPackJobs, setSelectedPackJobs] = useState<GenerationJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [selectedRawJobId, setSelectedRawJobId] = useState<number | null>(null)
  const pollFailuresRef = useRef(0)
  const handledPaymentReturnRef = useRef('')
  const jobStatusSnapshotRef = useRef<Map<number, string>>(new Map())
  const jobStatusSeededRef = useRef(false)

  const isAdmin = user?.role === 'admin'
  const selectedPack = useMemo(() => packs.find((pack) => pack.id === selectedPackId) ?? null, [packs, selectedPackId])
  const selectedJobPool = page === 'packs' && selectedPackId ? selectedPackJobs : jobs
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
    const [me, nextBalance, nextTransactions, nextPackages, nextCustomRechargeOptions, nextOrders, nextJobs, nextPacks, nextPackQuota, nextPricing] = await Promise.all([
      api.me(activeToken),
      api.balance(activeToken),
      api.transactions(activeToken),
      api.packages(),
      api.customRechargeOptions(),
      api.orders(activeToken),
      api.jobs(activeToken),
      api.packs(activeToken),
      api.packQuota(activeToken),
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
    setPacks(nextPacks)
    setPackQuota(nextPackQuota)
    setPricing(nextPricing)
    if (selectedPackId) {
      setSelectedPackJobs(await api.packJobs(activeToken, selectedPackId))
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
  }, [notifyJobCompletions, selectedPackId, token])

  useEffect(() => {
    refreshSetupStatus().catch(showError)
  }, [refreshSetupStatus, showError])

  useEffect(() => {
    const fromUrl = referralCodeFromLocation()
    if (!fromUrl) return
    localStorage.setItem(REFERRAL_CODE_KEY, fromUrl)
    setReferralCode(fromUrl)
  }, [])

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
        const [nextJobs, nextPacks, nextPackQuota, nextBalance, nextOrders] = await Promise.all([
          api.jobs(token),
          api.packs(token),
          api.packQuota(token),
          api.balance(token),
          api.orders(token),
        ])
        notifyJobCompletions(nextJobs)
        setJobs(nextJobs)
        setPacks(nextPacks)
        setPackQuota(nextPackQuota)
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

  async function register(email: string, password: string, displayName: string, verificationCode: string, nextReferralCode = referralCode) {
    setBusy(true)
    setMessage('')
    try {
      await api.register(email, password, displayName, verificationCode, nextReferralCode)
      localStorage.removeItem(REFERRAL_CODE_KEY)
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
    setPacks([])
    setPackQuota(null)
    setSelectedPackId(null)
    setSelectedPackJobs([])
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
    if (!confirmPhotoRetentionBeforeCreate(payloads.length)) return
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
    if (!confirmPhotoRetentionBeforeCreate(1)) return
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
    if (nextStatus === 'archived' && !window.confirm(text(`归档「${pack.name}」？`, `Archive “${pack.name}”?`))) return
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
    if (!confirmPhotoRetentionBeforeCreate(1)) return
    if (!window.confirm(text(`重试任务 #${job.id}？将按当前价格重新冻结点数。`, `Retry job #${job.id}? Credits will be reserved at the current price.`))) return
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
            <HeaderUtilityBar language={language} themePreference={themePreference} resolvedMode={themeMode} systemMode={systemThemeMode} autoOpenAnnouncement={page === 'home'} onLanguageChange={onLanguageChange} onThemePreferenceChange={onThemePreferenceChange} />
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
      <PackExpandConfirmDialog
        state={packExpandConfirm}
        loading={expandingPackLimit}
        onCancel={() => setPackExpandConfirm(null)}
        onConfirm={() => void confirmExpandPackLimit()}
      />
      <DeleteConfirmDialog
        state={deleteConfirm}
        loading={deleting}
        onCancel={() => setDeleteConfirm(null)}
        onConfirm={() => void confirmDelete()}
      />

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
          {page === 'raw-image' && <RawImagePage pricing={pricing} balance={balance} jobs={jobs} loading={busy} token={token} selectedJobId={selectedRawJobId} onSelectJob={setSelectedRawJobId} onCreateJob={createRawImageJob} onRefresh={() => refreshCore()} />}
          {page === 'gallery' && <GalleryPage jobs={jobs} selectedJob={selectedJob} selectedJobId={selectedJobId} pricing={pricing} loading={busy} retryingJobId={retryingJobId} onSelectJob={(job) => setSelectedJobId(job.id)} onCandidatePixelize={pixelizeCandidate} onCreateJob={createJob} onRetryJob={retryJob} onDeleteJob={deleteJob} onSaveSequenceAlignment={saveSequenceAlignment} />}
          {page === 'packs' && <PacksPage packs={packs} packQuota={packQuota} selectedPack={selectedPack} selectedPackId={selectedPackId} selectedPackJobs={selectedPackJobs} jobs={jobs} selectedJobId={selectedJobId} downloading={downloadingPackId !== null} onSelectPack={selectPack} onClearSelection={clearPackSelection} onCreatePack={createPack} onRenamePack={renamePack} onToggleArchive={toggleArchivePack} onDeletePack={deletePack} onExpandPackLimit={expandPackLimit} onDownloadPack={downloadPack} onAddJobToPack={addJobToPack} onRemoveJobFromPack={removeJobFromPack} onSelectJob={(job) => setSelectedJobId(job.id)} onCandidatePixelize={pixelizeCandidate} onRefresh={() => refreshCore()} />}
          {page === 'billing' && <BillingPage balance={balance} transactions={transactions} packages={packages} customRechargeOptions={customRechargeOptions} orders={orders} checkout={checkout} isAdmin={isAdmin} onRefresh={() => refreshCore()} onCreateOrder={createPaymentOrder} onCheckout={startCheckout} onCreateCustomOrder={createCustomPaymentOrder} onCustomCheckout={startCustomCheckout} onMockPayOrder={mockPayPaymentOrder} />}
          {page === 'rewards' && <RewardsPage token={token} onRefresh={() => refreshCore()} />}
          {page === 'admin' && isAdmin && <AdminPage dashboard={adminDashboard} users={adminUsers} pricing={pricing} packages={adminPackages} settings={systemSettings} onRefresh={() => refreshCore()} onAdjustCredits={adjustCredits} onUpdatePricing={updatePricing} onCreatePackage={createAdminPackage} onUpdatePackage={updateAdminPackage} onUpdateSetting={updateSetting} onTestEmail={testEmailSetting} />}
        </WorkspaceShell>
      ) : (
        <div>
          <AppHero user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={packs.length} />
          <LandingSections authSlot={<AuthPanel user={user} onLogin={login} onRegister={register} onRequestRegisterCode={requestRegisterCode} onLocalTestLogin={localTestLogin} onLogout={logout} loading={busy} registrationBonusCredits={setupStatus?.registration_bonus_credits ?? 0} referralCode={referralCode} localTestLoginAvailable={setupStatus?.local_test_login_available ?? false} localTestAccountEmail={setupStatus?.local_test_account_email ?? null} />} />
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

function DeleteConfirmDialog({ state, loading, onCancel, onConfirm }: { state: DeleteConfirmState | null; loading: boolean; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useI18n()
  const title = state?.kind === 'job'
    ? t('confirmDelete.workTitle', { id: state.job.id })
    : state?.kind === 'pack'
      ? t('confirmDelete.packTitle')
      : ''
  const description = state?.kind === 'job'
    ? t('confirmDelete.workDescription')
    : state?.kind === 'pack'
      ? t('confirmDelete.packDescription', { name: state.pack.name })
      : ''
  const impactItems = state?.kind === 'job'
    ? [
        t('confirmDelete.workMeta', { id: state.job.id }),
        t('confirmDelete.outputMeta'),
        t('confirmDelete.irreversible'),
      ]
    : state?.kind === 'pack'
      ? [
          t('confirmDelete.packMeta', { name: state.pack.name }),
          t('confirmDelete.irreversible'),
        ]
      : []

  return (
    <Dialog open={Boolean(state)} onOpenChange={(open) => { if (!open && !loading) onCancel() }}>
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          className="fixed z-50 overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card p-0 shadow-[0_24px_80px_-24px_rgba(15,15,15,0.42)] focus:outline-none dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]"
          style={{
            left: '50%',
            maxHeight: 'calc(100dvh - 32px)',
            maxWidth: 'none',
            top: '50%',
            transform: 'translate3d(-50%, -50%, 0)',
            width: 'min(500px, calc(100vw - 32px))',
          }}
        >
          {state && (
            <div className="relative grid gap-5 p-6">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_18%_0%,hsl(var(--destructive)/.18),transparent_36%),linear-gradient(180deg,hsl(var(--pix-cream)/.86),transparent)] dark:bg-[radial-gradient(circle_at_18%_0%,hsl(var(--destructive)/.34),transparent_34%),linear-gradient(180deg,hsl(var(--pix-navy)/.82),transparent)]" />
              <DialogHeader className="relative grid grid-cols-[auto_minmax(0,1fr)] gap-3 pr-8">
                <div className="grid h-12 w-12 place-items-center rounded-lg border border-destructive/24 bg-destructive/10 text-destructive shadow-[0_14px_34px_-22px_hsl(var(--destructive)/.72)] dark:border-red-300/24 dark:bg-red-500/12 dark:text-red-200">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-destructive/75 dark:text-red-200/78">{t('confirmDelete.eyebrow')}</p>
                  <DialogTitle className="mt-1 text-xl leading-tight">{title}</DialogTitle>
                  <DialogDescription className="mt-2 leading-6">{description}</DialogDescription>
                </div>
              </DialogHeader>
              <div className="relative grid gap-2 rounded-lg border border-destructive/18 bg-destructive/7 p-3 text-sm dark:border-red-300/18 dark:bg-red-500/10">
                {impactItems.map((item) => (
                  <div key={item} className="flex items-center gap-2 rounded-md bg-card/72 px-3 py-2 text-muted-foreground dark:bg-black/12 dark:text-white/68">
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-sm bg-destructive/10 text-[10px] font-bold text-destructive dark:bg-red-300/12 dark:text-red-200">×</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
              <DialogFooter className="relative">
                <Button type="button" variant="outline" disabled={loading} onClick={onCancel}>{t('confirmDelete.cancel')}</Button>
                <Button type="button" variant="destructive" disabled={loading} onClick={onConfirm}>{loading ? t('confirmDelete.deleting') : t('confirmDelete.confirm')}</Button>
              </DialogFooter>
            </div>
          )}
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring" disabled={loading}>
            <X className="h-4 w-4" />
            <span className="sr-only">关闭</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  )
}

function PackExpandConfirmDialog({ state, loading, onCancel, onConfirm }: { state: PackExpandConfirmState | null; loading: boolean; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useI18n()
  const available = state?.availableCredits ?? null
  return (
    <Dialog open={Boolean(state)} modal={false} onOpenChange={(open) => { if (!open && !loading) onCancel() }}>
      <DialogContent className="overflow-hidden border-[hsl(var(--pix-paper-border))] bg-card p-0 shadow-[0_24px_80px_-24px_rgba(15,15,15,0.42)] sm:max-w-[480px] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]">
        {state && (
          <div className="relative grid gap-5 p-6">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_20%_0%,hsl(var(--primary)/.18),transparent_38%),linear-gradient(180deg,hsl(var(--pix-mint)/.62),transparent)] dark:bg-[radial-gradient(circle_at_20%_0%,hsl(var(--primary)/.32),transparent_38%),linear-gradient(180deg,hsl(var(--pix-navy)/.72),transparent)]" />
            <DialogHeader className="relative grid grid-cols-[auto_minmax(0,1fr)] gap-3 pr-8">
              <div className="grid h-12 w-12 place-items-center rounded-lg border border-primary/20 bg-primary/10 text-primary shadow-[0_12px_28px_-18px_rgba(79,70,229,0.72)] dark:border-primary/30 dark:bg-primary/18">
                <PackagePlus className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <DialogTitle className="text-xl leading-tight">{t('packs.expandDialogTitle')}</DialogTitle>
                <DialogDescription className="mt-2 leading-6">{t('packs.expandDialogDescription', { price: state.price })}</DialogDescription>
              </div>
            </DialogHeader>
            <div className="relative grid gap-2 rounded-lg border border-border bg-background/82 p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
              <div className="grid grid-cols-3 gap-2 text-center">
                <DialogMetric label={t('packs.expandDialogCurrent')} value={`${state.currentCount}/${state.currentLimit}`} />
                <DialogMetric label={t('packs.expandDialogAfter')} value={`${state.currentCount}/${state.nextLimit}`} tone="primary" />
                <DialogMetric label={t('packs.expandDialogCost')} value={t('common.points', { count: state.price })} />
              </div>
              {available !== null && (
                <div className="mt-1 flex items-center gap-2 rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground dark:bg-white/6 dark:text-white/58">
                  <Coins className="h-4 w-4 text-primary" />
                  <span>{t('packs.expandDialogBalance', { count: available })}</span>
                </div>
              )}
            </div>
            <DialogFooter className="relative">
              <Button type="button" variant="outline" disabled={loading} onClick={onCancel}>{t('common.cancel')}</Button>
              <Button type="button" disabled={loading} onClick={onConfirm}>{loading ? t('packs.expandDialogWorking') : t('packs.expandDialogConfirm')}</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function DialogMetric({ label, value, tone = 'default' }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'primary' }) {
  const labelClass = tone === 'primary' ? 'text-primary/72 dark:text-primary/82' : 'text-muted-foreground dark:text-white/52'
  return (
    <div className={`rounded-md border px-2.5 py-2 ${tone === 'primary' ? 'border-primary/25 bg-primary/10 text-primary dark:bg-primary/18' : 'border-border bg-card dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]'}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[.08em] ${labelClass}`}>{label}</p>
      <p className="mt-1 text-sm font-bold leading-tight">{value}</p>
    </div>
  )
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
      <div key={toast.id} role="status" aria-live="polite" className={`motion-success-pop pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 text-sm font-medium shadow-[0_16px_48px_-8px_rgba(15,15,15,0.26)] ring-1 ring-black/5 ${tone}`}>
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
        <div key={page} className="motion-page-enter grid w-full gap-6">
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
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer" className="mt-4 inline-flex text-xs text-muted-foreground hover:text-foreground">鲁ICP备2022023963号-1</a>
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
