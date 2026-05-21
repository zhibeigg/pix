import { FormEvent, useState } from 'react'
import type { SetupStatus } from '../types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'

export function SetupWizard({ status, loading, onBootstrapAdmin, onLocalTestLogin }: { status: SetupStatus; loading: boolean; onBootstrapAdmin: (email: string, password: string, displayName: string) => Promise<void>; onLocalTestLogin: () => Promise<void> }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  async function submit(event: FormEvent) { event.preventDefault(); await onBootstrapAdmin(email, password, displayName) }
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <PixPanel eyebrow="初始化" title="创建第一个管理员" description={`当前用户 ${status.user_count} 个，管理员 ${status.admin_count} 个。`}>
        <form className="grid gap-4" onSubmit={submit}>
          <PixField label="昵称"><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></PixField>
          <PixField label="邮箱"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></PixField>
          <PixField label="密码"><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></PixField>
          <Button type="submit" size="lg" disabled={loading}>{loading ? '创建中…' : '创建管理员'}</Button>
          {status.local_test_login_available && <Alert variant="info" className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span>仅本地访问可用：可以先用 {status.local_test_account_email} 测试工作台，不会替代管理员初始化。</span><Button type="button" variant="outline" onClick={onLocalTestLogin} disabled={loading}>使用本地测试账号</Button></Alert>}
        </form>
      </PixPanel>
    </div>
  )
}
