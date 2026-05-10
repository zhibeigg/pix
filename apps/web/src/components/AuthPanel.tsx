import { FormEvent, useState } from 'react'
import type { User } from '../types'

type AuthPanelProps = {
  user: User | null
  onLogin: (email: string, password: string) => Promise<void>
  onRegister: (email: string, password: string, displayName: string) => Promise<void>
  onLogout: () => void
  loading: boolean
}

export function AuthPanel({ user, onLogin, onRegister, onLogout, loading }: AuthPanelProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('password123')
  const [displayName, setDisplayName] = useState('Pix Admin')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (mode === 'login') {
      await onLogin(email, password)
    } else {
      await onRegister(email, password, displayName)
    }
  }

  if (user) {
    return (
      <section className="panel identity-panel">
        <div>
          <p className="eyebrow">当前账户</p>
          <h2>{user.display_name || user.email}</h2>
          <p className="muted">{user.email}</p>
          <span className="pill">{user.role}</span>
        </div>
        <button className="ghost" onClick={onLogout}>退出登录</button>
      </section>
    )
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">账户</p>
          <h2>{mode === 'login' ? '登录工作台' : '创建账户'}</h2>
        </div>
        <button className="ghost" type="button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? '注册' : '登录'}
        </button>
      </div>
      <form onSubmit={submit} className="stack">
        {mode === 'register' && (
          <label>
            昵称
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
        )}
        <label>
          邮箱
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label>
          密码
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button disabled={loading}>{loading ? '处理中…' : mode === 'login' ? '登录' : '注册'}</button>
      </form>
    </section>
  )
}
