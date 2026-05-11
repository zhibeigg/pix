import { FormEvent, useEffect, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Chip, Stack, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import type { EmailCodeResponse, User } from '../types'

type AuthPanelProps = {
  user: User | null
  onLogin: (email: string, password: string) => Promise<void>
  onRegister: (email: string, password: string, displayName: string, verificationCode: string) => Promise<void>
  onRequestRegisterCode: (email: string) => Promise<EmailCodeResponse>
  onLogout: () => void
  loading: boolean
}

export function AuthPanel({ user, onLogin, onRegister, onRequestRegisterCode, onLogout, loading }: AuthPanelProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('password123')
  const [displayName, setDisplayName] = useState('Pix Admin')
  const [verificationCode, setVerificationCode] = useState('')
  const [codeMessage, setCodeMessage] = useState('')
  const [codeError, setCodeError] = useState('')
  const [sendingCode, setSendingCode] = useState(false)
  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    if (countdown <= 0) return undefined
    const timer = window.setTimeout(() => setCountdown((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearTimeout(timer)
  }, [countdown])

  useEffect(() => {
    if (mode === 'login') {
      setCountdown(0)
      setVerificationCode('')
      setCodeMessage('')
      setCodeError('')
    }
  }, [mode])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (mode === 'login') {
      await onLogin(email, password)
    } else {
      await onRegister(email, password, displayName, verificationCode)
    }
  }

  async function requestCode() {
    const targetEmail = email.trim()
    if (!targetEmail) {
      setCodeError('请先填写邮箱')
      return
    }
    setSendingCode(true)
    setCodeMessage('')
    setCodeError('')
    try {
      const result = await onRequestRegisterCode(targetEmail)
      setCountdown(result.retry_after_seconds || 60)
      setCodeMessage(result.debug_code ? `验证码已发送。测试验证码：${result.debug_code}` : '验证码已发送，请查看邮箱')
    } catch (error) {
      setCodeError(error instanceof Error ? error.message : '验证码发送失败')
    } finally {
      setSendingCode(false)
    }
  }

  if (user) {
    return (
      <Card variant="outlined" sx={{ bgcolor: notionTokens.tintCream }}>
        <CardContent>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' }, gap: 2 }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>当前账户</Typography>
              <Typography variant="h5" sx={{ fontWeight: 600 }}>{user.display_name || user.email}</Typography>
              <Typography color="text.secondary" sx={{ mb: 1 }}>{user.email}</Typography>
              <Chip label={user.role} sx={{ bgcolor: user.role === 'admin' ? notionTokens.tintLavender : notionTokens.tintGray, color: user.role === 'admin' ? notionTokens.brandPurple800 : notionTokens.ink }} />
            </Box>
            <Button variant="outlined" onClick={onLogout}>退出登录</Button>
          </Stack>
        </CardContent>
      </Card>
    )
  }

  const codeButtonText = sendingCode ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : '发送验证码'

  return (
    <Card variant="outlined" sx={{ boxShadow: notionTokens.liftShadow }}>
      <CardContent>
        <Stack spacing={2.5}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>账户</Typography>
              <Typography variant="h5" sx={{ fontWeight: 600 }}>{mode === 'login' ? '登录工作台' : '邮箱验证注册'}</Typography>
            </Box>
            <Button variant="outlined" type="button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? '注册' : '登录'}
            </Button>
          </Stack>
          <Stack component="form" spacing={2} onSubmit={submit}>
            {mode === 'register' && (
              <TextField label="昵称" value={displayName} autoComplete="name" onChange={(event) => setDisplayName(event.target.value)} />
            )}
            <TextField label="邮箱" type="email" value={email} autoComplete="email" onChange={(event) => setEmail(event.target.value)} />
            {mode === 'register' && (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
                <TextField
                  label="邮箱验证码"
                  value={verificationCode}
                  autoComplete="one-time-code"
                  slotProps={{ htmlInput: { inputMode: 'numeric', pattern: '[0-9]*', maxLength: 6 } }}
                  onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                  sx={{ flex: 1 }}
                />
                <Button type="button" variant="outlined" onClick={requestCode} disabled={loading || sendingCode || countdown > 0} sx={{ minWidth: 128 }}>
                  {codeButtonText}
                </Button>
              </Stack>
            )}
            {codeMessage && <Alert severity="info">{codeMessage}</Alert>}
            {codeError && <Alert severity="error">{codeError}</Alert>}
            <TextField label="密码" type="password" value={password} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} onChange={(event) => setPassword(event.target.value)} />
            <Button type="submit" variant="contained" color="primary" disabled={loading}>{loading ? '处理中…' : mode === 'login' ? '登录' : '验证并注册'}</Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}
