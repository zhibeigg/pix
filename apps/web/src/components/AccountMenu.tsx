import { GalleryHorizontalEnd, LogOut, RefreshCw, Settings, UserRound, WalletCards } from 'lucide-react'
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
  return (
    <div className="flex min-w-0 items-center justify-end gap-2">
      <div className="hidden items-center gap-2 sm:flex">
        <Badge variant="outline" className="bg-card">点数 {balance?.available_credits ?? '—'}</Badge>
        <Badge variant={activeJobs ? 'info' : 'muted'} className="hidden lg:inline-flex">队列 {activeJobs}</Badge>
        {failedJobs > 0 && <Badge variant="danger" className="hidden lg:inline-flex">失败 {failedJobs}</Badge>}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="bg-card"><UserRound />账号</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel>当前账户</DropdownMenuLabel>
          <div className="px-2.5 pb-2">
            <p className="truncate text-sm font-bold">{user.display_name || user.email}</p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge variant={isAdmin ? 'default' : 'secondary'}>{user.role}</Badge>
              <Badge variant="outline">点数 {balance?.available_credits ?? '—'}</Badge>
              <Badge variant={activeJobs ? 'info' : 'muted'}>队列 {activeJobs}</Badge>
              <Badge variant="success">完成 {completedJobs}</Badge>
              <Badge variant={failedJobs ? 'danger' : 'muted'}>失败 {failedJobs}</Badge>
            </div>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => onNavigate('billing')}><WalletCards />点数中心</DropdownMenuItem>
          <DropdownMenuItem onClick={() => onNavigate('gallery')}><GalleryHorizontalEnd />作品库</DropdownMenuItem>
          {isAdmin && <DropdownMenuItem onClick={() => onNavigate('admin')}><Settings />管理后台</DropdownMenuItem>}
          <DropdownMenuItem onClick={() => void onRefresh()}><RefreshCw />刷新数据</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onLogout} className="text-destructive"><LogOut />退出登录</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
