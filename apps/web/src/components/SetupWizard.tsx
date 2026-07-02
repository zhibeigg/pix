import { FormEvent, useState } from 'react'
import { useI18n } from '../i18n'
import type { SetupStatus } from '../types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'

export function SetupWizard({ status, loading, onBootstrapAdmin, onLocalTestLogin }: { status: SetupStatus; loading: boolean; onBootstrapAdmin: (email: string, password: string, displayName: string) => Promise<void>; onLocalTestLogin: () => Promise<void> }) {
  const { text } = useI18n()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  async function submit(event: FormEvent) { event.preventDefault(); await onBootstrapAdmin(email, password, displayName) }
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <PixPanel eyebrow={text('初始化', 'Setup')} title={text('创建第一个管理员', 'Create the first admin')} description={text(`当前用户 ${status.user_count} 个，管理员 ${status.admin_count} 个。`, `Currently ${status.user_count} users and ${status.admin_count} admins.`)}>
        <form className="grid gap-4" onSubmit={submit}>
          <PixField label={text('昵称', 'Display name')}><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></PixField>
          <PixField label={text('邮箱', 'Email')}><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></PixField>
          <PixField label={text('密码', 'Password')}><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></PixField>
          <Button type="submit" size="lg" disabled={loading}>{loading ? text('创建中…', 'Creating…') : text('创建管理员', 'Create admin')}</Button>
          {status.local_test_login_available && <Alert variant="info" className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><span>{text(`仅本地访问可用：可以先用 ${status.local_test_account_email} 测试工作台，不会替代管理员初始化。`, `Local access only: try the workspace with ${status.local_test_account_email} first; it does not replace admin setup.`)}</span><Button type="button" variant="outline" onClick={onLocalTestLogin} disabled={loading}>{text('使用本地测试账号', 'Use local test account')}</Button></Alert>}
        </form>
      </PixPanel>
    </div>
  )
}
