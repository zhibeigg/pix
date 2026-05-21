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

  function logout() {
    close()
    onLogout()
  }

  return (
    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', justifyContent: 'flex-end', minWidth: 0, flexWrap: 'nowrap' }}>
      <Stack direction="row" spacing={0.75} sx={{ display: { xs: 'none', sm: 'flex' }, minWidth: 0, '& .MuiChip-root': { height: 34 } }}>
        <Chip size="small" label={`点数 ${balance?.available_credits ?? '—'}`} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} />
        <Chip size="small" label={`队列 ${activeJobs}`} sx={{ display: { xs: 'none', lg: 'inline-flex' }, bgcolor: notionTokens.tintSky }} />
        {failedJobs > 0 && <Chip size="small" label={`失败 ${failedJobs}`} sx={{ display: { xs: 'none', lg: 'inline-flex' }, bgcolor: notionTokens.tintRose }} />}
      </Stack>
      <Button
        variant="outlined"
        onClick={(event) => setAnchorEl(event.currentTarget)}
        aria-controls={open ? 'account-menu' : undefined}
        aria-haspopup="true"
        aria-expanded={open ? 'true' : undefined}
        sx={{ minWidth: { xs: 52, sm: 92 }, px: { xs: 1.25, sm: 1.75 }, whiteSpace: 'nowrap' }}
      >
        <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>账号管理</Box>
        <Box component="span" sx={{ display: { xs: 'inline', sm: 'none' } }}>账号</Box>
      </Button>
      <Menu id="account-menu" anchorEl={anchorEl} open={open} onClose={close} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
        <Box sx={{ px: 2, py: 1.5, minWidth: 280 }}>
          <Typography variant="caption" color="text.secondary">当前账户</Typography>
          <Typography sx={{ fontWeight: 600 }}>{user.display_name || user.email}</Typography>
          <Typography variant="body2" color="text.secondary">{user.email}</Typography>
          <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: .75 }}>
            <Chip size="small" label={user.role} sx={{ bgcolor: isAdmin ? notionTokens.tintLavender : notionTokens.tintGray, color: isAdmin ? notionTokens.brandPurple800 : notionTokens.ink }} />
            <Chip size="small" label={`点数 ${balance?.available_credits ?? '—'}`} sx={{ bgcolor: notionTokens.tintCream }} />
            <Chip size="small" label={`队列 ${activeJobs}`} sx={{ bgcolor: notionTokens.tintSky }} />
            <Chip size="small" label={`完成 ${completedJobs}`} sx={{ bgcolor: notionTokens.tintMint }} />
            <Chip size="small" label={`失败 ${failedJobs}`} sx={{ bgcolor: failedJobs ? notionTokens.tintRose : notionTokens.tintGray }} />
          </Box>
        </Box>
        <Divider />
        <MenuItem onClick={() => go('billing')}>点数中心</MenuItem>
        <MenuItem onClick={() => go('gallery')}>作品库</MenuItem>
        {isAdmin && <MenuItem onClick={() => go('admin')}>管理后台</MenuItem>}
        <MenuItem onClick={refresh}>刷新数据</MenuItem>
        <Divider />
        <MenuItem onClick={logout}>退出登录</MenuItem>
      </Menu>
    </Stack>
  )
}
