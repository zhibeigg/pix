import { useState, type ComponentType, type ReactNode } from 'react'
import { Bell, Check, Languages, Megaphone, Monitor, Moon, Plus, Sun } from 'lucide-react'
import type { PixLanguage, PixThemeMode, PixThemePreference } from '../theme'
import { useI18n } from '../i18n'
import { cn } from '../lib/utils'
import { Button } from './ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog'

const ANNOUNCEMENT_MUTE_KEY = 'pix_announcement_muted_date'

const languageOptions: Array<{ value: PixLanguage; label: { zh: string; en: string }; flag: string }> = [
  { value: 'zh-CN', label: { zh: '中文', en: 'Chinese' }, flag: '🇨🇳' },
  { value: 'en', label: { zh: '英文', en: 'English' }, flag: '🇬🇧' },
]

const themeOptions: Array<{ value: PixThemePreference; title: { zh: string; en: string }; description: { zh: string; en: string }; icon: ComponentType<{ className?: string }> }> = [
  { value: 'light', title: { zh: '浅色模式', en: 'Light mode' }, description: { zh: '始终使用浅色主题', en: 'Always use the light theme' }, icon: Sun },
  { value: 'dark', title: { zh: '深色模式', en: 'Dark mode' }, description: { zh: '始终使用深色主题', en: 'Always use the dark theme' }, icon: Moon },
  { value: 'system', title: { zh: '自动模式', en: 'Auto mode' }, description: { zh: '跟随系统主题设置', en: 'Follow the system setting' }, icon: Monitor },
]

interface HeaderUtilityBarProps {
  language: PixLanguage
  themePreference: PixThemePreference
  resolvedMode: PixThemeMode
  systemMode: PixThemeMode
  onLanguageChange: (language: PixLanguage) => void
  onThemePreferenceChange: (preference: PixThemePreference) => void
}

type UtilityMenu = 'theme' | 'language'

export function HeaderUtilityBar({ language, themePreference, resolvedMode, systemMode, onLanguageChange, onThemePreferenceChange }: HeaderUtilityBarProps) {
  const [activeMenu, setActiveMenu] = useState<UtilityMenu | null>(null)
  const [announcementOpen, setAnnouncementOpen] = useState(false)

  function setMenuOpen(menu: UtilityMenu, open: boolean) {
    if (open) setAnnouncementOpen(false)
    setActiveMenu((current) => open ? menu : current === menu ? null : current)
  }

  function changeAnnouncementOpen(open: boolean) {
    if (open) setActiveMenu(null)
    setAnnouncementOpen(open)
  }

  return (
    <div className="flex items-center gap-1.5">
      <AnnouncementButton open={announcementOpen} onOpenChange={changeAnnouncementOpen} />
      <ThemeHoverMenu open={activeMenu === 'theme'} onOpenChange={(open) => setMenuOpen('theme', open)} preference={themePreference} resolvedMode={resolvedMode} systemMode={systemMode} onChange={onThemePreferenceChange} />
      <LanguageHoverMenu open={activeMenu === 'language'} onOpenChange={(open) => setMenuOpen('language', open)} language={language} onChange={onLanguageChange} />
    </div>
  )
}

function AnnouncementButton({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { text } = useI18n()
  function muteToday() {
    localStorage.setItem(ANNOUNCEMENT_MUTE_KEY, todayKey())
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} modal={false}>
      <DialogTrigger asChild>
        <button type="button" className={utilityButtonClass} aria-label={text('打开系统公告', 'Open announcements')}>
          <Bell className="h-4 w-4" />
        </button>
      </DialogTrigger>
      <DialogContent onCloseAutoFocus={(event) => event.preventDefault()} className="min-h-[456px] w-[min(92vw,920px)] content-start gap-0 p-0">
        <div className="flex items-start justify-between gap-6 px-6 pb-4 pt-8 md:px-7">
          <DialogHeader className="gap-0">
            <DialogTitle className="text-2xl font-semibold tracking-[-0.02em]">{text('系统公告', 'Announcements')}</DialogTitle>
            <DialogDescription className="sr-only">{text('查看系统通知和公告。', 'View system notifications and announcements.')}</DialogDescription>
          </DialogHeader>
          <div className="mr-8 flex items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-[hsl(var(--pix-sky))] px-3 py-2 font-semibold text-[hsl(var(--pix-link-blue))]">
              <Bell className="h-4 w-4" />{text('通知', 'Notifications')}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[hsl(var(--pix-steel))]">
              <Megaphone className="h-4 w-4" />{text('系统公告', 'Announcements')}
            </span>
          </div>
        </div>

        <div className="grid min-h-[300px] place-items-center px-6 py-4">
          <div className="grid justify-items-center gap-4 text-center">
            <EmptyAnnouncementArt />
            <p className="text-sm text-[hsl(var(--pix-slate))]">{text('暂无公告', 'No announcements')}</p>
          </div>
        </div>

        <DialogFooter className="px-6 pb-6 md:px-7">
          <Button type="button" variant="soft" onClick={muteToday}>{text('今日关闭', 'Dismiss today')}</Button>
          <DialogClose asChild><Button type="button">{text('关闭公告', 'Close')}</Button></DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ThemeHoverMenu({ open, preference, resolvedMode, systemMode, onChange, onOpenChange }: { open: boolean; preference: PixThemePreference; resolvedMode: PixThemeMode; systemMode: PixThemeMode; onChange: (preference: PixThemePreference) => void; onOpenChange: (open: boolean) => void }) {
  const { text } = useI18n()
  const TriggerIcon = preference === 'system' ? Monitor : resolvedMode === 'dark' ? Moon : Sun
  return (
    <HoverMenu
      open={open}
      onOpenChange={onOpenChange}
      trigger={(
        <button type="button" className={cn(utilityButtonClass, open && utilityButtonActiveClass)} aria-label={text('切换黑白主题', 'Switch color theme')} aria-expanded={open}>
          <TriggerIcon className="h-4 w-4" />
        </button>
      )}
    >
      <div role="radiogroup" aria-label={text('主题模式', 'Theme mode')} className="w-48 rounded-lg border border-border bg-popover p-1.5 text-popover-foreground shadow-[0_16px_48px_-8px_rgba(15,15,15,0.16)]">
        {themeOptions.map((option) => {
          const Icon = option.icon
          const active = preference === option.value
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => { onChange(option.value); onOpenChange(false) }}
              role="radio"
              aria-checked={active}
              className={cn('flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left text-popover-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/7', active && 'bg-[hsl(var(--pix-sky))] text-[hsl(var(--pix-link-blue))] dark:bg-white/7 dark:text-white dark:ring-1 dark:ring-white/12')}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-sm font-semibold leading-tight">{text(option.title.zh, option.title.en)}{active && <Check className="h-3.5 w-3.5 text-primary" />}</span>
                <span className={cn('mt-1 block text-xs leading-4 text-muted-foreground', active && 'dark:text-white/55')}>{text(option.description.zh, option.description.en)}</span>
              </span>
            </button>
          )
        })}
        <div className="px-3 pb-1 pt-2 text-[11px] text-muted-foreground">{text('系统当前：', 'System now: ')}{systemMode === 'dark' ? text('深色', 'Dark') : text('浅色', 'Light')}</div>
      </div>
    </HoverMenu>
  )
}

function LanguageHoverMenu({ open, language, onChange, onOpenChange }: { open: boolean; language: PixLanguage; onChange: (language: PixLanguage) => void; onOpenChange: (open: boolean) => void }) {
  const { text } = useI18n()
  return (
    <HoverMenu
      open={open}
      onOpenChange={onOpenChange}
      trigger={(
        <button type="button" className={cn(utilityButtonClass, open && utilityButtonActiveClass)} aria-label={text('切换语言', 'Switch language')} aria-expanded={open}>
          <Languages className="h-4 w-4" />
        </button>
      )}
    >
      <div role="radiogroup" aria-label={text('语言', 'Language')} className="w-36 rounded-lg border border-border bg-popover p-1.5 text-popover-foreground shadow-[0_16px_48px_-8px_rgba(15,15,15,0.16)]">
        {languageOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => { onChange(option.value); onOpenChange(false) }}
            role="radio"
            aria-checked={language === option.value}
            className={cn('flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm text-popover-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/7', language === option.value && 'bg-[hsl(var(--pix-sky))] text-[hsl(var(--pix-link-blue))] dark:bg-white/7 dark:text-white dark:ring-1 dark:ring-white/12')}
          >
            <span className="flex min-w-0 items-center gap-2 whitespace-nowrap"><span className="shrink-0 text-base leading-none">{option.flag}</span><span className="truncate">{text(option.label.zh, option.label.en)}</span></span>
            {language === option.value && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
          </button>
        ))}
      </div>
    </HoverMenu>
  )
}

function HoverMenu({ trigger, children, open, onOpenChange }: { trigger: ReactNode; children: ReactNode; open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <div
      className="relative"
      onMouseEnter={() => onOpenChange(true)}
      onMouseLeave={() => onOpenChange(false)}
      onFocus={() => onOpenChange(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) onOpenChange(false)
      }}
    >
      {trigger}
      <div className={cn('absolute right-0 top-full z-50 pt-2 transition duration-150 ease-out', open ? 'visible pointer-events-auto translate-y-0 opacity-100' : 'invisible pointer-events-none translate-y-1 opacity-0')}>
        {children}
      </div>
    </div>
  )
}

function EmptyAnnouncementArt() {
  return (
    <div className="relative h-32 w-40 text-[hsl(var(--pix-steel))]">
      <span className="absolute left-8 top-1 grid h-11 w-11 place-items-center rounded-full bg-[hsl(var(--pix-sky))] text-primary"><Plus className="h-7 w-7 stroke-[3]" /></span>
      <svg className="absolute bottom-0 left-4 h-28 w-32" viewBox="0 0 128 112" fill="none" aria-hidden="true">
        <path d="M42 100C30 97 21 88 21 77C21 63 35 55 47 61C51 46 65 36 81 40C96 44 105 59 101 74C110 76 115 83 113 92C110 103 96 109 83 104C72 112 55 110 42 100Z" fill="hsl(var(--card))" stroke="currentColor" strokeWidth="1.2" />
        <path d="M58 22H94V58H58V22Z" fill="hsl(var(--secondary))" stroke="currentColor" strokeWidth="1.2" />
        <path d="M64 30H84M64 38H90M64 46H78" stroke="currentColor" strokeWidth="1.2" />
        <path d="M48 44C40 53 38 69 45 79M96 54C102 62 104 74 99 84" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        <path d="M29 81C21 78 16 70 16 61C16 55 18 50 21 47C26 61 32 72 42 80C39 83 34 84 29 81Z" fill="currentColor" opacity="0.9" />
      </svg>
    </div>
  )
}

function todayKey() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

const utilityButtonClass = 'grid h-10 w-10 place-items-center rounded-full border border-border bg-[hsl(var(--secondary))] text-[hsl(var(--pix-charcoal))] shadow-[0_1px_2px_rgba(15,15,15,0.04)] transition hover:bg-card hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-foreground'
const utilityButtonActiveClass = 'border-[hsl(var(--pix-sky))] bg-card text-primary shadow-[0_4px_12px_rgba(15,15,15,0.08)]'
