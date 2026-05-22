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
  const { text } = useI18n()
  return (
    <PixPanel eyebrow={text('素材包', 'Packs')} title={text('批量素材包', 'Batch packs')} action={<div className="flex gap-2"><Button variant={selectedBatchId === null ? 'default' : 'outline'} size="sm" onClick={onClearSelection}>{text('全部', 'All')}</Button><Button variant="outline" size="sm" onClick={onRefresh}>{text('刷新', 'Refresh')}</Button></div>}>
      {batches.length === 0 ? <Alert variant="info">{text('批量生产后会出现在这里；素材包可下载、归档或只重试失败项。', 'Batch results appear here; packs can be downloaded, archived, or retried only for failed items.')}</Alert> : <div className="grid gap-3">{batches.map((batch) => <BatchCard key={batch.id} batch={batch} selected={selectedBatchId === batch.id} retrying={retrying} downloading={downloading} onSelectBatch={onSelectBatch} onRetryFailed={onRetryFailed} onDownloadBatch={onDownloadBatch} onRenameBatch={onRenameBatch} onToggleArchive={onToggleArchive} onDeleteBatch={onDeleteBatch} />)}</div>}
    </PixPanel>
  )
}

function BatchCard({ batch, selected, retrying, downloading, onSelectBatch, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch }: { batch: GenerationBatch; selected: boolean; retrying: boolean; downloading: boolean; onSelectBatch: (batch: GenerationBatch) => void; onRetryFailed: (batch: GenerationBatch) => void; onDownloadBatch: (batch: GenerationBatch) => void; onRenameBatch: (batch: GenerationBatch) => void; onToggleArchive: (batch: GenerationBatch) => void; onDeleteBatch: (batch: GenerationBatch) => void }) {
  const { text } = useI18n()
  const progress = batch.job_count > 0 ? Math.round((batch.succeeded_count / batch.job_count) * 100) : 0
  const archived = batch.status === 'archived'
  return (
    <article className={`rounded-lg border bg-card p-4 ${selected ? 'border-primary ring-2 ring-primary/15' : 'border-border'} ${archived ? 'opacity-65' : ''}`}>
      <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate font-semibold">#{batch.id} · {batch.name}</h3><p className="text-sm text-muted-foreground">{modeLabel(batch.mode, text)} · {text(`${batch.total_price_credits} 点`, `${batch.total_price_credits} credits`)} · {formatDateTime(batch.created_at)}</p></div><Badge variant={progress === 100 ? 'success' : 'outline'}>{progress}%</Badge></div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${batch.failed_count ? 'bg-amber-500' : 'bg-primary'}`} style={{ width: `${progress}%` }} /></div>
      <div className="mt-3 flex flex-wrap gap-1.5"><Badge variant="outline">{text(`${batch.job_count} 个素材`, `${batch.job_count} assets`)}</Badge><Badge variant="success">{text(`完成 ${batch.succeeded_count}`, `Done ${batch.succeeded_count}`)}</Badge>{batch.failed_count > 0 && <Badge variant="danger">{text(`失败 ${batch.failed_count}`, `Failed ${batch.failed_count}`)}</Badge>}{(batch.running_count > 0 || batch.pending_count > 0) && <Badge variant="info">{text(`生产中 ${batch.running_count + batch.pending_count}`, `Running ${batch.running_count + batch.pending_count}`)}</Badge>}</div>
      <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant={selected ? 'default' : 'outline'} onClick={() => onSelectBatch(batch)}>{selected ? text('当前素材包', 'Current pack') : text('打开', 'Open')}</Button>{batch.succeeded_count > 0 && <Button size="sm" variant="outline" disabled={downloading} onClick={() => onDownloadBatch(batch)}><Download />ZIP</Button>}{batch.failed_count > 0 && <Button size="sm" variant="outline" disabled={retrying} onClick={() => onRetryFailed(batch)}><RotateCcw />{text('失败项', 'Failed items')}</Button>}<DropdownMenu><DropdownMenuTrigger asChild><Button size="sm" variant="ghost"><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onClick={() => onRenameBatch(batch)}>{text('重命名素材包', 'Rename pack')}</DropdownMenuItem><DropdownMenuItem onClick={() => onToggleArchive(batch)}><Archive />{archived ? text('恢复到活跃', 'Restore to active') : text('归档素材包', 'Archive pack')}</DropdownMenuItem>{batch.job_count === 0 && <DropdownMenuItem onClick={() => onDeleteBatch(batch)}>{text('删除空素材包', 'Delete empty pack')}</DropdownMenuItem>}</DropdownMenuContent></DropdownMenu></div>
    </article>
  )
}

function modeLabel(mode: string, text: (zh: string, en: string) => string) { return ({ asset: text('素材直出', 'Asset output'), text_to_image: text('文字生成', 'Text to image'), image_to_image: text('参考图微调', 'Image to image'), local_pixelize: text('本地像素化', 'Local pixelize'), mixed: text('混合批次', 'Mixed batch') } as Record<string, string>)[mode] ?? mode }
