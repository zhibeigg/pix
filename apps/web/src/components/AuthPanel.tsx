import { FormEvent, useEffect, useState } from 'react'
import type { EmailCodeResponse, User } from '../types'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'

type AuthPanelProps = { user: User | null; onLogin: (email: string, password: string) => Promise<void>; onRegister: (email: string, password: string, displayName: string, verificationCode: string) => Promise<void>; onRequestRegisterCode: (email: string) => Promise<EmailCodeResponse>; onLocalTestLogin: () => Promise<void>; onLogout: () => void; loading: boolean; registrationBonusCredits: number; localTestLoginAvailable: boolean; localTestAccountEmail: string | null }

export function AuthPanel({ user, onLogin, onRegister, onRequestRegisterCode, onLocalTestLogin, onLogout, loading, registrationBonusCredits, localTestLoginAvailable, localTestAccountEmail }: AuthPanelProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [codeMessage, setCodeMessage] = useState('')
  const [codeError, setCodeError] = useState('')
  const [sendingCode, setSendingCode] = useState(false)
  const [countdown, setCountdown] = useState(0)

  useEffect(() => { if (countdown > 0) { const t = window.setTimeout(() => setCountdown((v) => Math.max(0, v - 1)), 1000); return () => window.clearTimeout(t) } }, [countdown])
  const isRegister = mode === 'register'

  async function submit(event: FormEvent) { event.preventDefault(); if (isRegister) await onRegister(email, password, displayName, verificationCode); else await onLogin(email, password) }
  async function requestCode() { if (!email.trim()) { setCodeError('请先填写邮箱'); return } setSendingCode(true); setCodeMessage(''); setCodeError(''); try { const r = await onRequestRegisterCode(email.trim()); setCountdown(r.retry_after_seconds || 60); setCodeMessage(r.debug_code ? `验证码已发送。测试验证码：${r.debug_code}` : '验证码已发送，请查看邮箱') } catch (e) { setCodeError(e instanceof Error ? e.message : '验证码发送失败') } finally { setSendingCode(false) } }

  if (user) return <PixPanel eyebrow="账户" title="已进入工位台" description="账户已连接，可以开始创建素材、查看作品和管理点数。" action={<Button variant="outline" onClick={onLogout}>退出</Button>}><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-lg font-black">{user.display_name || user.email}</p><p className="text-sm text-muted-foreground">{user.email}</p></div><Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>{user.role === 'admin' ? '管理员' : '创作者'}</Badge></div><Alert className="mt-4" variant="success">身份已验证，任务和点数会在后台持续同步。</Alert></PixPanel>

  return (
    <PixPanel eyebrow="账户" title={isRegister ? '邮箱验证注册' : '登录工作台'} description={isRegister ? '验证码用于确认创作者邮箱。' : '回到你的像素素材生产线，继续批量生成、筛选和导出。'} action={<Button type="button" variant="outline" onClick={() => setMode(isRegister ? 'login' : 'register')}>{isRegister ? '登录' : '注册'}</Button>}>
      <form className="grid gap-4" onSubmit={submit}>
        {isRegister && <PixField label="昵称"><Input value={displayName} autoComplete="name" onChange={(e) => setDisplayName(e.target.value)} /></PixField>}
        <PixField label="邮箱"><Input type="email" value={email} autoComplete="email" onChange={(e) => setEmail(e.target.value)} required /></PixField>
        {isRegister && <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><PixField label="邮箱验证码"><Input value={verificationCode} autoComplete="one-time-code" inputMode="numeric" maxLength={6} onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))} required /></PixField><Button type="button" variant="outline" className="self-end" onClick={requestCode} disabled={loading || sendingCode || countdown > 0}>{sendingCode ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : '发送验证码'}</Button></div>}
        {codeMessage && <Alert variant="info">{codeMessage}</Alert>}{codeError && <Alert variant="destructive">{codeError}</Alert>}
        <PixField label="密码"><Input type="password" value={password} autoComplete={isRegister ? 'new-password' : 'current-password'} onChange={(e) => setPassword(e.target.value)} required /></PixField>
        {!isRegister && localTestLoginAvailable && <Alert variant="info" className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span>仅本地访问可用：用 {localTestAccountEmail} 快速测试工作台。</span><Button type="button" variant="outline" onClick={onLocalTestLogin} disabled={loading}>使用本地测试账号</Button></Alert>}
        <Button type="submit" size="lg" disabled={loading}>{loading ? '处理中…' : isRegister ? '验证并注册' : '进入工作台'}</Button>
        {isRegister && registrationBonusCredits > 0 && <Alert variant="info">注册即送 {registrationBonusCredits} 点数，可立即用于生成素材。</Alert>}
      </form>
    </PixPanel>
  )
}
