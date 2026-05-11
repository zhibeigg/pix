import { FormEvent, useState } from 'react'
import { Box, Button, Card, CardContent, Chip, Stack, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'
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

  return (
    <Card variant="outlined" sx={{ boxShadow: 'rgba(15, 15, 15, 0.08) 0px 4px 12px 0px' }}>
      <CardContent>
        <Stack spacing={2.5}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>账户</Typography>
              <Typography variant="h5" sx={{ fontWeight: 600 }}>{mode === 'login' ? '登录工作台' : '创建账户'}</Typography>
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
            <TextField label="密码" type="password" value={password} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} onChange={(event) => setPassword(event.target.value)} />
            <Button type="submit" variant="contained" color="primary" disabled={loading}>{loading ? '处理中…' : mode === 'login' ? '登录' : '注册'}</Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}
