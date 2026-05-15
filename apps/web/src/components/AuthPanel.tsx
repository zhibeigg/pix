import { FormEvent, useEffect, useState } from 'react'
import { Box, Button, Stack, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import type { EmailCodeResponse, User } from '../types'
import { AuthCardFrame, AuthInlineAlert, authTextFieldSx } from './AuthWorkbenchKit'

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
    setCodeMessage('')
    setCodeError('')
    if (mode === 'login') {
      setCountdown(0)
      setVerificationCode('')
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
      <AuthCardFrame
        eyebrow="账户"
        title="已进入工位台"
        subtitle="账户已连接，可以开始创建素材、查看作品和管理点数。"
        actionLabel="退出"
        onAction={onLogout}
      >
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr auto' }, gap: 2, alignItems: 'center' }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ color: notionTokens.onDark, fontWeight: 600, fontSize: 20 }} noWrap>{user.display_name || user.email}</Typography>
            <Typography sx={{ color: notionTokens.onDarkMuted, mt: .5 }} noWrap>{user.email}</Typography>
          </Box>
          <Box sx={{ justifySelf: { xs: 'start', sm: 'end' }, px: 1.4, py: .8, borderRadius: '8px', bgcolor: user.role === 'admin' ? 'oklch(28% .07 295)' : 'oklch(24% .05 250)', color: notionTokens.onDark, fontWeight: 600 }}>
            {user.role === 'admin' ? '管理员' : '创作者'}
          </Box>
        </Box>
        <AuthInlineAlert severity="success">身份已验证，任务和点数会在后台持续同步。</AuthInlineAlert>
      </AuthCardFrame>
    )
  }

  const isRegister = mode === 'register'
  const codeButtonText = sendingCode ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : '发送验证码'

  return (
    <AuthCardFrame
      eyebrow="账户"
      title={isRegister ? '邮箱验证注册' : '登录工作台'}
      subtitle={isRegister ? '验证码用于确认创作者邮箱；开发环境会在 console 模式下直接显示测试码。' : '回到你的像素素材生产线，继续批量生成、筛选和导出。'}
      actionLabel={isRegister ? '登录' : '注册'}
      onAction={() => setMode(isRegister ? 'login' : 'register')}
    >
      <Stack component="form" spacing={2} onSubmit={submit}>
        {isRegister && (
          <TextField label="昵称" value={displayName} autoComplete="name" onChange={(event) => setDisplayName(event.target.value)} sx={authTextFieldSx} />
        )}
        <TextField label="邮箱" type="email" value={email} autoComplete="email" onChange={(event) => setEmail(event.target.value)} required sx={authTextFieldSx} />
        {isRegister && (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
            <TextField
              label="邮箱验证码"
              value={verificationCode}
              autoComplete="one-time-code"
              slotProps={{ htmlInput: { inputMode: 'numeric', pattern: '[0-9]*', maxLength: 6 } }}
              onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
              sx={[authTextFieldSx, { flex: 1 }]}
              required
            />
            <Button
              type="button"
              variant="outlined"
              onClick={requestCode}
              disabled={loading || sendingCode || countdown > 0}
              sx={{
                minHeight: 56,
                minWidth: 128,
                borderColor: 'oklch(58% .06 254)',
                color: notionTokens.onDark,
                bgcolor: 'oklch(14% .024 263)',
                '&:hover': { borderColor: 'oklch(78% .07 250)', bgcolor: 'oklch(20% .036 263)' },
              }}
            >
              {codeButtonText}
            </Button>
          </Stack>
        )}
        {codeMessage && <AuthInlineAlert severity="info">{codeMessage}</AuthInlineAlert>}
        {codeError && <AuthInlineAlert severity="error">{codeError}</AuthInlineAlert>}
        <TextField label="密码" type="password" value={password} autoComplete={isRegister ? 'new-password' : 'current-password'} onChange={(event) => setPassword(event.target.value)} required sx={authTextFieldSx} />
        <Button type="submit" variant="contained" color="primary" disabled={loading} sx={{ minHeight: 48, bgcolor: 'oklch(71% .17 296)', color: 'oklch(12% .028 263)', fontWeight: 600, '&:hover': { bgcolor: 'oklch(76% .16 296)' } }}>
          {loading ? '处理中…' : isRegister ? '验证并注册' : '进入工作台'}
        </Button>
      </Stack>
    </AuthCardFrame>
  )
}
