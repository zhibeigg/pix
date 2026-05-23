import { Archive, Download, MoreHorizontal, Plus, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'
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
  onRenamePack: (pack: AssetPack) => void
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
  const remainingPacks = quota?.remaining_packs ?? 0
  const packLimit = quota?.pack_limit ?? packs.length
  const packCapacity = quota?.pack_capacity ?? 100
  const expandPrice = quota?.expand_price_credits ?? 99

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

  return (
    <PixPanel eyebrow={t('packs.eyebrow')} title={t('packs.title')} action={<div className="flex flex-wrap gap-2"><Badge variant={remainingPacks > 0 ? 'success' : 'warning'}>{t('packs.packQuota', { used: packs.length, limit: packLimit })}</Badge><Button variant="outline" size="sm" onClick={onRefresh}><RefreshCw />{t('common.refresh')}</Button></div>}>
      <div className="grid gap-3">
        <div className="rounded-lg border border-border bg-muted/35 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground" htmlFor="new-pack-name">{t('packs.newName')}</label>
            <Badge variant="outline">{t('packs.packCapacity', { capacity: packCapacity })}</Badge>
          </div>
          <div className="mt-2 flex gap-2">
            <Input id="new-pack-name" value={name} maxLength={160} disabled={remainingPacks <= 0} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void submitCreate() }} placeholder={t('packs.newPlaceholder')} />
            <Button type="button" disabled={creating || !name.trim() || remainingPacks <= 0} onClick={() => void submitCreate()}><Plus />{t('packs.create')}</Button>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>{remainingPacks > 0 ? t('packs.remainingPackSlots', { count: remainingPacks }) : t('packs.packLimitReached')}</span>
            <Button type="button" variant="outline" size="sm" onClick={onExpandPackLimit}><Sparkles />{t('packs.expandPackLimit', { price: expandPrice })}</Button>
          </div>
        </div>
        {packs.length === 0 ? <Alert variant="info">{t('packs.empty')}</Alert> : <div className="grid gap-3">{packs.map((pack) => <AssetPackCard key={pack.id} pack={pack} selected={selectedPackId === pack.id} downloading={downloading} onSelectPack={onSelectPack} onRenamePack={onRenamePack} onToggleArchive={onToggleArchive} onDeletePack={onDeletePack} onDownloadPack={onDownloadPack} />)}</div>}
        {selectedPackId !== null && <Button type="button" variant="ghost" onClick={onClearSelection}>{t('packs.clearSelection')}</Button>}
      </div>
    </PixPanel>
  )
}

function AssetPackCard({ pack, selected, downloading, onSelectPack, onRenamePack, onToggleArchive, onDeletePack, onDownloadPack }: { pack: AssetPack; selected: boolean; downloading: boolean; onSelectPack: (pack: AssetPack) => void; onRenamePack: (pack: AssetPack) => void; onToggleArchive: (pack: AssetPack) => void; onDeletePack: (pack: AssetPack) => void; onDownloadPack: (pack: AssetPack) => void }) {
  const { t } = useI18n()
  const archived = pack.status === 'archived'
  const percent = pack.capacity > 0 ? Math.round((pack.item_count / pack.capacity) * 100) : 0
  return (
    <article className={`rounded-lg border bg-card p-4 ${selected ? 'border-primary ring-2 ring-primary/15' : 'border-border'} ${archived ? 'opacity-65' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold">#{pack.id} · {pack.name}</h3>
          <p className="text-sm text-muted-foreground">{t('packs.updatedAt', { time: formatDateTime(pack.updated_at) })}</p>
        </div>
        <Badge variant={pack.remaining_capacity > 0 ? 'success' : 'warning'}>{pack.item_count}/{pack.capacity}</Badge>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, percent)}%` }} /></div>
      <div className="mt-3 flex flex-wrap gap-1.5"><Badge variant="outline">{t('packs.itemCount', { count: pack.item_count })}</Badge><Badge variant="outline">{t('packs.remaining', { count: pack.remaining_capacity })}</Badge>{archived && <Badge variant="secondary">{t('packs.archived')}</Badge>}</div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant={selected ? 'default' : 'outline'} onClick={() => onSelectPack(pack)}>{selected ? t('packs.current') : t('common.open')}</Button>
        <Button size="sm" variant="outline" disabled={downloading || pack.item_count === 0} onClick={() => onDownloadPack(pack)}><Download />ZIP</Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button size="sm" variant="ghost"><MoreHorizontal /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onRenamePack(pack)}>{t('packs.rename')}</DropdownMenuItem>
            <DropdownMenuItem onClick={() => onToggleArchive(pack)}><Archive />{archived ? t('packs.restore') : t('packs.archive')}</DropdownMenuItem>
            {pack.item_count === 0 && <DropdownMenuItem onClick={() => onDeletePack(pack)}><Trash2 />{t('packs.deleteEmpty')}</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </article>
  )
}
