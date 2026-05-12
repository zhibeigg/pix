import { FormEvent, useState } from 'react'
import { Button, Stack, TextField } from '@mui/material'
import type { SetupStatus } from '../types'
import { AuthCardFrame, AuthInlineAlert, AuthScene, authTextFieldSx } from './AuthWorkbenchKit'

type SetupWizardProps = {
  status: SetupStatus
  loading: boolean
  onBootstrapAdmin: (email: string, password: string, displayName: string) => Promise<void>
}

export function SetupWizard({ status, loading, onBootstrapAdmin }: SetupWizardProps) {
  const [email, setEmail] = useState('admin@example.com')
  const [displayName, setDisplayName] = useState('Pix Admin')
  const [password, setPassword] = useState('password123')
  const [confirmPassword, setConfirmPassword] = useState('password123')
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    if (password.length < 8) {
      setError('密码至少 8 位')
      return
    }
    await onBootstrapAdmin(email.trim(), password, displayName.trim())
  }

  return (
    <AuthScene
      label="首次启动"
      title="初始化 Pix Forge"
      description="当前站点还没有管理员。先创建唯一的初始管理员，再进入管理后台配置邮件、模型、素材默认值、价格和充值套餐。"
      stats={[
        { label: '用户', value: status.user_count },
        { label: '管理员', value: status.admin_count },
        { label: '邮件', value: status.email_provider },
      ]}
    >
      <AuthCardFrame
        eyebrow="Admin Bootstrap"
        title="创建管理员账户"
        subtitle="该入口只在空用户表时可用，创建后会自动关闭。"
      >
        <Stack component="form" spacing={2} onSubmit={submit}>
          <TextField label="管理员邮箱" type="email" value={email} autoComplete="email" onChange={(event) => setEmail(event.target.value)} required sx={authTextFieldSx} />
          <TextField label="昵称" value={displayName} autoComplete="name" onChange={(event) => setDisplayName(event.target.value)} sx={authTextFieldSx} />
          <TextField label="密码" type="password" value={password} autoComplete="new-password" onChange={(event) => setPassword(event.target.value)} required sx={authTextFieldSx} />
          <TextField label="确认密码" type="password" value={confirmPassword} autoComplete="new-password" onChange={(event) => setConfirmPassword(event.target.value)} required sx={authTextFieldSx} />
          {error && <AuthInlineAlert severity="error">{error}</AuthInlineAlert>}
          <AuthInlineAlert severity="info">首次管理员不需要邮箱验证码；进入后台后请立即配置 SMTP 或启用 console 调试码。</AuthInlineAlert>
          <Button type="submit" variant="contained" disabled={loading} sx={{ minHeight: 48, bgcolor: 'oklch(71% .17 296)', color: 'oklch(12% .028 263)', fontWeight: 900, '&:hover': { bgcolor: 'oklch(76% .16 296)' } }}>
            {loading ? '初始化中…' : '创建管理员并进入后台'}
          </Button>
        </Stack>
      </AuthCardFrame>
    </AuthScene>
  )
}
