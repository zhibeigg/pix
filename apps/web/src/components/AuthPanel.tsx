import { FormEvent, useEffect, useState } from 'react'
import { useI18n } from '../i18n'
import type { EmailCodeResponse, User } from '../types'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'

type AuthPanelProps = { user: User | null; onLogin: (email: string, password: string) => Promise<void>; onRegister: (email: string, password: string, displayName: string, verificationCode: string, referralCode?: string) => Promise<void>; onRequestRegisterCode: (email: string) => Promise<EmailCodeResponse>; onLocalTestLogin: () => Promise<void>; onLogout: () => void; loading: boolean; registrationBonusCredits: number; referralCode: string; localTestLoginAvailable: boolean; localTestAccountEmail: string | null }

export function AuthPanel({ user, onLogin, onRegister, onRequestRegisterCode, onLocalTestLogin, onLogout, loading, registrationBonusCredits, referralCode, localTestLoginAvailable, localTestAccountEmail }: AuthPanelProps) {
  const { text, t } = useI18n()
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
  const registrationBonusCopy = registrationBonusCredits > 0 ? text(`新人注册赠送 ${registrationBonusCredits} 点数`, `New accounts get ${registrationBonusCredits} bonus credits`) : ''

  async function submit(event: FormEvent) { event.preventDefault(); if (isRegister) await onRegister(email, password, displayName, verificationCode, referralCode); else await onLogin(email, password) }
  async function requestCode() { if (!email.trim()) { setCodeError(text('请先填写邮箱', 'Enter your email first')); return } setSendingCode(true); setCodeMessage(''); setCodeError(''); try { const r = await onRequestRegisterCode(email.trim()); setCountdown(r.retry_after_seconds || 60); setCodeMessage(r.debug_code ? text(`验证码已发送。测试验证码：${r.debug_code}`, `Verification code sent. Test code: ${r.debug_code}`) : text('验证码已发送，请查看邮箱', 'Verification code sent. Check your inbox.')) } catch (e) { setCodeError(e instanceof Error ? e.message : text('验证码发送失败', 'Failed to send verification code')) } finally { setSendingCode(false) } }

  if (user) return <PixPanel eyebrow={text('账户', 'Account')} title={text('已进入工位台', 'Workbench connected')} description={text('账户已连接，可以开始创建素材、查看作品和管理点数。', 'Your account is connected. You can create assets, review works, and manage credits.')} action={<Button variant="outline" onClick={onLogout}>{text('退出', 'Sign out')}</Button>}><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-lg font-semibold">{user.display_name || user.email}</p><p className="text-sm text-muted-foreground">{user.email}</p></div><Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>{user.role === 'admin' ? text('管理员', 'Admin') : text('创作者', 'Creator')}</Badge></div><Alert className="mt-4" variant="success">{text('身份已验证，任务和点数会在后台持续同步。', 'Identity verified. Jobs and credits will keep syncing in the background.')}</Alert></PixPanel>

  return (
    <PixPanel
      eyebrow={text('账户', 'Account')}
      title={isRegister ? text('邮箱验证注册', 'Register with email verification') : text('登录工作台', 'Sign in to workspace')}
      description={isRegister ? registrationBonusCopy || text('验证码用于确认创作者邮箱。', 'The verification code confirms the creator email.') : text('回到你的像素素材生产线，继续批量生成、筛选和导出。', 'Return to your pixel asset pipeline to batch generate, review, and export.')}
      action={
        <div className="grid gap-2 justify-items-end">
          {!isRegister && registrationBonusCopy && <Badge variant="secondary">{registrationBonusCopy}</Badge>}
          <Button type="button" variant="outline" onClick={() => setMode(isRegister ? 'login' : 'register')}>{isRegister ? text('登录', 'Sign in') : text('注册', 'Register')}</Button>
        </div>
      }
    >
      <form className="grid gap-4" onSubmit={submit}>
        {isRegister && referralCode && <Alert variant="success">{t('auth.referralDetected', { code: referralCode })}</Alert>}
        {isRegister && <PixField label={text('昵称', 'Display name')}><Input value={displayName} autoComplete="name" onChange={(e) => setDisplayName(e.target.value)} /></PixField>}
        <PixField label={text('邮箱', 'Email')}><Input type="email" value={email} autoComplete="email" onChange={(e) => setEmail(e.target.value)} required /></PixField>
        {isRegister && <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><PixField label={text('邮箱验证码', 'Email verification code')}><Input value={verificationCode} autoComplete="one-time-code" inputMode="numeric" maxLength={6} onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))} required /></PixField><Button type="button" variant="outline" className="self-end" onClick={requestCode} disabled={loading || sendingCode || countdown > 0}>{sendingCode ? text('发送中…', 'Sending…') : countdown > 0 ? text(`${countdown}s 后重发`, `Resend in ${countdown}s`) : text('发送验证码', 'Send code')}</Button></div>}
        {codeMessage && <Alert variant="info">{codeMessage}</Alert>}{codeError && <Alert variant="destructive">{codeError}</Alert>}
        <PixField label={text('密码', 'Password')}><Input type="password" value={password} autoComplete={isRegister ? 'new-password' : 'current-password'} onChange={(e) => setPassword(e.target.value)} required /></PixField>
        {localTestLoginAvailable && <Alert variant="info" className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span>{text(`仅本地访问可用：用 ${localTestAccountEmail} 快速测试工作台。`, `Local access only: use ${localTestAccountEmail} to quickly test the workspace.`)}</span><Button type="button" variant="outline" onClick={onLocalTestLogin} disabled={loading}>{text('使用本地测试账号', 'Use local test account')}</Button></Alert>}
        <Button type="submit" size="lg" disabled={loading}>{loading ? text('处理中…', 'Processing…') : isRegister ? text('验证并注册', 'Verify and register') : text('进入工作台', 'Enter workspace')}</Button>

      </form>
    </PixPanel>
  )
}
