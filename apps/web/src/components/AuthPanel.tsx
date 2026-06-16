import { FormEvent, useEffect, useState } from 'react'
import { useI18n } from '../i18n'
import { useTurnstile } from '../lib/turnstile'
import type { EmailCodeResponse, User } from '../types'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'

type AuthPanelProps = {
  user: User | null
  onLogin: (email: string, password: string) => Promise<void>
  onRegister: (email: string, password: string, displayName: string, verificationCode: string, referralCode?: string) => Promise<void>
  onRequestRegisterCode: (email: string, turnstileToken: string) => Promise<EmailCodeResponse>
  onRequestResetCode: (email: string, turnstileToken: string) => Promise<EmailCodeResponse>
  onResetPassword: (email: string, newPassword: string, verificationCode: string) => Promise<void>
  onLocalTestLogin: () => Promise<void>
  onLogout: () => void
  loading: boolean
  registrationBonusCredits: number
  referralCode: string
  localTestLoginAvailable: boolean
  localTestAccountEmail: string | null
  turnstileEnabled: boolean
  turnstileSiteKey: string
}

export function AuthPanel({ user, onLogin, onRegister, onRequestRegisterCode, onRequestResetCode, onResetPassword, onLocalTestLogin, onLogout, loading, registrationBonusCredits, referralCode, localTestLoginAvailable, localTestAccountEmail, turnstileEnabled, turnstileSiteKey }: AuthPanelProps) {
  const { text, t, language } = useI18n()
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [codeMessage, setCodeMessage] = useState('')
  const [codeError, setCodeError] = useState('')
  const [sendingCode, setSendingCode] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [passwordHint, setPasswordHint] = useState('')
  const [turnstileRequired, setTurnstileRequired] = useState(false)
  const isRegister = mode === 'register'
  const isForgot = mode === 'forgot'
  const turnstileAvailable = turnstileEnabled && Boolean(turnstileSiteKey)
  const turnstileActive = (isRegister || isForgot) && turnstileAvailable && turnstileRequired
  const turnstile = useTurnstile({ enabled: turnstileActive, siteKey: turnstileSiteKey, language })

  useEffect(() => { if (countdown > 0) { const tid = window.setTimeout(() => setCountdown((v) => Math.max(0, v - 1)), 1000); return () => window.clearTimeout(tid) } }, [countdown])
  const registrationBonusCopy = registrationBonusCredits > 0 ? text(`新人注册赠送 ${registrationBonusCredits} 点数`, `New accounts get ${registrationBonusCredits} bonus credits`) : ''

  function isTurnstileRequiredError(error: unknown) {
    return Boolean(error && typeof error === 'object' && 'status' in error && (error as { status?: number }).status === 428)
  }

  function handleTurnstileRequired(error: unknown) {
    setTurnstileRequired(true)
    setCodeError(error instanceof Error ? error.message : text('请求较频繁，请完成人机校验后再发送验证码', 'Too many requests. Complete verification before sending another code.'))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (isForgot) {
      try {
        await onResetPassword(email.trim(), password, verificationCode)
        resetForm()
        setMode('login')
      } catch { /* error handled in parent */ }
    } else if (isRegister) {
      await onRegister(email, password, displayName, verificationCode, referralCode)
    } else {
      await onLogin(email, password)
    }
  }

  async function requestCode() {
    if (!email.trim()) { setCodeError(text('请先填写邮箱', 'Enter your email first')); return }
    if (turnstileActive && !turnstile.ready) { setCodeError(text('请先在下方完成校验后再发送验证码', 'Scroll down and complete the verification before sending the code')); return }
    setSendingCode(true); setCodeMessage(''); setCodeError('')
    try {
      const r = await onRequestResetCode(email.trim(), turnstileActive ? turnstile.token : '')
      setTurnstileRequired(false)
      setCountdown(r.retry_after_seconds || 60)
      setCodeMessage(r.debug_code ? text(`验证码已发送。测试验证码：${r.debug_code}`, `Verification code sent. Test code: ${r.debug_code}`) : t('auth.resetCodeSent', { email: email.trim() }))
    } catch (e) {
      if (isTurnstileRequiredError(e)) handleTurnstileRequired(e)
      else setCodeError(e instanceof Error ? e.message : text('验证码发送失败', 'Failed to send verification code'))
    } finally {
      setSendingCode(false)
      if (turnstileActive) turnstile.reset()
    }
  }

  async function requestRegisterCode() {
    if (!email.trim()) { setCodeError(text('请先填写邮箱', 'Enter your email first')); return }
    if (turnstileActive && !turnstile.ready) { setCodeError(text('请先在下方完成校验后再发送验证码', 'Scroll down and complete the verification before sending the code')); return }
    setSendingCode(true); setCodeMessage(''); setCodeError('')
    try {
      const r = await onRequestRegisterCode(email.trim(), turnstileActive ? turnstile.token : '')
      setTurnstileRequired(false)
      setCountdown(r.retry_after_seconds || 60)
      setCodeMessage(r.debug_code ? text(`验证码已发送。测试验证码：${r.debug_code}`, `Verification code sent. Test code: ${r.debug_code}`) : text('验证码已发送，请查看邮箱', 'Verification code sent. Check your inbox.'))
    } catch (e) {
      if (isTurnstileRequiredError(e)) handleTurnstileRequired(e)
      else setCodeError(e instanceof Error ? e.message : text('验证码发送失败', 'Failed to send verification code'))
    } finally {
      setSendingCode(false)
      if (turnstileActive) turnstile.reset()
    }
  }

  function validatePassword(pw: string) {
    if (!pw) { setPasswordHint(''); return }
    const hasLetter = /[a-zA-Z]/.test(pw)
    const hasDigit = /\d/.test(pw)
    if (pw.length <= 8) setPasswordHint(t('auth.passwordTooShort'))
    else if (!hasLetter || !hasDigit) setPasswordHint(t('auth.passwordMixed'))
    else setPasswordHint('')
  }

  function resetForm() {
    setVerificationCode(''); setPassword(''); setDisplayName(''); setCodeMessage(''); setCodeError(''); setCountdown(0); setPasswordHint(''); setTurnstileRequired(false)
  }

  function updateEmail(value: string) {
    setEmail(value)
    if (turnstileRequired) setTurnstileRequired(false)
  }

  function switchMode(next: 'login' | 'register' | 'forgot') {
    resetForm()
    setMode(next)
  }

  if (user) return <PixPanel eyebrow={text('账户', 'Account')} title={text('已进入工位台', 'Workbench connected')} description={text('账户已连接，可以开始创建素材、查看作品和管理点数。', 'Your account is connected. You can create assets, review works, and manage credits.')} action={<Button variant="outline" onClick={onLogout}>{text('退出', 'Sign out')}</Button>}><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-lg font-semibold">{user.display_name || user.email}</p><p className="text-sm text-muted-foreground">{user.email}</p></div><Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>{user.role === 'admin' ? text('管理员', 'Admin') : text('创作者', 'Creator')}</Badge></div><Alert className="mt-4" variant="success">{text('身份已验证，任务和点数会在后台持续同步。', 'Identity verified. Jobs and credits will keep syncing in the background.')}</Alert></PixPanel>

  // ── 忘记密码模式 ────────────────────────────────────────────
  if (isForgot) {
    return (
      <PixPanel
        eyebrow={t('auth.resetPassword')}
        title={t('auth.resetPassword')}
        description={t('auth.resetDescription')}
        action={<Button type="button" variant="outline" onClick={() => switchMode('login')}>{t('auth.backToLogin')}</Button>}
      >
        <form className="grid gap-4" onSubmit={submit}>
          <PixField label={text('邮箱', 'Email')}>
            <Input type="email" value={email} autoComplete="email" onChange={(e) => updateEmail(e.target.value)} required />
          </PixField>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <PixField label={text('邮箱验证码', 'Verification code')}>
              <Input value={verificationCode} autoComplete="one-time-code" inputMode="numeric" maxLength={6} placeholder={t('auth.resetCodePlaceholder')} onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))} required />
            </PixField>
            <Button
              type="button"
              variant="outline"
              className="self-end"
              onClick={requestCode}
              disabled={loading || sendingCode || countdown > 0 || (turnstileActive && !turnstile.ready)}
            >
              {sendingCode ? t('auth.sending') : countdown > 0 ? t('auth.codeExpires', { seconds: countdown }) : t('auth.sendCode')}
            </Button>
          </div>
          {codeMessage && <Alert variant="info">{codeMessage}</Alert>}
          {codeError && <Alert variant="destructive">{codeError}</Alert>}
          <PixField label={t('auth.newPassword')} hint={passwordHint ? <span className="text-destructive">{passwordHint}</span> : t('auth.passwordRule')}>
            <Input type="password" value={password} autoComplete="new-password" minLength={9} maxLength={128} placeholder={t('auth.newPasswordPlaceholder')} onChange={(e) => { setPassword(e.target.value); validatePassword(e.target.value) }} required />
          </PixField>
          {turnstileActive && (
            <div className="grid gap-2">
              <div ref={turnstile.containerRef} className="cf-turnstile min-h-[65px]" />
              {turnstile.error && <Alert variant="destructive">{turnstile.error}</Alert>}
            </div>
          )}
          <Button type="submit" size="lg" disabled={loading || !verificationCode || password.length <= 8 || !!passwordHint}>
            {loading ? t('auth.resetting') : t('auth.confirmReset')}
          </Button>
        </form>
      </PixPanel>
    )
  }

  // ── 登录 / 注册模式 ────────────────────────────────────────
  return (
    <PixPanel
      eyebrow={text('账户', 'Account')}
      title={isRegister ? text('邮箱验证注册', 'Register with email verification') : text('登录工作台', 'Sign in to workspace')}
      description={isRegister ? registrationBonusCopy || text('验证码用于确认创作者邮箱。', 'The verification code confirms the creator email.') : text('回到你的像素素材生产线，继续批量生成、筛选和导出。', 'Return to your pixel asset pipeline to batch generate, review, and export.')}
      action={
        <div className="grid gap-2 justify-items-end">
          {!isRegister && registrationBonusCopy && <Badge variant="secondary">{registrationBonusCopy}</Badge>}
          <Button type="button" variant="outline" onClick={() => switchMode(isRegister ? 'login' : 'register')}>{isRegister ? text('登录', 'Sign in') : text('注册', 'Register')}</Button>
        </div>
      }
    >
      <form className="grid gap-4" onSubmit={submit}>
        {isRegister && referralCode && <Alert variant="success">{t('auth.referralDetected', { code: referralCode })}</Alert>}
        {isRegister && <PixField label={text('昵称', 'Display name')}><Input value={displayName} autoComplete="name" onChange={(e) => setDisplayName(e.target.value)} /></PixField>}
        <PixField label={text('邮箱', 'Email')}><Input type="email" value={email} autoComplete="email" onChange={(e) => updateEmail(e.target.value)} required /></PixField>
        {isRegister && (
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <PixField label={text('邮箱验证码', 'Email verification code')}>
              <Input value={verificationCode} autoComplete="one-time-code" inputMode="numeric" maxLength={6} onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))} required />
            </PixField>
            <Button
              type="button"
              variant="outline"
              className="self-end"
              onClick={requestRegisterCode}
              disabled={loading || sendingCode || countdown > 0 || (turnstileActive && !turnstile.ready)}
            >
              {sendingCode ? text('发送中…', 'Sending…') : countdown > 0 ? text(`${countdown}s 后重发`, `Resend in ${countdown}s`) : text('发送验证码', 'Send code')}
            </Button>
          </div>
        )}
        {codeMessage && <Alert variant="info">{codeMessage}</Alert>}{codeError && <Alert variant="destructive">{codeError}</Alert>}
        <PixField label={text('密码', 'Password')} hint={isRegister && passwordHint ? <span className="text-destructive">{passwordHint}</span> : isRegister ? t('auth.passwordRule') : undefined}>
          <Input type="password" value={password} autoComplete={isRegister ? 'new-password' : 'current-password'} onChange={(e) => { setPassword(e.target.value); if (isRegister) validatePassword(e.target.value) }} required />
        </PixField>
        {!isRegister && (
          <button type="button" className="justify-self-start -mt-2 text-xs font-semibold text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm" onClick={() => switchMode('forgot')}>
            {t('auth.forgotPassword')}
          </button>
        )}
        {localTestLoginAvailable && <Alert variant="info" className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span>{text(`仅本地访问可用：用 ${localTestAccountEmail} 快速测试工作台。`, `Local access only: use ${localTestAccountEmail} to quickly test the workspace.`)}</span><Button type="button" variant="outline" onClick={onLocalTestLogin} disabled={loading}>{text('使用本地测试账号', 'Use local test account')}</Button></Alert>}
        {isRegister && turnstileActive && (
          <div className="grid gap-2">
            <div ref={turnstile.containerRef} className="cf-turnstile min-h-[65px]" />
            {turnstile.error && <Alert variant="destructive">{turnstile.error}</Alert>}
          </div>
        )}
        <Button type="submit" size="lg" disabled={loading || (isRegister && !!passwordHint)}>{loading ? text('处理中…', 'Processing…') : isRegister ? text('验证并注册', 'Verify and register') : text('进入工作台', 'Enter workspace')}</Button>

      </form>
    </PixPanel>
  )
}
