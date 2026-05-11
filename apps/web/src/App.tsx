import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, AppBar, Box, Button, Container, Stack, Toolbar, Typography } from '@mui/material'
import { notionTokens } from './theme'
import { api, ApiError } from './api'
import { AppTabs, type AppPage } from './components/AppTabs'
import { AccountMenu } from './components/AccountMenu'
import { AppHero, DashboardSummary } from './components/AppHero'
import { AuthPanel } from './components/AuthPanel'
import { LandingSections } from './components/LandingSections'
import { AdminPage } from './pages/AdminPage'
import { BillingPage } from './pages/BillingPage'
import { GalleryPage } from './pages/GalleryPage'
import { PacksPage } from './pages/PacksPage'
import { WorkspacePage, type WorkMode } from './pages/WorkspacePage'
import type { AdminDashboard, CreditBalance, CreditPackage, CreditTransaction, GenerationBatch, GenerationJob, JobCreateRequest, PaymentCheckout, PaymentOrder, PricingRule, SystemSetting, User } from './types'

const TOKEN_KEY = 'pix_web_token'
function pageFromHash(user: User | null): AppPage {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const page = ['workspace', 'gallery', 'packs', 'billing', 'admin'].includes(raw) ? raw as AppPage : 'workspace'
  if (page === 'admin' && user?.role !== 'admin') return 'workspace'
  return page
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [user, setUser] = useState<User | null>(null)
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [transactions, setTransactions] = useState<CreditTransaction[]>([])
  const [packages, setPackages] = useState<CreditPackage[]>([])
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
  const [downloadingBatchId, setDownloadingBatchId] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [page, setPage] = useState<AppPage>(() => pageFromHash(null))
  const [mode, setMode] = useState<WorkMode>('single')
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null)
  const [selectedBatchJobs, setSelectedBatchJobs] = useState<GenerationJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const pollFailuresRef = useRef(0)

  const isAdmin = user?.role === 'admin'
  const selectedBatch = useMemo(() => batches.find((batch) => batch.id === selectedBatchId) ?? null, [batches, selectedBatchId])
  const selectedJobPool = page === 'packs' && selectedBatchId ? selectedBatchJobs : jobs
  const selectedJob = useMemo(() => selectedJobPool.find((job) => job.id === selectedJobId) ?? null, [selectedJobPool, selectedJobId])
  const activeJobs = useMemo(() => jobs.filter((job) => ['pending', 'running'].includes(job.status)).length, [jobs])
  const completedJobs = useMemo(() => jobs.filter((job) => job.status === 'succeeded').length, [jobs])
  const failedJobs = useMemo(() => jobs.filter((job) => job.status === 'failed').length, [jobs])

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
      const [users, settings, dashboard] = await Promise.all([
        api.adminUsers(activeToken),
        api.adminSettings(activeToken),
        api.adminDashboard(activeToken),
      ])
      setAdminUsers(users)
      setSystemSettings(settings)
      setAdminDashboard(dashboard)
    }
  }, [selectedBatchId, token])

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
      setMessage('登录成功')
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
  }

  async function register(email: string, password: string, displayName: string) {
    setBusy(true)
    setMessage('')
    try {
      await api.register(email, password, displayName)
      await login(email, password)
      setMessage('注册成功')
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
    }
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
    setSystemSettings([])
    setAdminDashboard(null)
    setSelectedJobId(null)
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
      setMessage(`${created.jobs.length} 个素材任务已加入生产队列，已冻结 ${created.total_price_credits} 点；失败项会自动退回冻结点数。`)
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
    if (nextStatus === 'archived' && !window.confirm(`归档「${batch.name}」？归档后仍可恢复，但会从活跃素材包中弱化显示。`)) return
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
      setMessage(`素材包 ${batch.name} 已开始下载`)
    } catch (error) {
      showError(error)
    } finally {
      setDownloadingBatchId(null)
    }
  }

  async function retryFailedBatch(batch: GenerationBatch) {
    if (!token) return
    if (!window.confirm(`重试「${batch.name}」中的 ${batch.failed_count} 个失败项？系统会重新冻结对应点数，仍失败的任务会自动退回冻结点数。`)) return
    setRetryingBatchId(batch.id)
    setMessage('')
    try {
      const result = await api.retryFailedBatch(token, batch.id)
      setMessage(`已重新入队 ${result.jobs.length} 个失败项，重新冻结 ${result.total_price_credits} 点；仍失败会自动退回。`)
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

  async function createPaymentOrder(packageKey: string) {
    if (!token) return
    try {
      const order = await api.createOrder(token, packageKey)
      setCheckout(null)
      await refreshCore(token)
      setMessage(`充值订单 #${order.id} 已创建，等待支付`)
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
      setMessage(`充值订单 #${result.order.id} 已创建：${provider}`)
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

  async function updateSetting(key: string, value: string) {
    if (!token) return
    await api.updateSetting(token, key, value)
    await refreshCore(token)
    setMessage('运营保护设置已更新')
  }

  return (
    <Box component="main">
      <AppBar position="sticky" elevation={0} color="inherit" sx={{ bgcolor: notionTokens.canvas, borderBottom: 1, borderColor: 'divider', zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap: 2, maxWidth: 1280, width: '100%', mx: 'auto', px: { xs: 2, md: 4 }, py: 1, minHeight: 72, alignItems: 'center', flexWrap: { xs: 'wrap', lg: 'nowrap' } }}>
          <Box sx={{ minWidth: 190, flex: { xs: '1 1 auto', lg: '0 0 auto' } }}>
            <Typography variant="overline" color="text.secondary">Pix Forge</Typography>
            <Typography variant="h5" component="h1">像素素材工坊</Typography>
          </Box>
          {user && (
            <Box sx={{ order: { xs: 3, lg: 2 }, flex: '1 1 auto', minWidth: 0, width: { xs: '100%', lg: 'auto' } }}>
              <AppTabs page={page} user={user} onChange={navigate} />
            </Box>
          )}
          <Box sx={{ order: { xs: 2, lg: 3 }, flex: { xs: '0 0 auto', lg: '0 0 auto' }, ml: { lg: 'auto' } }}>
            {user ? (
              <AccountMenu user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} isAdmin={isAdmin} onNavigate={navigate} onRefresh={() => refreshCore()} onLogout={logout} />
            ) : (
              <Stack direction="row" spacing={1}>
                <Button variant="text" href="#auth-panel">登录</Button>
                <Button variant="contained" href="#auth-panel">注册</Button>
              </Stack>
            )}
          </Box>
        </Toolbar>
      </AppBar>

      {user ? (
        <Container maxWidth={false} sx={{ maxWidth: 1280, py: { xs: 3, md: 4 }, px: { xs: 2, md: 4 }, mx: 'auto' }}>
          <Stack spacing={4}>
            <DashboardSummary balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={batches.length} />
            {message && <Alert severity="info" role="status" aria-live="polite">{message}</Alert>}
            <Box sx={{ display: 'grid', gap: 3 }}>
              {page === 'workspace' && (
                <WorkspacePage mode={mode} pricing={pricing} balance={balance} jobs={jobs} loading={busy} token={token} onModeChange={setMode} onCreateJob={createJob} onCreateJobs={createJobs} onRefresh={() => refreshCore()} />
              )}
              {page === 'gallery' && (
                <GalleryPage jobs={jobs} selectedJob={selectedJob} selectedJobId={selectedJobId} pricing={pricing} loading={busy} onSelectJob={(job) => setSelectedJobId(job.id)} onCopyPath={copyPath} onCreateJob={createJob} onRefresh={() => refreshCore()} />
              )}
              {page === 'packs' && (
                <PacksPage batches={batches} selectedBatch={selectedBatch} selectedBatchId={selectedBatchId} selectedBatchJobs={selectedBatchJobs} selectedJobId={selectedJobId} retrying={retryingBatchId !== null} downloading={downloadingBatchId !== null} onSelectBatch={selectBatch} onClearSelection={clearBatchFilter} onRetryFailed={retryFailedBatch} onDownloadBatch={downloadBatch} onRenameBatch={renameBatch} onToggleArchive={toggleArchiveBatch} onDeleteBatch={deleteBatch} onSelectJob={(job) => setSelectedJobId(job.id)} onCopyPath={copyPath} onRefresh={() => refreshCore()} />
              )}
              {page === 'billing' && (
                <BillingPage balance={balance} transactions={transactions} packages={packages} orders={orders} checkout={checkout} isAdmin={isAdmin} onRefresh={() => refreshCore()} onCreateOrder={createPaymentOrder} onCheckout={startCheckout} onMockPayOrder={mockPayPaymentOrder} />
              )}
              {page === 'admin' && isAdmin && (
                <AdminPage dashboard={adminDashboard} users={adminUsers} pricing={pricing} settings={systemSettings} onRefresh={() => refreshCore()} onAdjustCredits={adjustCredits} onUpdatePricing={updatePricing} onUpdateSetting={updateSetting} />
              )}
            </Box>
          </Stack>
        </Container>
      ) : (
        <Box
          sx={{
            height: { md: 'calc(100vh - 80px)' },
            overflowY: { md: 'auto' },
            scrollSnapType: { md: 'y mandatory' },
            scrollBehavior: 'smooth',
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
            '&::-webkit-scrollbar': { display: 'none' },
          }}
        >
          <AppHero user={user} balance={balance} activeJobs={activeJobs} completedJobs={completedJobs} failedJobs={failedJobs} batchCount={batches.length} />
          {message && <Box sx={{ maxWidth: 1152, mx: 'auto', px: { xs: 2, md: 4 }, py: 2 }}><Alert severity="info" role="status" aria-live="polite">{message}</Alert></Box>}
          <LandingSections authSlot={<AuthPanel user={user} onLogin={login} onRegister={register} onLogout={logout} loading={busy} />} />
        </Box>
      )}
    </Box>
  )
}
