import { AdminPanel } from '../components/AdminPanel'

type AdminPageProps = {
  token: string
  onNotify?: (message: string, variant?: 'info' | 'success' | 'error') => void
}

export function AdminPage({ token, onNotify }: AdminPageProps) {
  return <AdminPanel token={token} onNotify={onNotify} />
}
