import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { Bell, Check, Languages, Megaphone, Monitor, Moon, Plus, Sun } from 'lucide-react'
import { api } from '../api'
import type { PixLanguage, PixThemeMode, PixThemePreference } from '../theme'
import type { AnnouncementItem } from '../types'
import { useI18n } from '../i18n'
import { cn } from '../lib/utils'
import { setPreviewLanguage, setPreviewTheme } from '../lib/uiPreview'
import { Button } from './ui/button'
import { Dialog, DialogClose, DialogDescription, DialogFooter, DialogHeader, DialogOverlay, DialogPortal, DialogTitle, DialogTrigger } from './ui/dialog'

const ANNOUNCEMENT_MUTE_KEY = 'pix_announcement_muted_date'
const ANNOUNCEMENT_SEEN_KEY = 'pix_announcement_seen_ids'

function announcementTimestamp(item: AnnouncementItem) {
  const raw = item.published_at || item.created_at || item.updated_at
  const value = raw ? new Date(raw).getTime() : 0
  return Number.isFinite(value) ? value : 0
}

const languageOptions: Array<{ value: PixLanguage; labelKey: string; flag: string }> = [
  { value: 'zh-CN', labelKey: 'utility.language.chinese', flag: '🇨🇳' },
  { value: 'en', labelKey: 'utility.language.english', flag: '🇬🇧' },
]

const themeOptions: Array<{ value: PixThemePreference; titleKey: string; descriptionKey: string; icon: ComponentType<{ className?: string }> }> = [
  { value: 'light', titleKey: 'utility.theme.lightTitle', descriptionKey: 'utility.theme.lightDescription', icon: Sun },
  { value: 'dark', titleKey: 'utility.theme.darkTitle', descriptionKey: 'utility.theme.darkDescription', icon: Moon },
  { value: 'system', titleKey: 'utility.theme.systemTitle', descriptionKey: 'utility.theme.systemDescription', icon: Monitor },
]

interface HeaderUtilityBarProps {
  language: PixLanguage
  themePreference: PixThemePreference
  resolvedMode: PixThemeMode
  systemMode: PixThemeMode
  autoOpenAnnouncement?: boolean
  onLanguageChange: (language: PixLanguage) => void
  onThemePreferenceChange: (preference: PixThemePreference) => void
}

type UtilityMenu = 'theme' | 'language'

export function HeaderUtilityBar({ language, themePreference, resolvedMode, systemMode, autoOpenAnnouncement = false, onLanguageChange, onThemePreferenceChange }: HeaderUtilityBarProps) {
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
      <AnnouncementButton open={announcementOpen} autoOpen={autoOpenAnnouncement} onOpenChange={changeAnnouncementOpen} />
      <ThemeHoverMenu open={activeMenu === 'theme'} onOpenChange={(open) => setMenuOpen('theme', open)} preference={themePreference} resolvedMode={resolvedMode} systemMode={systemMode} onChange={onThemePreferenceChange} />
      <LanguageHoverMenu open={activeMenu === 'language'} onOpenChange={(open) => setMenuOpen('language', open)} language={language} onChange={onLanguageChange} />
    </div>
  )
}

function AnnouncementButton({ open, autoOpen, onOpenChange }: { open: boolean; autoOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useI18n()
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([])
  const [loading, setLoading] = useState(false)

  async function loadAnnouncements() {
    setLoading(true)
    try {
      const res = await api.announcements()
      setAnnouncements(res.items)
    } catch {
      setAnnouncements([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAnnouncements()
  }, [])

  useEffect(() => {
    if (open) void loadAnnouncements()
  }, [open])

  const sortedAnnouncements = useMemo(
    () => [...announcements].sort((a, b) => announcementTimestamp(b) - announcementTimestamp(a) || b.id - a.id),
    [announcements],
  )
  const hasAnnouncement = sortedAnnouncements.length > 0
  const seenIds = getSeenIds()

  function markAllSeen() {
    const ids = sortedAnnouncements.map((a) => a.id)
    localStorage.setItem(ANNOUNCEMENT_SEEN_KEY, JSON.stringify(ids))
  }

  function changeOpen(nextOpen: boolean) {
    if (!nextOpen) markAllSeen()
    onOpenChange(nextOpen)
  }

  const hasUnseen = sortedAnnouncements.some((a) => !seenIds.includes(a.id))

  useEffect(() => {
    if (!autoOpen || open || !hasAnnouncement || !hasUnseen) return
    const muteValue = announcementMuteValue(JSON.stringify(sortedAnnouncements.map((a) => a.id)))
    if (localStorage.getItem(ANNOUNCEMENT_MUTE_KEY) === muteValue) return
    markAllSeen()
    onOpenChange(true)
  }, [autoOpen, hasAnnouncement, hasUnseen, onOpenChange, open, sortedAnnouncements])

  function muteToday() {
    const ids = sortedAnnouncements.map((a) => a.id)
    localStorage.setItem(ANNOUNCEMENT_MUTE_KEY, announcementMuteValue(JSON.stringify(ids)))
    markAllSeen()
    onOpenChange(false)
  }

  function relativePublishedLabel(value: string) {
    const time = new Date(value).getTime()
    if (!Number.isFinite(time)) return ''
    const diffMs = Math.max(0, Date.now() - time)
    const minutes = Math.floor(diffMs / 60_000)
    if (minutes < 1) return t('utility.announcements.publishedRelative', { time: t('utility.announcements.justNow') })
    if (minutes < 60) return t('utility.announcements.publishedRelative', { time: t('utility.announcements.minutesAgo', { count: minutes }) })
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return t('utility.announcements.publishedRelative', { time: t('utility.announcements.hoursAgo', { count: hours }) })
    const days = Math.floor(hours / 24)
    return t('utility.announcements.publishedRelative', { time: t('utility.announcements.daysAgo', { count: days }) })
  }

  function publishedTimeLabel(value: string) {
    const time = new Date(value).getTime()
    const absolute = Number.isFinite(time) ? new Date(time).toLocaleString() : value
    const relative = relativePublishedLabel(value)
    return relative
      ? `${t('utility.announcements.publishedAt', { time: absolute })} · ${relative}`
      : t('utility.announcements.publishedAt', { time: absolute })
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen} modal={false}>
      <DialogTrigger asChild>
        <button type="button" className={cn(utilityButtonClass, hasUnseen && 'border-primary/30 bg-card text-primary pix-shadow-raised')} aria-label={t('utility.announcements.open')}>
          <span className="relative grid place-items-center">
            <Bell className="h-4 w-4" />
            {hasUnseen && <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-primary ring-2 ring-card" />}
          </span>
        </button>
      </DialogTrigger>
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          onCloseAutoFocus={(event) => event.preventDefault()}
          className="announcement-dialog-content fixed z-50 grid min-h-[456px] content-start gap-0 overflow-hidden rounded-lg border border-border bg-card p-0 pix-shadow-overlay focus:outline-none dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]"
          style={{
            left: '50%',
            maxHeight: 'calc(100dvh - 32px)',
            maxWidth: 'none',
            position: 'fixed',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 'min(920px, calc(100vw - 32px))',
          }}
        >
          <div className="flex items-start justify-between gap-6 px-6 pb-4 pt-8 md:px-7">
          <DialogHeader className="gap-0">
            <DialogTitle className="text-2xl font-semibold tracking-[-0.02em]">{t('utility.announcements.title')}</DialogTitle>
            <DialogDescription className="sr-only">{t('utility.announcements.description')}</DialogDescription>
          </DialogHeader>
          <div className="mr-8 flex items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-[hsl(var(--pix-sky))] px-3 py-2 font-semibold text-[hsl(var(--pix-link-blue))]">
              <Bell className="h-4 w-4" />{t('utility.announcements.notifications')}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[hsl(var(--pix-steel))]">
              <Megaphone className="h-4 w-4" />{t('utility.announcements.system')}
            </span>
          </div>
        </div>

          <div className="min-h-[300px] px-6 py-4">
          {hasAnnouncement ? (
            <div className="w-full space-y-0">
              {sortedAnnouncements.map((announcement) => (
                <article key={announcement.id} className="motion-panel-enter relative flex gap-4 border-l-2 border-[hsl(var(--pix-paper-border))] pl-5 dark:border-white/10">
                  <span className="absolute left-[-5px] top-1 h-2 w-2 rounded-full bg-[hsl(var(--pix-link-blue))]" />
                  <div className="min-w-0 pb-6">
                    <h3 className="text-base font-semibold tracking-[-0.01em]">{announcement.title || t('utility.announcements.system')}</h3>
                    {announcement.body && <p className="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-[hsl(var(--pix-slate))] dark:text-white/68">{announcement.body}</p>}
                    {announcement.published_at && <p className="mt-2 text-xs text-muted-foreground">{publishedTimeLabel(announcement.published_at)}</p>}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="grid min-h-[300px] justify-items-center gap-4 text-center">
              <EmptyAnnouncementArt />
              <p className="text-sm text-[hsl(var(--pix-slate))]">{loading ? t('utility.announcements.loading') : t('utility.announcements.empty')}</p>
            </div>
          )}
        </div>

          <DialogFooter className="px-6 pb-6 md:px-7">
          <Button type="button" variant="soft" onClick={muteToday}>{t('utility.announcements.muteToday')}</Button>
          <DialogClose asChild><Button type="button">{t('utility.announcements.close')}</Button></DialogClose>
        </DialogFooter>
        <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring">
          <span aria-hidden="true">×</span>
          <span className="sr-only">{t('utility.announcements.close')}</span>
        </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  )
}

function ThemeHoverMenu({ open, preference, resolvedMode, systemMode, onChange, onOpenChange }: { open: boolean; preference: PixThemePreference; resolvedMode: PixThemeMode; systemMode: PixThemeMode; onChange: (preference: PixThemePreference) => void; onOpenChange: (open: boolean) => void }) {
  const { t } = useI18n()
  useEffect(() => { if (!open) setPreviewTheme(null) }, [open])
  const TriggerIcon = preference === 'system' ? Monitor : resolvedMode === 'dark' ? Moon : Sun
  return (
    <HoverMenu
      open={open}
      onOpenChange={onOpenChange}
      trigger={(
        <button type="button" className={cn(utilityButtonClass, open && utilityButtonActiveClass)} aria-label={t('utility.theme.switchLabel')} aria-expanded={open}>
          <TriggerIcon className="h-4 w-4" />
        </button>
      )}
    >
      <div role="radiogroup" aria-label={t('utility.theme.groupLabel')} onMouseLeave={() => setPreviewTheme(null)} className="w-48 rounded-lg border border-border bg-popover p-1.5 text-popover-foreground pix-shadow-overlay">
        {themeOptions.map((option) => {
          const Icon = option.icon
          const active = preference === option.value
          return (
            <button
              key={option.value}
              type="button"
              onMouseEnter={() => setPreviewTheme(option.value === 'system' ? systemMode : option.value)}
              onClick={() => { setPreviewTheme(null); onChange(option.value); onOpenChange(false) }}
              role="radio"
              aria-checked={active}
              className={cn('flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left text-popover-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/7', active && 'bg-[hsl(var(--primary)/.12)] text-[hsl(var(--primary))] ring-1 ring-[hsl(var(--primary)/.3)] dark:bg-[hsl(var(--primary)/.18)] dark:text-foreground dark:ring-[hsl(var(--primary)/.4)]')}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-sm font-semibold leading-tight">{t(option.titleKey)}{active && <Check className="h-3.5 w-3.5 text-primary" />}</span>
                <span className={cn('mt-1 block text-xs leading-4 text-muted-foreground', active && 'dark:text-white/55')}>{t(option.descriptionKey)}</span>
              </span>
            </button>
          )
        })}
        <div className="px-3 pb-1 pt-2 text-[11px] text-muted-foreground">{t('utility.theme.systemNow')}{systemMode === 'dark' ? t('utility.theme.currentDark') : t('utility.theme.currentLight')}</div>
      </div>
    </HoverMenu>
  )
}

function LanguageHoverMenu({ open, language, onChange, onOpenChange }: { open: boolean; language: PixLanguage; onChange: (language: PixLanguage) => void; onOpenChange: (open: boolean) => void }) {
  const { t } = useI18n()
  useEffect(() => { if (!open) setPreviewLanguage(null) }, [open])
  return (
    <HoverMenu
      open={open}
      onOpenChange={onOpenChange}
      trigger={(
        <button type="button" className={cn(utilityButtonClass, open && utilityButtonActiveClass)} aria-label={t('utility.language.switchLabel')} aria-expanded={open}>
          <Languages className="h-4 w-4" />
        </button>
      )}
    >
      <div role="radiogroup" aria-label={t('utility.language.groupLabel')} onMouseLeave={() => setPreviewLanguage(null)} className="w-36 rounded-lg border border-border bg-popover p-1.5 text-popover-foreground pix-shadow-overlay">
        {languageOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            onMouseEnter={() => setPreviewLanguage(option.value)}
            onClick={() => { setPreviewLanguage(null); onChange(option.value); onOpenChange(false) }}
            role="radio"
            aria-checked={language === option.value}
            className={cn('flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm text-popover-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/7', language === option.value && 'bg-[hsl(var(--primary)/.12)] text-[hsl(var(--primary))] ring-1 ring-[hsl(var(--primary)/.3)] dark:bg-[hsl(var(--primary)/.18)] dark:text-foreground dark:ring-[hsl(var(--primary)/.4)]')}
          >
            <span className="flex min-w-0 items-center gap-2 whitespace-nowrap"><span className="shrink-0 text-base leading-none">{option.flag}</span><span className="truncate">{t(option.labelKey)}</span></span>
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

function getSeenIds(): number[] {
  try {
    const raw = localStorage.getItem(ANNOUNCEMENT_SEEN_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.filter((id): id is number => typeof id === 'number')
    return []
  } catch {
    return []
  }
}

function announcementMuteValue(idsJson: string) {
  return `${todayKey()}:${idsJson}`
}

function todayKey() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

const utilityButtonClass = 'grid h-11 w-11 place-items-center rounded-full border border-border bg-[hsl(var(--secondary))] text-[hsl(var(--pix-charcoal))] pix-shadow-hairline transition hover:bg-card hover:pix-shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-foreground'
const utilityButtonActiveClass = 'border-[hsl(var(--pix-sky))] bg-card text-primary pix-shadow-raised'
