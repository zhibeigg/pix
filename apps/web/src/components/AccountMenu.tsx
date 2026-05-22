import { GalleryHorizontalEnd, LogOut, RefreshCw, Settings, UserRound, WalletCards } from 'lucide-react'
import { useI18n } from '../i18n'
import type { CreditBalance, User } from '../types'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'
import type { AppPage } from './AppTabs'

type AccountMenuProps = {
  user: User
  balance: CreditBalance | null
  activeJobs: number
  completedJobs: number
  failedJobs: number
  isAdmin: boolean
  onNavigate: (page: AppPage) => void
  onRefresh: () => void | Promise<void>
  onLogout: () => void
}

export function AccountMenu({ user, balance, activeJobs, completedJobs, failedJobs, isAdmin, onNavigate, onRefresh, onLogout }: AccountMenuProps) {
  const { text } = useI18n()
  return (
    <div className="flex min-w-0 items-center justify-end gap-2">
      <div className="hidden items-center gap-2 sm:flex">
        <Badge variant="outline" className="bg-card">{text(`点数 ${balance?.available_credits ?? '—'}`, `Credits ${balance?.available_credits ?? '—'}`)}</Badge>
        <Badge variant={activeJobs ? 'info' : 'muted'} className="hidden lg:inline-flex">{text(`队列 ${activeJobs}`, `Queue ${activeJobs}`)}</Badge>
        {failedJobs > 0 && <Badge variant="danger" className="hidden lg:inline-flex">{text(`失败 ${failedJobs}`, `Failed ${failedJobs}`)}</Badge>}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="bg-card"><UserRound />{text('账号', 'Account')}</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel>{text('当前账户', 'Current account')}</DropdownMenuLabel>
          <div className="px-2.5 pb-2">
            <p className="truncate text-sm font-bold">{user.display_name || user.email}</p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge variant={isAdmin ? 'default' : 'secondary'}>{user.role}</Badge>
              <Badge variant="outline">{text(`点数 ${balance?.available_credits ?? '—'}`, `Credits ${balance?.available_credits ?? '—'}`)}</Badge>
              <Badge variant={activeJobs ? 'info' : 'muted'}>{text(`队列 ${activeJobs}`, `Queue ${activeJobs}`)}</Badge>
              <Badge variant="success">{text(`完成 ${completedJobs}`, `Done ${completedJobs}`)}</Badge>
              <Badge variant={failedJobs ? 'danger' : 'muted'}>{text(`失败 ${failedJobs}`, `Failed ${failedJobs}`)}</Badge>
            </div>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => onNavigate('billing')}><WalletCards />{text('点数中心', 'Billing center')}</DropdownMenuItem>
          <DropdownMenuItem onClick={() => onNavigate('gallery')}><GalleryHorizontalEnd />{text('作品库', 'Gallery')}</DropdownMenuItem>
          {isAdmin && <DropdownMenuItem onClick={() => onNavigate('admin')}><Settings />{text('管理后台', 'Admin console')}</DropdownMenuItem>}
          <DropdownMenuItem onClick={() => void onRefresh()}><RefreshCw />{text('刷新数据', 'Refresh data')}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onLogout} className="text-destructive"><LogOut />{text('退出登录', 'Sign out')}</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
