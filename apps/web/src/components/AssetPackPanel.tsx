import { Archive, Check, Download, Folder, FolderOpen, MoreHorizontal, Pencil, Plus, RefreshCw, Sparkles, Trash2, X } from 'lucide-react'
import { useMemo, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useI18n } from '../i18n'
import type { AssetPack, AssetPackQuota } from '../types'
import { cn, formatDateTime } from '../lib/utils'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu'
import { Input } from './ui/input'
import { PixPanel } from './pix/PixPanel'

export type AssetPackPanelProps = {
  packs: AssetPack[]
  quota: AssetPackQuota | null
  selectedPackId: number | null
  downloading: boolean
  onSelectPack: (pack: AssetPack) => void
  onClearSelection: () => void
  onCreatePack: (name: string) => Promise<void>
  onRenamePack: (pack: AssetPack, name: string) => Promise<void>
  onToggleArchive: (pack: AssetPack) => void
  onDeletePack: (pack: AssetPack) => void
  onExpandPackLimit: () => void
  onDownloadPack: (pack: AssetPack) => void
  onRefresh: () => void
}

export function AssetPackPanel({ packs, quota, selectedPackId, downloading, onSelectPack, onClearSelection, onCreatePack, onRenamePack, onToggleArchive, onDeletePack, onExpandPackLimit, onDownloadPack, onRefresh }: AssetPackPanelProps) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [editingPackId, setEditingPackId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [renamingPackId, setRenamingPackId] = useState<number | null>(null)
  const remainingPacks = quota?.remaining_packs ?? 0
  const packLimit = quota?.pack_limit ?? packs.length
  const packCapacity = quota?.pack_capacity ?? 100
  const expandPrice = quota?.expand_price_credits ?? 99
  const selectedPack = useMemo(() => packs.find((pack) => pack.id === selectedPackId) ?? null, [packs, selectedPackId])
  const selectedPercent = selectedPack ? getPackPercent(selectedPack) : 0
  const canCreate = remainingPacks > 0

  async function submitCreate() {
    const trimmed = name.trim()
    if (!trimmed || !canCreate) return
    setCreating(true)
    try {
      await onCreatePack(trimmed)
      setName('')
    } finally {
      setCreating(false)
    }
  }

  function startRename(pack: AssetPack) {
    setEditingPackId(pack.id)
    setEditName(pack.name)
    onSelectPack(pack)
  }

  async function submitRename(pack: AssetPack) {
    const trimmed = editName.trim()
    if (!trimmed) return
    if (trimmed === pack.name) {
      setEditingPackId(null)
      return
    }
    setRenamingPackId(pack.id)
    try {
      await onRenamePack(pack, trimmed)
      setEditingPackId(null)
    } finally {
      setRenamingPackId(null)
    }
  }

  function cancelRename() {
    setEditingPackId(null)
    setEditName('')
  }

  function selectFromKeyboard(event: KeyboardEvent<HTMLDivElement>, pack: AssetPack) {
    if (event.currentTarget !== event.target) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelectPack(pack)
    }
  }

  return (
    <PixPanel
      eyebrow={t('packs.eyebrow')}
      title={t('packs.title')}
      action={(
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={remainingPacks > 0 ? 'success' : 'warning'}>{t('packs.packQuota', { used: packs.length, limit: packLimit })}</Badge>
          <Button variant="outline" size="sm" onClick={onRefresh} className="rounded-full"><RefreshCw />{t('common.refresh')}</Button>
        </div>
      )}
    >
      <div className="grid gap-4">
        <section className="overflow-hidden rounded-2xl border border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper-soft)/.58)] shadow-[0_16px_36px_-30px_rgba(35,31,20,0.5)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft)/.54)] dark:shadow-[0_24px_60px_-42px_rgba(0,0,0,0.95)]">
          <div className="grid gap-3 p-3">
            <div className={cn('rounded-2xl border p-3 transition-colors', selectedPack ? 'border-primary/35 bg-card shadow-[0_1px_0_hsl(var(--background)/.8)] dark:bg-white/[.045]' : 'border-dashed border-[hsl(var(--pix-paper-border))] bg-card/70 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-white/[.035]')}>
              {selectedPack ? (
                <div className="grid gap-3">
                  <div className="flex items-start gap-3">
                    <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-primary/25 bg-primary/10 text-primary shadow-inner">
                      <FolderOpen className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground">{t('packs.selectedPack')}</p>
                      <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
                        <h3 className="truncate text-base font-semibold leading-tight text-foreground">{selectedPack.name}</h3>
                        <Badge variant={selectedPack.status === 'archived' ? 'secondary' : 'success'}>{selectedPack.status === 'archived' ? t('packs.archived') : t('packs.active')}</Badge>
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-foreground">#{selectedPack.id} · {t('packs.updatedAt', { time: formatDateTime(selectedPack.updated_at) })}</p>
                    </div>
                    <Button type="button" variant="ghost" size="sm" onClick={() => { cancelRename(); onClearSelection() }} className="h-8 shrink-0 rounded-full px-2.5 text-xs text-muted-foreground hover:text-foreground"><X />{t('packs.clearSelection')}</Button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <ProgressBar percent={selectedPercent} />
                    <Badge variant={selectedPack.remaining_capacity > 0 ? 'success' : 'warning'}>{t('packs.capacity', { used: selectedPack.item_count, capacity: selectedPack.capacity })}</Badge>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper)/.68)] text-muted-foreground dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-white/[.04]">
                    <Folder className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">{t('packs.noSelectedPack')}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{t('packs.noSelectedHint')}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-2 xs:grid-cols-2" aria-label={t('packs.commandBar')}>
              <CommandButton disabled={!selectedPack} onClick={() => selectedPack && startRename(selectedPack)}><Pencil />{t('packs.rename')}</CommandButton>
              <CommandButton disabled={!selectedPack || selectedPack.item_count === 0 || downloading} onClick={() => selectedPack && onDownloadPack(selectedPack)}><Download />{t('packs.downloadZip')}</CommandButton>
              <CommandButton disabled={!selectedPack} onClick={() => selectedPack && onToggleArchive(selectedPack)}><Archive />{selectedPack?.status === 'archived' ? t('packs.restore') : t('packs.archive')}</CommandButton>
              <CommandButton tone="danger" disabled={!selectedPack || selectedPack.item_count > 0} onClick={() => selectedPack && onDeletePack(selectedPack)}><Trash2 />{t('packs.deleteEmpty')}</CommandButton>
              <CommandButton className="xs:col-span-2 border-[hsl(var(--pix-brand-yellow)/.55)] bg-[hsl(var(--pix-yellow)/.55)] text-[hsl(var(--pix-brand-brown))] hover:border-[hsl(var(--pix-brand-yellow))] hover:bg-[hsl(var(--pix-yellow))] dark:border-[hsl(var(--pix-brand-yellow)/.24)] dark:bg-[hsl(var(--pix-brand-yellow)/.12)] dark:text-[hsl(var(--pix-brand-yellow))] dark:hover:bg-[hsl(var(--pix-brand-yellow)/.18)]" onClick={onExpandPackLimit}><Sparkles />{t('packs.expandPackLimit', { price: expandPrice })}</CommandButton>
            </div>
          </div>
        </section>

        <form className="rounded-2xl border border-[hsl(var(--pix-paper-border))] bg-card p-3 shadow-[0_12px_30px_-28px_rgba(35,31,20,0.46)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised)/.48)]" onSubmit={(event) => { event.preventDefault(); void submitCreate() }}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground" htmlFor="new-pack-name">{t('packs.quickCreate')}</label>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{t('packs.createHint')}</p>
            </div>
            <Badge variant="outline">{t('packs.packCapacity', { capacity: packCapacity })}</Badge>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Input id="new-pack-name" value={name} maxLength={160} disabled={!canCreate} onChange={(event) => setName(event.target.value)} placeholder={t('packs.newPlaceholder')} className="h-11 rounded-xl border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper)/.46)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-white/[.04]" />
            <Button type="submit" disabled={creating || !name.trim() || !canCreate} className="h-11 rounded-xl px-4"><Plus />{t('packs.create')}</Button>
          </div>
          <p className={cn('mt-2 text-xs', canCreate ? 'text-muted-foreground' : 'font-medium text-[hsl(var(--pix-brand-orange-deep))] dark:text-[hsl(var(--pix-brand-yellow))]')}>{canCreate ? t('packs.remainingPackSlots', { count: remainingPacks }) : t('packs.packLimitReached')}</p>
        </form>

        <section className="grid gap-2">
          <div className="flex items-end justify-between gap-3 px-1">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground">{t('packs.folderList')}</p>
              <p className="mt-1 text-xs text-muted-foreground">{t('packs.listCount', { count: packs.length })}</p>
            </div>
            <span className="min-w-0 truncate text-right text-xs text-muted-foreground">{selectedPack ? t('packs.selectedSummary', { name: selectedPack.name }) : t('packs.noSelectionSummary')}</span>
          </div>
          {packs.length === 0 ? <Alert variant="info">{t('packs.empty')}</Alert> : (
            <div className="grid gap-2">
              {packs.map((pack) => <AssetPackRow key={pack.id} pack={pack} selected={selectedPackId === pack.id} editing={editingPackId === pack.id} editName={editName} renaming={renamingPackId === pack.id} downloading={downloading} onEditNameChange={setEditName} onSelectPack={onSelectPack} onStartRename={startRename} onSubmitRename={submitRename} onCancelRename={cancelRename} onToggleArchive={onToggleArchive} onDeletePack={onDeletePack} onDownloadPack={onDownloadPack} onKeySelect={selectFromKeyboard} />)}
            </div>
          )}
        </section>
      </div>
    </PixPanel>
  )
}

function CommandButton({ children, disabled, onClick, className, tone = 'default' }: { children: ReactNode; disabled?: boolean; onClick: () => void; className?: string; tone?: 'default' | 'danger' }) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'h-auto min-h-11 justify-start rounded-xl border border-[hsl(var(--pix-paper-border))] bg-card/82 px-3 py-2 text-left text-[13px] font-semibold shadow-[0_1px_0_hsl(var(--background)/.72)] hover:border-primary/35 hover:bg-primary/10 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-white/[.04] dark:hover:bg-white/[.08] disabled:border-[hsl(var(--pix-paper-border))] disabled:bg-muted/35 disabled:text-muted-foreground disabled:opacity-70 dark:disabled:border-[hsl(var(--pix-dark-hairline))] dark:disabled:bg-white/[.03]',
        tone === 'danger' && 'hover:border-destructive/30 hover:bg-destructive/10 hover:text-destructive',
        className,
      )}
    >
      {children}
    </Button>
  )
}

function AssetPackRow({ pack, selected, editing, editName, renaming, downloading, onEditNameChange, onSelectPack, onStartRename, onSubmitRename, onCancelRename, onToggleArchive, onDeletePack, onDownloadPack, onKeySelect }: { pack: AssetPack; selected: boolean; editing: boolean; editName: string; renaming: boolean; downloading: boolean; onEditNameChange: (name: string) => void; onSelectPack: (pack: AssetPack) => void; onStartRename: (pack: AssetPack) => void; onSubmitRename: (pack: AssetPack) => Promise<void>; onCancelRename: () => void; onToggleArchive: (pack: AssetPack) => void; onDeletePack: (pack: AssetPack) => void; onDownloadPack: (pack: AssetPack) => void; onKeySelect: (event: KeyboardEvent<HTMLDivElement>, pack: AssetPack) => void }) {
  const { t } = useI18n()
  const archived = pack.status === 'archived'
  const percent = getPackPercent(pack)
  const FolderIcon = selected ? FolderOpen : Folder
  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={() => onSelectPack(pack)}
      onKeyDown={(event) => onKeySelect(event, pack)}
      className={cn(
        'group cursor-default rounded-2xl border p-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        selected ? 'border-primary/50 bg-primary/10 shadow-[0_12px_34px_-28px_hsl(var(--primary))] dark:bg-primary/15' : 'border-[hsl(var(--pix-paper-border))] bg-card hover:border-primary/25 hover:bg-[hsl(var(--pix-paper)/.42)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-white/[.035] dark:hover:bg-white/[.07]',
        archived && 'opacity-75',
      )}
    >
      {editing ? (
        <div className="flex items-center gap-3" onClick={(event) => event.stopPropagation()}>
          <PackIcon selected={selected} archived={archived}><FolderIcon className="h-5 w-5" /></PackIcon>
          <form className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)_auto_auto] gap-2" onSubmit={(event) => { event.preventDefault(); void onSubmitRename(pack) }}>
            <Input autoFocus value={editName} maxLength={160} disabled={renaming} onChange={(event) => onEditNameChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') onCancelRename() }} aria-label={t('packs.renameEditing', { name: pack.name })} className="h-9 rounded-xl" />
            <Button type="submit" size="sm" variant="default" disabled={renaming || !editName.trim()} aria-label={t('packs.saveRename')} className="h-9 rounded-xl px-2.5"><Check /></Button>
            <Button type="button" size="sm" variant="ghost" disabled={renaming} onClick={onCancelRename} aria-label={t('packs.cancelRename')} className="h-9 rounded-xl px-2.5"><X /></Button>
          </form>
        </div>
      ) : (
        <>
          <div className="flex items-start gap-3">
            <PackIcon selected={selected} archived={archived}><FolderIcon className="h-5 w-5" /></PackIcon>
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <p className="min-w-0 truncate text-sm font-semibold leading-5 text-foreground">{pack.name}</p>
                <span className="shrink-0 text-[11px] font-medium text-muted-foreground">#{pack.id}</span>
                {archived && <Badge variant="secondary">{t('packs.archived')}</Badge>}
              </div>
              <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                <span className="truncate">{t('packs.updatedAt', { time: formatDateTime(pack.updated_at) })}</span>
                <span className="text-[hsl(var(--pix-muted))]">·</span>
                <span>{t('packs.capacity', { used: pack.item_count, capacity: pack.capacity })}</span>
              </div>
            </div>
            <Badge variant={pack.remaining_capacity > 0 ? 'success' : 'warning'}>{pack.item_count}/{pack.capacity}</Badge>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <ProgressBar percent={percent} />
            <div className="flex justify-end gap-1" onClick={(event) => event.stopPropagation()}>
              <Button type="button" size="sm" variant="ghost" disabled={downloading || pack.item_count === 0} onClick={() => onDownloadPack(pack)} aria-label={t('packs.downloadZip')} className="h-8 w-8 rounded-xl px-0 text-muted-foreground hover:text-foreground"><Download /></Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" aria-label={t('packs.moreActions')} className="h-8 w-8 rounded-xl px-0 text-muted-foreground hover:text-foreground"><MoreHorizontal /></Button></DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onStartRename(pack)}><Pencil />{t('packs.rename')}</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onToggleArchive(pack)}><Archive />{archived ? t('packs.restore') : t('packs.archive')}</DropdownMenuItem>
                  {pack.item_count === 0 && <DropdownMenuItem onClick={() => onDeletePack(pack)}><Trash2 />{t('packs.deleteEmpty')}</DropdownMenuItem>}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function PackIcon({ selected, archived, children }: { selected: boolean; archived: boolean; children: ReactNode }) {
  return (
    <div className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-2xl border shadow-inner', selected ? 'border-primary/28 bg-primary/12 text-primary' : 'border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper)/.64)] text-muted-foreground dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-white/[.04]', archived && 'grayscale')}>
      {children}
    </div>
  )
}

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[hsl(var(--pix-paper-muted)/.72)] dark:bg-black/25" aria-hidden="true">
      <div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out" style={{ width: `${percent}%` }} />
    </div>
  )
}

function getPackPercent(pack: Pick<AssetPack, 'capacity' | 'item_count'>) {
  if (pack.capacity <= 0) return 0
  return Math.min(100, Math.max(0, Math.round((pack.item_count / pack.capacity) * 100)))
}
