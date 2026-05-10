import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from './api'
import { AdminPanel } from './components/AdminPanel'
import { AuthPanel } from './components/AuthPanel'
import { BatchGeneratePanel } from './components/BatchGeneratePanel'
import { BatchPanel } from './components/BatchPanel'
import { CreditPanel } from './components/CreditPanel'
import { GalleryGrid } from './components/GalleryGrid'
import { JobList } from './components/JobList'
import { SingleGeneratePanel } from './components/SingleGeneratePanel'
import { TuningPanel } from './components/TuningPanel'
import type { CreditBalance, CreditTransaction, GenerationBatch, GenerationJob, JobCreateRequest, PricingRule, User } from './types'

const TOKEN_KEY = 'pix_web_token'
type WorkMode = 'single' | 'batch'

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [user, setUser] = useState<User | null>(null)
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [transactions, setTransactions] = useState<CreditTransaction[]>([])
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [batches, setBatches] = useState<GenerationBatch[]>([])
  const [pricing, setPricing] = useState<PricingRule[]>([])
  const [adminUsers, setAdminUsers] = useState<User[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [mode, setMode] = useState<WorkMode>('single')
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null)
  const [selectedBatchJobs, setSelectedBatchJobs] = useState<GenerationJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)

  const isAdmin = user?.role === 'admin'
  const selectedBatch = useMemo(() => batches.find((batch) => batch.id === selectedBatchId) ?? null, [batches, selectedBatchId])
  const visibleJobs = selectedBatchId ? selectedBatchJobs : jobs
  const selectedJob = useMemo(() => visibleJobs.find((job) => job.id === selectedJobId) ?? null, [visibleJobs, selectedJobId])
  const gallerySubtitle = selectedBatch ? `素材包：${selectedBatch.name}` : '全部作品'
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
    const [me, nextBalance, nextTransactions, nextJobs, nextBatches, nextPricing] = await Promise.all([
      api.me(activeToken),
      api.balance(activeToken),
      api.transactions(activeToken),
      api.jobs(activeToken),
      api.batches(activeToken),
      api.pricing(activeToken),
    ])
    setUser(me)
    setBalance(nextBalance)
    setTransactions(nextTransactions)
    setJobs(nextJobs)
    setBatches(nextBatches)
    setPricing(nextPricing)
    if (selectedBatchId) {
      setSelectedBatchJobs(await api.batchJobs(activeToken, selectedBatchId))
    }
    if (me.role === 'admin') {
      const users = await api.adminUsers(activeToken)
      setAdminUsers(users)
    }
  }, [selectedBatchId, token])

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
    const id = window.setInterval(() => {
      api.jobs(token).then(setJobs).catch(() => undefined)
      api.batches(token).then(setBatches).catch(() => undefined)
      if (selectedBatchId) api.batchJobs(token, selectedBatchId).then(setSelectedBatchJobs).catch(() => undefined)
      api.balance(token).then(setBalance).catch(() => undefined)
    }, 3000)
    return () => window.clearInterval(id)
  }, [selectedBatchId, token])

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

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken('')
    setUser(null)
    setBalance(null)
    setTransactions([])
    setJobs([])
    setBatches([])
    setSelectedBatchId(null)
    setSelectedBatchJobs([])
    setPricing([])
    setAdminUsers([])
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
      setMessage(`${created.jobs.length} 个任务已加入生产队列，冻结 ${created.total_price_credits} credits`)
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
    setMessage(`已筛选素材包：${batch.name}`)
  }

  function clearBatchFilter() {
    setSelectedBatchId(null)
    setSelectedBatchJobs([])
    setSelectedJobId(null)
    setMessage('已显示全部作品')
  }

  async function copyPath(path: string) {
    await navigator.clipboard.writeText(path)
    setMessage('输出路径已复制')
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

  return (
    <main className="app-shell forge-shell">
      <header className="hero forge-hero">
        <div>
          <p className="eyebrow">Pix Forge</p>
          <h1>像素素材工坊</h1>
          <p>单图快速试想法，批量生产素材包；本地微调免费，AI 微调清楚显示点数消耗。</p>
        </div>
        <div className="hero-stats">
          <Metric label="可用点数" value={balance?.available_credits ?? '—'} />
          <Metric label="队列中" value={activeJobs} />
          <Metric label="已完成" value={completedJobs} />
          <Metric label="失败" value={failedJobs} />
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <div className="workbench-grid">
        <aside className="side-column">
          <AuthPanel user={user} onLogin={login} onRegister={register} onLogout={logout} loading={busy} />
          {user && <CreditPanel balance={balance} transactions={transactions} onRefresh={() => refreshCore()} />}
        </aside>

        <section className="gallery-column">
          {user ? (
            <GalleryGrid jobs={visibleJobs} subtitle={gallerySubtitle} selectedJobId={selectedJobId} onSelect={(job) => setSelectedJobId(job.id)} onCopyPath={copyPath} />
          ) : (
            <section className="panel empty-panel">
              <h2>先登录或注册</h2>
              <p>第一个注册用户会自动成为管理员，可给自己加点并配置价格。</p>
            </section>
          )}
          {user && <JobList jobs={visibleJobs.filter((job) => job.status !== 'succeeded')} onRefresh={() => refreshCore()} />}
        </section>

        <aside className="right-column">
          {user && (
            <>
              <section className="panel mode-panel">
                <p className="eyebrow">Mode</p>
                <div className="mode-tabs">
                  <button className={mode === 'single' ? '' : 'ghost'} onClick={() => setMode('single')}>单图生成</button>
                  <button className={mode === 'batch' ? '' : 'ghost'} onClick={() => setMode('batch')}>批量生产</button>
                </div>
              </section>
              {mode === 'single' ? (
                <SingleGeneratePanel pricing={pricing} loading={busy} token={token} onSubmit={createJob} />
              ) : (
                <BatchGeneratePanel pricing={pricing} loading={busy} token={token} onSubmitMany={createJobs} />
              )}
              <BatchPanel batches={batches} selectedBatchId={selectedBatchId} onSelectBatch={selectBatch} onClearSelection={clearBatchFilter} onRefresh={() => refreshCore()} />
              <TuningPanel job={selectedJob} pricing={pricing} loading={busy} onSubmit={createJob} />
              {isAdmin && (
                <AdminPanel users={adminUsers} pricing={pricing} onRefresh={() => refreshCore()} onAdjustCredits={adjustCredits} onUpdatePricing={updatePricing} />
              )}
            </>
          )}
        </aside>
      </div>
    </main>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric hero-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
