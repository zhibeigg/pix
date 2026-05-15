import { useState } from 'react'
import { Box, Button, Divider, Menu, MenuItem, Stack, Typography } from '@mui/material'
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined'
import DesktopWindowsOutlinedIcon from '@mui/icons-material/DesktopWindowsOutlined'
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined'
import { notionTokens, type PixThemeMode, type PixThemePreference } from '../theme'

type ThemeModeMenuProps = {
  preference: PixThemePreference
  resolvedMode: PixThemeMode
  systemMode: PixThemeMode
  onChange: (preference: PixThemePreference) => void
}

const themeOptions: Array<{
  value: PixThemePreference
  title: string
  description: string
  icon: typeof LightModeOutlinedIcon
}> = [
  { value: 'light', title: '浅色模式', description: '始终使用浅色主题', icon: LightModeOutlinedIcon },
  { value: 'dark', title: '深色模式', description: '始终使用深色主题', icon: DarkModeOutlinedIcon },
  { value: 'system', title: '自动模式', description: '跟随系统主题设置', icon: DesktopWindowsOutlinedIcon },
]

export function ThemeModeMenu({ preference, resolvedMode, systemMode, onChange }: ThemeModeMenuProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)
  const TriggerIcon = preference === 'system'
    ? DesktopWindowsOutlinedIcon
    : resolvedMode === 'dark'
      ? DarkModeOutlinedIcon
      : LightModeOutlinedIcon

  function close() {
    setAnchorEl(null)
  }

  function select(next: PixThemePreference) {
    onChange(next)
    close()
  }

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        onClick={(event) => setAnchorEl(event.currentTarget)}
        aria-controls={open ? 'theme-mode-menu' : undefined}
        aria-haspopup="true"
        aria-expanded={open ? 'true' : undefined}
        aria-label="选择主题模式"
        sx={{
          minWidth: 40,
          width: 40,
          height: 40,
          p: 0,
          borderRadius: 999,
          bgcolor: notionTokens.surface,
          transition: 'transform .12s ease, box-shadow .18s ease, border-color .18s ease',
          '&:hover': { transform: 'translateY(-1px)', boxShadow: notionTokens.cardShadow },
          '&:active': { transform: 'translateY(1px)' },
          '@media (prefers-reduced-motion: reduce)': { '&, &:hover, &:active': { transform: 'none' } },
        }}
      >
        <TriggerIcon fontSize="small" />
      </Button>
      <Menu
        id="theme-mode-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{
          list: { 'aria-label': '主题模式' },
          paper: {
            sx: {
              mt: 1,
              minWidth: 236,
              overflow: 'hidden',
              bgcolor: notionTokens.canvas,
              border: `1px solid ${notionTokens.hairlineStrong}`,
              borderRadius: 1,
              boxShadow: notionTokens.mockupShadow,
            },
          },
        }}
      >
        {themeOptions.map((option) => {
          const Icon = option.icon
          const active = preference === option.value
          return (
            <MenuItem
              key={option.value}
              role="menuitemradio"
              aria-checked={active}
              onClick={() => select(option.value)}
              sx={{
                alignItems: 'flex-start',
                gap: 1.4,
                px: 2,
                py: 1.25,
                bgcolor: active ? notionTokens.brandNavyMid : 'transparent',
                color: active ? notionTokens.onDark : notionTokens.ink,
                '&:hover': { bgcolor: active ? notionTokens.brandNavyMid : notionTokens.surface },
              }}
            >
              <Box
                sx={{
                  width: 28,
                  height: 28,
                  mt: .1,
                  display: 'grid',
                  placeItems: 'center',
                  borderRadius: 1,
                  bgcolor: active ? 'rgba(255,255,255,.14)' : notionTokens.surface,
                  color: active ? notionTokens.onDark : notionTokens.slate,
                  boxShadow: active ? 'inset 0 0 0 1px rgba(255,255,255,.18)' : `inset 0 0 0 1px ${notionTokens.hairline}`,
                }}
              >
                <Icon fontSize="small" />
              </Box>
              <Stack spacing={.15}>
                <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.25 }}>{option.title}</Typography>
                <Typography variant="caption" sx={{ color: active ? notionTokens.onDarkMuted : notionTokens.slate }}>{option.description}</Typography>
              </Stack>
            </MenuItem>
          )
        })}
        <Divider sx={{ borderColor: notionTokens.hairline }} />
        <Box sx={{ px: 2, py: 1.25, bgcolor: notionTokens.surface, color: notionTokens.steel }}>
          <Typography variant="caption">
            当前跟随系统：{systemMode === 'dark' ? '深色' : '浅色'}
          </Typography>
        </Box>
      </Menu>
    </>
  )
}
