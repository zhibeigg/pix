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
  const { t } = useI18n()
  return (
    <div className="flex min-w-0 items-center justify-end gap-2">
      <div className="hidden items-center gap-2 sm:flex">
        <Badge variant="outline" className="bg-card">{t('account.credits', { count: balance?.available_credits ?? '—' })}</Badge>
        <Badge variant={activeJobs ? 'info' : 'muted'} className="hidden lg:inline-flex">{t('account.queue', { count: activeJobs })}</Badge>
        {failedJobs > 0 && <Badge variant="danger" className="hidden lg:inline-flex">{t('account.failed', { count: failedJobs })}</Badge>}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="bg-card"><UserRound />{t('account.button')}</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel>{t('account.current')}</DropdownMenuLabel>
          <div className="px-2.5 pb-2">
            <p className="truncate text-sm font-bold">{user.display_name || user.email}</p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge variant={isAdmin ? 'default' : 'secondary'}>{user.role}</Badge>
              <Badge variant="outline">{t('account.credits', { count: balance?.available_credits ?? '—' })}</Badge>
              <Badge variant={activeJobs ? 'info' : 'muted'}>{t('account.queue', { count: activeJobs })}</Badge>
              <Badge variant="success">{t('account.done', { count: completedJobs })}</Badge>
              <Badge variant={failedJobs ? 'danger' : 'muted'}>{t('account.failed', { count: failedJobs })}</Badge>
            </div>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => onNavigate('billing')}><WalletCards />{t('account.billingCenter')}</DropdownMenuItem>
          <DropdownMenuItem onClick={() => onNavigate('gallery')}><GalleryHorizontalEnd />{t('account.gallery')}</DropdownMenuItem>
          {isAdmin && <DropdownMenuItem onClick={() => onNavigate('admin')}><Settings />{t('account.adminConsole')}</DropdownMenuItem>}
          <DropdownMenuItem onClick={() => void onRefresh()}><RefreshCw />{t('account.refreshData')}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onLogout} className="text-destructive"><LogOut />{t('account.signOut')}</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
