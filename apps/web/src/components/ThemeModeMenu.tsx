import { Laptop, Moon, Sun } from 'lucide-react'
import type { PixThemeMode, PixThemePreference } from '../theme'
import { Button } from './ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'

interface ThemeModeMenuProps {
  preference: PixThemePreference
  resolvedMode: PixThemeMode
  systemMode: PixThemeMode
  onChange: (preference: PixThemePreference) => void
}

export function ThemeModeMenu({ preference, resolvedMode, systemMode, onChange }: ThemeModeMenuProps) {
  const Icon = preference === 'system' ? Laptop : resolvedMode === 'dark' ? Moon : Sun
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" aria-label="选择主题模式" className="rounded-full bg-card">
          <Icon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>主题模式</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={preference} onValueChange={(value) => onChange(value as PixThemePreference)}>
          <DropdownMenuRadioItem value="light"><Sun className="h-4 w-4" />浅色模式</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark"><Moon className="h-4 w-4" />深色模式</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system"><Laptop className="h-4 w-4" />跟随系统</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>系统当前：{systemMode === 'dark' ? '深色' : '浅色'}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
