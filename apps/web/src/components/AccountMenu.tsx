import { useState } from 'react'
import { Box, Button, Chip, Divider, Menu, MenuItem, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import type { CreditBalance, User } from '../types'
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
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)

  function close() {
    setAnchorEl(null)
  }

  function go(page: AppPage) {
    close()
    onNavigate(page)
  }

  async function refresh() {
    close()
    await onRefresh()
  }

  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'flex-end' }}>
      <Stack direction="row" spacing={0.75} sx={{ display: { xs: 'none', xl: 'flex' } }}>
        <Chip label={`点数 ${balance?.available_credits ?? '—'}`} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} />
        <Chip label={`队列 ${activeJobs}`} sx={{ bgcolor: notionTokens.tintSky }} />
        <Chip label={`完成 ${completedJobs}`} sx={{ bgcolor: notionTokens.tintMint }} />
        <Chip label={`失败 ${failedJobs}`} sx={{ bgcolor: failedJobs ? notionTokens.tintRose : notionTokens.tintGray }} />
      </Stack>
      <Button variant="outlined" onClick={(event) => setAnchorEl(event.currentTarget)} aria-controls={open ? 'account-menu' : undefined} aria-haspopup="true" aria-expanded={open ? 'true' : undefined}>
        账号管理
      </Button>
      <Button variant="text" onClick={onLogout} sx={{ color: notionTokens.steel }}>退出登录</Button>
      <Menu id="account-menu" anchorEl={anchorEl} open={open} onClose={close} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
        <Box sx={{ px: 2, py: 1.5, minWidth: 260 }}>
          <Typography variant="caption" color="text.secondary">当前账户</Typography>
          <Typography sx={{ fontWeight: 600 }}>{user.display_name || user.email}</Typography>
          <Typography variant="body2" color="text.secondary">{user.email}</Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
            <Chip size="small" label={user.role} sx={{ bgcolor: isAdmin ? notionTokens.tintLavender : notionTokens.tintGray, color: isAdmin ? notionTokens.brandPurple800 : notionTokens.ink }} />
            <Chip size="small" label={`点数 ${balance?.available_credits ?? '—'}`} sx={{ bgcolor: notionTokens.tintCream }} />
          </Stack>
        </Box>
        <Divider />
        <MenuItem onClick={() => go('billing')}>点数中心</MenuItem>
        <MenuItem onClick={() => go('gallery')}>作品库</MenuItem>
        {isAdmin && <MenuItem onClick={() => go('admin')}>管理后台</MenuItem>}
        <MenuItem onClick={refresh}>刷新数据</MenuItem>
        <Divider />
        <MenuItem onClick={() => { close(); onLogout() }}>退出登录</MenuItem>
      </Menu>
    </Stack>
  )
}
