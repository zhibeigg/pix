import { FormEvent, useState } from 'react'
import type { SetupStatus } from '../types'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'

export function SetupWizard({ status, loading, onBootstrapAdmin }: { status: SetupStatus; loading: boolean; onBootstrapAdmin: (email: string, password: string, displayName: string) => Promise<void> }) {
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('password123')
  const [displayName, setDisplayName] = useState('Pix Admin')
  async function submit(event: FormEvent) { event.preventDefault(); await onBootstrapAdmin(email, password, displayName) }
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <PixPanel eyebrow="初始化" title="创建第一个管理员" description={`当前用户 ${status.user_count} 个，管理员 ${status.admin_count} 个。`}>
        <form className="grid gap-4" onSubmit={submit}>
          <PixField label="昵称"><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></PixField>
          <PixField label="邮箱"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></PixField>
          <PixField label="密码"><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></PixField>
          <Button type="submit" size="lg" disabled={loading}>{loading ? '创建中…' : '创建管理员'}</Button>
        </form>
      </PixPanel>
    </div>
  )
}
