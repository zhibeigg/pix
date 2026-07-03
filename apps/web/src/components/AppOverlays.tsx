import * as DialogPrimitive from '@radix-ui/react-dialog'
import { CheckCircle2, CircleAlert, Coins, Info, PackagePlus, Trash2, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useI18n } from '../i18n'
import type { AppPage } from './AppTabs'
import { AppTabs } from './AppTabs'
import { AccountMenu } from './AccountMenu'
import { Button } from './ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogOverlay, DialogPortal, DialogTitle } from './ui/dialog'
import type { AssetPack, CreditBalance, GenerationJob, User } from '../types'

/* ── Types ─────────────────────────────────────────────── */

export type ToastVariant = 'success' | 'info' | 'error'
export type AppToastState = { id: number; message: string; variant: ToastVariant }
export type PackExpandConfirmState = { price: number; currentCount: number; currentLimit: number; nextLimit: number; availableCredits: number | null }
export type GalleryExpandConfirmState = { price: number; currentCount: number; currentLimit: number; nextLimit: number; slots: number; availableCredits: number | null }
export type DeleteConfirmState = { kind: 'job'; job: GenerationJob } | { kind: 'jobs'; jobs: GenerationJob[] } | { kind: 'pack'; pack: AssetPack }

/* ── DeleteConfirmDialog ───────────────────────────────── */

export function DeleteConfirmDialog({ state, loading, onCancel, onConfirm }: { state: DeleteConfirmState | null; loading: boolean; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useI18n()
  const bulkWorkIds = state?.kind === 'jobs' ? state.jobs.map((job) => `#${job.id}`) : []
  const bulkWorkSummary = bulkWorkIds.length > 8 ? `${bulkWorkIds.slice(0, 8).join(', ')} +${bulkWorkIds.length - 8}` : bulkWorkIds.join(', ')
  const title = state?.kind === 'job'
    ? t('confirmDelete.workTitle', { id: state.job.id })
    : state?.kind === 'jobs'
      ? t('confirmDelete.worksTitle', { count: state.jobs.length })
      : state?.kind === 'pack'
        ? t('confirmDelete.packTitle')
        : ''
  const description = state?.kind === 'job'
    ? t('confirmDelete.workDescription')
    : state?.kind === 'jobs'
      ? t('confirmDelete.worksDescription', { count: state.jobs.length })
      : state?.kind === 'pack'
        ? t('confirmDelete.packDescription', { name: state.pack.name })
        : ''
  const impactItems = state?.kind === 'job'
    ? [
        t('confirmDelete.workMeta', { id: state.job.id }),
        t('confirmDelete.outputMeta'),
        t('confirmDelete.irreversible'),
      ]
    : state?.kind === 'jobs'
      ? [
          t('confirmDelete.worksMeta', { count: state.jobs.length, ids: bulkWorkSummary }),
          t('confirmDelete.outputMeta'),
          t('confirmDelete.irreversible'),
        ]
      : state?.kind === 'pack'
        ? [
            t('confirmDelete.packMeta', { name: state.pack.name }),
            t('confirmDelete.irreversible'),
          ]
        : []

  return (
    <Dialog open={Boolean(state)} onOpenChange={(open) => { if (!open && !loading) onCancel() }}>
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          className="fixed z-50 overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-card p-0 pix-shadow-dialog focus:outline-none dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]"
          style={{
            left: '50%',
            maxHeight: 'calc(100dvh - 32px)',
            maxWidth: 'none',
            top: '50%',
            transform: 'translate3d(-50%, -50%, 0)',
            width: 'min(500px, calc(100vw - 32px))',
          }}
        >
          {state && (
            <div className="relative grid gap-5 p-6">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_18%_0%,hsl(var(--destructive)/.18),transparent_36%),linear-gradient(180deg,hsl(var(--pix-cream)/.86),transparent)] dark:bg-[radial-gradient(circle_at_18%_0%,hsl(var(--destructive)/.34),transparent_34%),linear-gradient(180deg,hsl(var(--pix-navy)/.82),transparent)]" />
              <DialogHeader className="relative grid grid-cols-[auto_minmax(0,1fr)] gap-3 pr-8">
                <div className="grid h-12 w-12 place-items-center rounded-lg border border-destructive/24 bg-destructive/10 text-destructive shadow-[0_14px_34px_-22px_hsl(var(--destructive)/.72)] dark:border-[hsl(var(--destructive)/.24)] dark:bg-[hsl(var(--destructive)/.12)] dark:text-[hsl(0_74%_80%)]">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-destructive/75 dark:text-[hsl(0_74%_80%/.78)]">{t('confirmDelete.eyebrow')}</p>
                  <DialogTitle className="mt-1 text-xl leading-tight">{title}</DialogTitle>
                  <DialogDescription className="mt-2 leading-6">{description}</DialogDescription>
                </div>
              </DialogHeader>
              <div className="relative grid gap-2 rounded-lg border border-destructive/18 bg-destructive/7 p-3 text-sm dark:border-[hsl(var(--destructive)/.18)] dark:bg-[hsl(var(--destructive)/.10)]">
                {impactItems.map((item) => (
                  <div key={item} className="flex items-center gap-2 rounded-md bg-card/72 px-3 py-2 text-muted-foreground dark:bg-black/12 dark:text-white/68">
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-sm bg-destructive/10 text-[10px] font-bold text-destructive dark:bg-[hsl(var(--destructive)/.12)] dark:text-[hsl(0_74%_80%)]">×</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
              <DialogFooter className="relative">
                <Button type="button" variant="outline" disabled={loading} onClick={onCancel}>{t('confirmDelete.cancel')}</Button>
                <Button type="button" variant="destructive" disabled={loading} onClick={onConfirm}>{loading ? t('confirmDelete.deleting') : t('confirmDelete.confirm')}</Button>
              </DialogFooter>
            </div>
          )}
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring" disabled={loading}>
            <X className="h-4 w-4" />
            <span className="sr-only">{t('common.close')}</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  )
}

/* ── PackExpandConfirmDialog ───────────────────────────── */

type ExpandConfirmShared = { price: number; currentCount: number; currentLimit: number; nextLimit: number; availableCredits: number | null }

function ExpandConfirmDialog({ state, loading, tone, i18nPrefix, descriptionParams, onCancel, onConfirm }: { state: ExpandConfirmShared | null; loading: boolean; tone: 'primary' | 'green'; i18nPrefix: string; descriptionParams: Record<string, unknown>; onCancel: () => void; onConfirm: () => void }) {
  const { t } = useI18n()
  const available = state?.availableCredits ?? null
  const overlayClass = tone === 'green'
    ? 'bg-[radial-gradient(circle_at_20%_0%,hsl(var(--pix-brand-green)/.18),transparent_38%),linear-gradient(180deg,hsl(var(--pix-mint)/.62),transparent)] dark:bg-[radial-gradient(circle_at_20%_0%,hsl(var(--pix-brand-green)/.26),transparent_38%),linear-gradient(180deg,hsl(var(--pix-navy)/.72),transparent)]'
    : 'bg-[radial-gradient(circle_at_20%_0%,hsl(var(--primary)/.18),transparent_38%),linear-gradient(180deg,hsl(var(--pix-mint)/.62),transparent)] dark:bg-[radial-gradient(circle_at_20%_0%,hsl(var(--primary)/.32),transparent_38%),linear-gradient(180deg,hsl(var(--pix-navy)/.72),transparent)]'
  return (
    <Dialog open={Boolean(state)} modal={false} onOpenChange={(open) => { if (!open && !loading) onCancel() }}>
      <DialogContent className="overflow-hidden border-[hsl(var(--pix-paper-border))] bg-card p-0 pix-shadow-dialog sm:max-w-[480px] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]">
        {state && (
          <div className="relative grid gap-5 p-6">
            <div className={`pointer-events-none absolute inset-x-0 top-0 h-28 ${overlayClass}`} />
            <DialogHeader className="relative grid grid-cols-[auto_minmax(0,1fr)] gap-3 pr-8">
              <div className="grid h-12 w-12 place-items-center rounded-lg border border-primary/20 bg-primary/10 text-primary shadow-[0_12px_28px_-18px_rgba(79,70,229,0.72)] dark:border-primary/30 dark:bg-primary/18">
                <PackagePlus className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <DialogTitle className="text-xl leading-tight">{t(`${i18nPrefix}Title`)}</DialogTitle>
                <DialogDescription className="mt-2 leading-6">{t(`${i18nPrefix}Description`, descriptionParams)}</DialogDescription>
              </div>
            </DialogHeader>
            <div className="relative grid gap-2 rounded-lg border border-border bg-background/82 p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
              <div className="grid grid-cols-3 gap-2 text-center">
                <DialogMetric label={t(`${i18nPrefix}Current`)} value={`${state.currentCount}/${state.currentLimit}`} />
                <DialogMetric label={t(`${i18nPrefix}After`)} value={`${state.currentCount}/${state.nextLimit}`} tone="primary" />
                <DialogMetric label={t(`${i18nPrefix}Cost`)} value={t('common.points', { count: state.price })} />
              </div>
              {available !== null && (
                <div className="mt-1 flex items-center gap-2 rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground dark:bg-white/6 dark:text-white/58">
                  <Coins className="h-4 w-4 text-primary" />
                  <span>{t(`${i18nPrefix}Balance`, { count: available })}</span>
                </div>
              )}
            </div>
            <DialogFooter className="relative">
              <Button type="button" variant="outline" disabled={loading} onClick={onCancel}>{t('common.cancel')}</Button>
              <Button type="button" disabled={loading} onClick={onConfirm}>{loading ? t(`${i18nPrefix}Working`) : t(`${i18nPrefix}Confirm`)}</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function PackExpandConfirmDialog({ state, loading, onCancel, onConfirm }: { state: PackExpandConfirmState | null; loading: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <ExpandConfirmDialog state={state} loading={loading} tone="primary" i18nPrefix="packs.expandDialog" descriptionParams={{ price: state?.price ?? 0 }} onCancel={onCancel} onConfirm={onConfirm} />
}

export function GalleryExpandConfirmDialog({ state, loading, onCancel, onConfirm }: { state: GalleryExpandConfirmState | null; loading: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <ExpandConfirmDialog state={state} loading={loading} tone="green" i18nPrefix="gallery.expandDialog" descriptionParams={{ price: state?.price ?? 0, slots: state?.slots ?? 0 }} onCancel={onCancel} onConfirm={onConfirm} />
}

function DialogMetric({ label, value, tone = 'default' }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'primary' }) {
  const labelClass = tone === 'primary' ? 'text-primary/72 dark:text-primary/82' : 'text-muted-foreground dark:text-white/52'
  return (
    <div className={`rounded-md border px-2.5 py-2 ${tone === 'primary' ? 'border-primary/25 bg-primary/10 text-primary dark:bg-primary/18' : 'border-border bg-card dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]'}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[.08em] ${labelClass}`}>{label}</p>
      <p className="mt-1 text-sm font-bold leading-tight">{value}</p>
    </div>
  )
}

/* ── AppToast ──────────────────────────────────────────── */

export function AppToast({ toast, onDismiss }: { toast: AppToastState | null; onDismiss: () => void }) {
  const { t } = useI18n()
  if (!toast) return null
  const Icon = toast.variant === 'error' ? CircleAlert : toast.variant === 'info' ? Info : CheckCircle2
  const tone = toast.variant === 'error'
    ? 'border-destructive/35 bg-destructive text-destructive-foreground dark:border-[hsl(var(--destructive))]/35 dark:bg-[hsl(0_55%_16%)] dark:text-[hsl(0_90%_92%)]'
    : toast.variant === 'info'
      ? 'border-[hsl(var(--tone-info-line))]/30 bg-[hsl(var(--tone-info-surface))] text-[hsl(var(--pix-navy))] dark:border-[hsl(var(--tone-info-line))]/30 dark:bg-[hsl(var(--pix-navy-deep))] dark:text-[hsl(var(--pix-sky))]'
      : 'border-[hsl(var(--tone-success-line))]/30 bg-[hsl(var(--tone-success-surface))] text-[hsl(var(--pix-navy))] dark:border-[hsl(var(--tone-success-line))]/30 dark:bg-[hsl(var(--pix-navy-deep))] dark:text-[hsl(var(--pix-mint))]'
  const iconTone = toast.variant === 'error' ? 'text-[hsl(0_90%_92%)] dark:text-[hsl(0_88%_86%)]' : toast.variant === 'info' ? 'text-[hsl(var(--pix-link-blue))] dark:text-[hsl(208_80%_82%)]' : 'text-[hsl(var(--pix-brand-green))] dark:text-[hsl(150_60%_80%)]'

  return (
    <div className="pointer-events-none fixed left-1/2 top-3 z-[100] w-[min(calc(100vw-24px),360px)] -translate-x-1/2 px-0 md:top-4">
      <div key={toast.id} role="status" aria-live="polite" className={`motion-success-pop pointer-events-auto relative flex items-center gap-2.5 rounded-md border px-3 py-2 pr-10 text-sm font-medium pix-shadow-toast ring-1 ring-black/5 ${tone}`}>
        <Icon className={`h-4 w-4 shrink-0 ${iconTone}`} />
        <p className="min-w-0 flex-1 leading-5">{toast.message}</p>
        <button type="button" onClick={onDismiss} aria-label={t('app.toastDismiss')} className="absolute right-1.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md opacity-72 transition hover:bg-black/5 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/10">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

/* ── WorkspaceShell ────────────────────────────────────── */

export function WorkspaceShell({ page, user, balance, activeJobs, completedJobs, failedJobs, isAdmin, children, onNavigate }: { page: AppPage; user: User; balance: CreditBalance | null; activeJobs: number; completedJobs: number; failedJobs: number; isAdmin: boolean; children: ReactNode; onNavigate: (page: AppPage) => void }) {
  const { t } = useI18n()
  return (
    <div className="grid min-h-[calc(100vh-65px)] bg-[hsl(var(--pix-cream)/.42)] lg:grid-cols-[260px_minmax(0,1fr)] dark:bg-[hsl(var(--pix-navy-deep))]">
      <aside className="border-b border-border bg-[hsl(var(--pix-paper-soft))] p-4 text-[hsl(var(--pix-ink))] lg:border-b-0 lg:border-r dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band))] dark:text-white">
        <div className="grid gap-6 lg:sticky lg:top-20 lg:min-h-[calc(100vh-97px)] lg:grid-rows-[auto_auto_1fr_auto]">
          <div>
            <p className="text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-[hsl(var(--pix-steel))] dark:text-white/58">{t('sidebar.workspace')}</p>
            <div className="mt-3 rounded-md border border-border bg-card p-3 pix-shadow-hairline dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]">
              <p className="truncate text-sm font-semibold">{user.display_name || user.email}</p>
              <p className="mt-1 truncate text-xs text-muted-foreground dark:text-white/45">{user.email}</p>
            </div>
          </div>
          <AppTabs page={page} user={user} onChange={onNavigate} orientation="side" />
          <div className="hidden lg:block" />
          <div className="grid grid-cols-3 gap-2 lg:grid-cols-1">
            <SidebarMetric label={t('sidebar.credits')} value={balance?.available_total ?? balance?.available_credits ?? '—'} />
            <SidebarMetric label={t('sidebar.queue')} value={activeJobs} />
            <SidebarMetric label={t('sidebar.done')} value={completedJobs} />
            {failedJobs > 0 && <SidebarMetric label={t('sidebar.failed')} value={failedJobs} tone="danger" />}
            {isAdmin && <SidebarMetric label={t('sidebar.role')} value={t('sidebar.admin')} />}
          </div>
        </div>
      </aside>
      <section className="min-w-0 bg-[linear-gradient(180deg,hsl(var(--pix-paper))_0%,hsl(var(--background))_36rem)] px-4 py-5 md:px-8 md:py-8 dark:bg-[linear-gradient(180deg,hsl(var(--pix-navy))_0%,hsl(var(--pix-navy-deep))_42rem)]">
        <div key={page} className="motion-page-enter grid w-full gap-6">
          <div className="block lg:hidden">
            <AppTabs page={page} user={user} onChange={onNavigate} />
          </div>
          {children}
        </div>
      </section>
    </div>
  )
}

function SidebarMetric({ label, value, tone = 'default' }: { label: ReactNode; value: ReactNode; tone?: 'default' | 'danger' }) {
  return (
    <div className={`rounded-md border px-3 py-2 pix-shadow-hairline ${tone === 'danger' ? 'border-[hsl(var(--destructive)/.28)] bg-[hsl(var(--destructive)/.08)] text-[hsl(var(--destructive))] dark:border-[hsl(var(--destructive)/.30)] dark:bg-[hsl(var(--destructive)/.10)] dark:text-white' : 'border-border bg-card text-[hsl(var(--pix-ink))] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white'}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground dark:text-white/52">{label}</p>
      <p className="mt-1 text-lg font-semibold leading-tight">{value}</p>
    </div>
  )
}

/* ── SiteFooter ─────────────────────────────────────────── */

export function SiteFooter() {
  const { t } = useI18n()
  const groups = [
    { title: t('footer.product'), links: [
      { label: t('footer.productionWorkspace'), href: '#/workspace' },
      { label: t('footer.gallery'), href: '#/gallery' },
      { label: t('footer.packs'), href: '#/packs' },
    ]},
    { title: t('footer.resources'), links: [
      { label: t('footer.pixelUi'), href: '#/workspace' },
      { label: t('footer.spriteFrames'), href: '#/workspace' },
      { label: t('footer.sampleAtlas'), href: '#/home' },
    ]},
    { title: t('footer.workspace'), links: [
      { label: t('footer.billingCenter'), href: '#/billing' },
      { label: t('footer.jobQueue'), href: '#/workspace' },
      { label: t('footer.batchExport'), href: '#/workspace' },
    ]},
    { title: t('footer.company'), links: [
      { label: t('footer.pixForge'), href: '#/home' },
      { label: t('footer.gameAssets'), href: '#/home' },
    ]},
  ]
  return (
    <footer className="border-t border-border bg-card px-4 py-16 md:px-8 dark:border-white/10 dark:bg-[hsl(var(--pix-navy-deep))]">
      <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-[1.2fr_2fr]">
        <div>
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <img src="/pix-logo-64.png" alt="" className="h-7 w-7 opacity-80 [image-rendering:pixelated]" />
            {t('footer.brand')}
          </div>
          <p className="mt-4 max-w-sm text-sm leading-6 text-muted-foreground">{t('footer.description')}</p>
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer" className="mt-4 inline-flex text-xs text-muted-foreground hover:text-foreground">鲁ICP备2022023963号-1</a>
        </div>
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {groups.map((group) => (
            <div key={group.title}>
              <p className="text-sm font-semibold text-foreground">{group.title}</p>
              <div className="mt-3 grid gap-2">
                {group.links.map((link) => <a key={link.label} href={link.href} className="text-sm text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 rounded-sm">{link.label}</a>)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </footer>
  )
}

/* ── showSystemNotification ─────────────────────────────── */

export function showSystemNotification(title: string, body: string) {
  if (typeof window === 'undefined' || !('Notification' in window)) return
  const options: NotificationOptions = { body, icon: '/pix-logo-64.png', tag: 'pix-generation-complete' }
  if (Notification.permission === 'granted') {
    new Notification(title, options)
    return
  }
  if (Notification.permission === 'default') {
    void Notification.requestPermission().then((permission) => {
      if (permission === 'granted') new Notification(title, options)
    }).catch(() => undefined)
  }
}
