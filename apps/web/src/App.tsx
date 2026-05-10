import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from './api'
import { AdminPanel } from './components/AdminPanel'
import { AuthPanel } from './components/AuthPanel'
import { CreditPanel } from './components/CreditPanel'
import { JobComposer } from './components/JobComposer'
import { JobList } from './components/JobList'
import type { CreditBalance, CreditTransaction, GenerationJob, JobCreateRequest, PricingRule, User } from './types'

const TOKEN_KEY = 'pix_web_token'

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')
  const [user, setUser] = useState<User | null>(null)
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [transactions, setTransactions] = useState<CreditTransaction[]>([])
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [pricing, setPricing] = useState<PricingRule[]>([])
  const [adminUsers, setAdminUsers] = useState<User[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const isAdmin = user?.role === 'admin'

  const showError = useCallback((error: unknown) => {
    if (error instanceof ApiError) {
      setMessage(error.message)
    } else if (error instanceof Error) {
      setMessage(error.message)
    } else {
      setMessage('发生未知错误')
    }
  }, [])

  const refreshCore = useCallback(async (activeToken = token) => {
    if (!activeToken) return
    const [me, nextBalance, nextTransactions, nextJobs] = await Promise.all([
      api.me(activeToken),
      api.balance(activeToken),
      api.transactions(activeToken),
      api.jobs(activeToken),
    ])
    setUser(me)
    setBalance(nextBalance)
    setTransactions(nextTransactions)
    setJobs(nextJobs)
    if (me.role === 'admin') {
      const [users, rules] = await Promise.all([api.adminUsers(activeToken), api.pricing(activeToken)])
      setAdminUsers(users)
      setPricing(rules)
    }
  }, [token])

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
      api.balance(token).then(setBalance).catch(() => undefined)
    }, 3000)
    return () => window.clearInterval(id)
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

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken('')
    setUser(null)
    setBalance(null)
    setTransactions([])
    setJobs([])
    setPricing([])
    setAdminUsers([])
    setMessage('已退出')
  }

  async function createJob(payload: JobCreateRequest) {
    if (!token) return
    setBusy(true)
    setMessage('')
    try {
      const job = await api.createJob(token, payload)
      setMessage(`任务 #${job.id} 已入队`)
      await refreshCore(token)
    } catch (error) {
      showError(error)
    } finally {
      setBusy(false)
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

  const activeJobs = useMemo(() => jobs.filter((job) => ['pending', 'running'].includes(job.status)).length, [jobs])

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Pix Web MVP</p>
          <h1>AI 像素图生成工作台</h1>
          <p>注册、充值点数、创建任务、排队生成。当前版本先用本地路径和管理员加点跑通 SaaS 闭环。</p>
        </div>
        <div className="hero-card">
          <span>队列中</span>
          <strong>{activeJobs}</strong>
          <small>pending / running</small>
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <div className="layout-grid">
        <aside className="side-column">
          <AuthPanel user={user} onLogin={login} onRegister={register} onLogout={logout} loading={busy} />
          {user && <CreditPanel balance={balance} transactions={transactions} onRefresh={() => refreshCore()} />}
        </aside>
        <section className="main-column">
          {user ? (
            <>
              <JobComposer pricing={pricing} onSubmit={createJob} loading={busy} />
              <JobList jobs={jobs} onRefresh={() => refreshCore()} />
              {isAdmin && (
                <AdminPanel
                  users={adminUsers}
                  pricing={pricing}
                  onRefresh={() => refreshCore()}
                  onAdjustCredits={adjustCredits}
                  onUpdatePricing={updatePricing}
                />
              )}
            </>
          ) : (
            <section className="panel empty-panel">
              <h2>先登录或注册</h2>
              <p>第一个注册用户会自动成为管理员，可进入后台给自己加点并配置价格。</p>
            </section>
          )}
        </section>
      </div>
    </main>
  )
}
