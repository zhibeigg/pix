import { Archive, Download, MoreHorizontal, RotateCcw } from 'lucide-react'
import { useI18n } from '../i18n'
import type { GenerationBatch } from '../types'
import { formatDateTime } from '../lib/utils'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu'
import { PixPanel } from './pix/PixPanel'

type Props = { batches: GenerationBatch[]; selectedBatchId: number | null; onSelectBatch: (batch: GenerationBatch) => void; onClearSelection: () => void; onRetryFailed: (batch: GenerationBatch) => void; onDownloadBatch: (batch: GenerationBatch) => void; onRenameBatch: (batch: GenerationBatch) => void; onToggleArchive: (batch: GenerationBatch) => void; onDeleteBatch: (batch: GenerationBatch) => void; retrying: boolean; downloading: boolean; onRefresh: () => void }

export function BatchPanel({ batches, selectedBatchId, onSelectBatch, onClearSelection, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch, retrying, downloading, onRefresh }: Props) {
  const { t } = useI18n()
  return (
    <PixPanel eyebrow={t('batches.eyebrow')} title={t('batches.title')} action={<div className="flex gap-2"><Button variant={selectedBatchId === null ? 'default' : 'outline'} size="sm" onClick={onClearSelection}>{t('common.all')}</Button><Button variant="outline" size="sm" onClick={onRefresh}>{t('common.refresh')}</Button></div>}>
      {batches.length === 0 ? <Alert variant="info">{t('batches.empty')}</Alert> : <div className="grid gap-3">{batches.map((batch) => <BatchCard key={batch.id} batch={batch} selected={selectedBatchId === batch.id} retrying={retrying} downloading={downloading} onSelectBatch={onSelectBatch} onRetryFailed={onRetryFailed} onDownloadBatch={onDownloadBatch} onRenameBatch={onRenameBatch} onToggleArchive={onToggleArchive} onDeleteBatch={onDeleteBatch} />)}</div>}
    </PixPanel>
  )
}

function BatchCard({ batch, selected, retrying, downloading, onSelectBatch, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch }: { batch: GenerationBatch; selected: boolean; retrying: boolean; downloading: boolean; onSelectBatch: (batch: GenerationBatch) => void; onRetryFailed: (batch: GenerationBatch) => void; onDownloadBatch: (batch: GenerationBatch) => void; onRenameBatch: (batch: GenerationBatch) => void; onToggleArchive: (batch: GenerationBatch) => void; onDeleteBatch: (batch: GenerationBatch) => void }) {
  const { t } = useI18n()
  const progress = batch.job_count > 0 ? Math.round((batch.succeeded_count / batch.job_count) * 100) : 0
  const archived = batch.status === 'archived'
  return (
    <article className={`rounded-lg border bg-card p-4 ${selected ? 'border-primary ring-2 ring-primary/15' : 'border-border'} ${archived ? 'opacity-65' : ''}`}>
      <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate font-semibold">#{batch.id} · {batch.name}</h3><p className="text-sm text-muted-foreground">{modeLabel(batch.mode, t)} · {t('batches.credits', { count: batch.total_price_credits })} · {formatDateTime(batch.created_at)}</p></div><Badge variant={progress === 100 ? 'success' : 'outline'}>{progress}%</Badge></div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${batch.failed_count ? 'bg-amber-500' : 'bg-primary'}`} style={{ width: `${progress}%` }} /></div>
      <div className="mt-3 flex flex-wrap gap-1.5"><Badge variant="outline">{t('batches.assetCount', { count: batch.job_count })}</Badge><Badge variant="success">{t('batches.doneCount', { count: batch.succeeded_count })}</Badge>{batch.failed_count > 0 && <Badge variant="danger">{t('batches.failedCount', { count: batch.failed_count })}</Badge>}{(batch.running_count > 0 || batch.pending_count > 0) && <Badge variant="info">{t('batches.runningCount', { count: batch.running_count + batch.pending_count })}</Badge>}</div>
      <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant={selected ? 'default' : 'outline'} onClick={() => onSelectBatch(batch)}>{selected ? t('batches.current') : t('common.open')}</Button>{batch.succeeded_count > 0 && <Button size="sm" variant="outline" disabled={downloading} onClick={() => onDownloadBatch(batch)}><Download />ZIP</Button>}{batch.failed_count > 0 && <Button size="sm" variant="outline" disabled={retrying} onClick={() => onRetryFailed(batch)}><RotateCcw />{t('batches.failedItems')}</Button>}<DropdownMenu><DropdownMenuTrigger asChild><Button size="sm" variant="ghost"><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onClick={() => onRenameBatch(batch)}>{t('batches.rename')}</DropdownMenuItem><DropdownMenuItem onClick={() => onToggleArchive(batch)}><Archive />{archived ? t('batches.restore') : t('batches.archive')}</DropdownMenuItem>{batch.job_count === 0 && <DropdownMenuItem onClick={() => onDeleteBatch(batch)}>{t('batches.deleteEmpty')}</DropdownMenuItem>}</DropdownMenuContent></DropdownMenu></div>
    </article>
  )
}

function modeLabel(mode: string, t: (key: string, options?: Record<string, unknown>) => string) {
  return t(`jobs.type.${mode}`, { defaultValue: mode })
}
