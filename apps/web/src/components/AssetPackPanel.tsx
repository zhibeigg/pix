import { Archive, Check, Download, Folder, FolderOpen, MoreHorizontal, Pencil, Plus, RefreshCw, Sparkles, Trash2, X } from 'lucide-react'
import { useMemo, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useI18n } from '../i18n'
import type { AssetPack, AssetPackQuota } from '../types'
import { formatDateTime } from '../lib/utils'
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

  async function submitCreate() {
    const trimmed = name.trim()
    if (!trimmed) return
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
    <PixPanel eyebrow={t('packs.eyebrow')} title={t('packs.title')} action={<div className="flex flex-wrap gap-2"><Badge variant={remainingPacks > 0 ? 'success' : 'warning'}>{t('packs.packQuota', { used: packs.length, limit: packLimit })}</Badge><Button variant="outline" size="sm" onClick={onRefresh}><RefreshCw />{t('common.refresh')}</Button></div>}>
      <div className="grid gap-3">
        <div className="rounded-lg border border-border bg-card shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
          <div className="flex flex-wrap items-center gap-1 border-b border-border p-2 dark:border-[hsl(var(--pix-dark-hairline))]" aria-label={t('packs.commandBar')}>
            <CommandButton disabled={!selectedPack} onClick={() => selectedPack && startRename(selectedPack)}><Pencil />{t('packs.rename')}</CommandButton>
            <CommandButton disabled={!selectedPack || selectedPack.item_count === 0 || downloading} onClick={() => selectedPack && onDownloadPack(selectedPack)}><Download />{t('packs.downloadZip')}</CommandButton>
            <CommandButton disabled={!selectedPack} onClick={() => selectedPack && onToggleArchive(selectedPack)}><Archive />{selectedPack?.status === 'archived' ? t('packs.restore') : t('packs.archive')}</CommandButton>
            <CommandButton disabled={!selectedPack || selectedPack.item_count > 0} onClick={() => selectedPack && onDeletePack(selectedPack)}><Trash2 />{t('packs.deleteEmpty')}</CommandButton>
            <div className="mx-1 h-6 w-px bg-border dark:bg-[hsl(var(--pix-dark-hairline))]" />
            <CommandButton onClick={onExpandPackLimit}><Sparkles />{t('packs.expandPackLimit', { price: expandPrice })}</CommandButton>
            {selectedPack && <Button type="button" variant="ghost" size="sm" onClick={onClearSelection}><X />{t('packs.clearSelection')}</Button>}
          </div>
          <div className="grid gap-3 p-3">
            <div className="rounded-md border border-border bg-muted/35 p-2.5 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="text-[11px] font-semibold uppercase tracking-[.12em] text-muted-foreground" htmlFor="new-pack-name">{t('packs.newName')}</label>
                <Badge variant="outline">{t('packs.packCapacity', { capacity: packCapacity })}</Badge>
              </div>
              <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                <Input id="new-pack-name" value={name} maxLength={160} disabled={remainingPacks <= 0} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void submitCreate() }} placeholder={t('packs.newPlaceholder')} />
                <Button type="button" disabled={creating || !name.trim() || remainingPacks <= 0} onClick={() => void submitCreate()}><Plus />{t('packs.create')}</Button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{remainingPacks > 0 ? t('packs.remainingPackSlots', { count: remainingPacks }) : t('packs.packLimitReached')}</p>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[.12em] text-muted-foreground">{t('packs.folderList')}</p>
                <span className="text-xs text-muted-foreground">{selectedPack ? t('packs.selectedSummary', { name: selectedPack.name }) : t('packs.noSelectionSummary')}</span>
              </div>
              {packs.length === 0 ? <Alert variant="info">{t('packs.empty')}</Alert> : (
                <div className="grid gap-1 rounded-md border border-border bg-background/72 p-1 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
                  {packs.map((pack) => <AssetPackRow key={pack.id} pack={pack} selected={selectedPackId === pack.id} editing={editingPackId === pack.id} editName={editName} renaming={renamingPackId === pack.id} downloading={downloading} onEditNameChange={setEditName} onSelectPack={onSelectPack} onStartRename={startRename} onSubmitRename={submitRename} onCancelRename={cancelRename} onToggleArchive={onToggleArchive} onDeletePack={onDeletePack} onDownloadPack={onDownloadPack} onKeySelect={selectFromKeyboard} />)}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </PixPanel>
  )
}

function CommandButton({ children, disabled, onClick }: { children: ReactNode; disabled?: boolean; onClick: () => void }) {
  return <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={onClick} className="h-8 px-2.5">{children}</Button>
}

function AssetPackRow({ pack, selected, editing, editName, renaming, downloading, onEditNameChange, onSelectPack, onStartRename, onSubmitRename, onCancelRename, onToggleArchive, onDeletePack, onDownloadPack, onKeySelect }: { pack: AssetPack; selected: boolean; editing: boolean; editName: string; renaming: boolean; downloading: boolean; onEditNameChange: (name: string) => void; onSelectPack: (pack: AssetPack) => void; onStartRename: (pack: AssetPack) => void; onSubmitRename: (pack: AssetPack) => Promise<void>; onCancelRename: () => void; onToggleArchive: (pack: AssetPack) => void; onDeletePack: (pack: AssetPack) => void; onDownloadPack: (pack: AssetPack) => void; onKeySelect: (event: KeyboardEvent<HTMLDivElement>, pack: AssetPack) => void }) {
  const { t } = useI18n()
  const archived = pack.status === 'archived'
  const percent = pack.capacity > 0 ? Math.round((pack.item_count / pack.capacity) * 100) : 0
  const FolderIcon = selected ? FolderOpen : Folder
  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={() => onSelectPack(pack)}
      onKeyDown={(event) => onKeySelect(event, pack)}
      className={`group grid cursor-default grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-md border px-2.5 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selected ? 'border-primary/45 bg-primary/10 ring-1 ring-primary/15 dark:bg-primary/15' : 'border-transparent hover:border-border hover:bg-muted/55 dark:hover:border-[hsl(var(--pix-dark-hairline))] dark:hover:bg-white/10'} ${archived ? 'opacity-70' : ''}`}
    >
      <div className={`grid h-9 w-9 place-items-center rounded-md border ${selected ? 'border-primary/25 bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]'}`}>
        <FolderIcon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        {editing ? (
          <form className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-1.5" onClick={(event) => event.stopPropagation()} onSubmit={(event) => { event.preventDefault(); void onSubmitRename(pack) }}>
            <Input autoFocus value={editName} maxLength={160} disabled={renaming} onChange={(event) => onEditNameChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') onCancelRename() }} aria-label={t('packs.renameEditing', { name: pack.name })} className="h-8" />
            <Button type="submit" size="sm" variant="default" disabled={renaming || !editName.trim()} aria-label={t('packs.saveRename')}><Check /></Button>
            <Button type="button" size="sm" variant="ghost" disabled={renaming} onClick={onCancelRename} aria-label={t('packs.cancelRename')}><X /></Button>
          </form>
        ) : (
          <>
            <div className="flex min-w-0 items-center gap-2">
              <p className="truncate text-sm font-semibold">{pack.name}</p>
              <span className="shrink-0 text-xs text-muted-foreground">#{pack.id}</span>
              {archived && <Badge variant="secondary">{t('packs.archived')}</Badge>}
            </div>
            <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>{t('packs.updatedAt', { time: formatDateTime(pack.updated_at) })}</span>
              <span>·</span>
              <span>{t('packs.capacity', { used: pack.item_count, capacity: pack.capacity })}</span>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, percent)}%` }} /></div>
          </>
        )}
      </div>
      <div className="flex items-center gap-1" onClick={(event) => event.stopPropagation()}>
        <Badge variant={pack.remaining_capacity > 0 ? 'success' : 'warning'}>{pack.item_count}/{pack.capacity}</Badge>
        <Button type="button" size="sm" variant="ghost" disabled={downloading || pack.item_count === 0} onClick={() => onDownloadPack(pack)} aria-label={t('packs.downloadZip')}><Download /></Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" aria-label={t('packs.moreActions')}><MoreHorizontal /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onStartRename(pack)}><Pencil />{t('packs.rename')}</DropdownMenuItem>
            <DropdownMenuItem onClick={() => onToggleArchive(pack)}><Archive />{archived ? t('packs.restore') : t('packs.archive')}</DropdownMenuItem>
            {pack.item_count === 0 && <DropdownMenuItem onClick={() => onDeletePack(pack)}><Trash2 />{t('packs.deleteEmpty')}</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
