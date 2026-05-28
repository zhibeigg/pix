import { useMemo, useState, type DragEvent } from 'react'
import { Crosshair, Download, FileDown, PackagePlus, RotateCcw, Trash2, X } from 'lucide-react'
import { fileName, signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { ContactSheetCandidate, GenerationJob, JobOutput, SequenceAlignmentRequest } from '../types'
import { jobInputSummary } from '../pixelize'
import { jobTypeLabel } from '../labels'
import { formatDateTime } from '../lib/utils'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Checkbox } from './ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog'
import { PixPanel } from './pix/PixPanel'
import { PixStatusBadge } from './pix/PixStatusBadge'
import { JobErrorSummary } from './JobErrorSummary'
import { SpriteSequencePreview } from './SpriteSequencePreview'
import { SpriteSequenceAlignmentEditor } from './SpriteSequenceAlignmentEditor'
import { JobParameterSnapshotDialog } from './JobParameterSnapshotDialog'

type GalleryGridProps = { jobs: GenerationJob[]; selectedJobId: number | null; subtitle?: string; retryingJobId?: number | null; onSelect: (job: GenerationJob) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void>; onDeleteJob?: (job: GenerationJob) => void | Promise<void>; onSaveToPack?: (job: GenerationJob) => void | Promise<void>; onRemoveFromPack?: (job: GenerationJob) => void | Promise<void>; onSaveSequenceAlignment?: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void>; draggableSucceeded?: boolean }
type DownloadKind = 'source' | 'pixelized' | 'sprite_gif' | 'sprite_sheet' | 'sequence_json' | 'contact_sheet'
type DownloadOption = { id: DownloadKind; label: string; description: string; path: string; url: string; filename: string }

export function GalleryGrid({ jobs, subtitle, selectedJobId, retryingJobId = null, onSelect, onCandidatePixelize, onRetryJob, onDeleteJob, onSaveToPack, onRemoveFromPack, onSaveSequenceAlignment, draggableSucceeded = false }: GalleryGridProps) {
  const { t } = useI18n()
  const [page, setPage] = useState(1)
  const pageSize = 48
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <PixPanel eyebrow={t('gallery.eyebrow')} title={t('gallery.title')} description={subtitle} action={<div className="flex flex-wrap gap-2"><Badge variant="info">{t('gallery.itemCount', { count: ordered.length })}</Badge><Badge variant="outline">{t('gallery.maxWorks')}</Badge><Badge variant="outline">{t('gallery.page', { page: safePage, total: totalPages })}</Badge></div>}>
      {ordered.length === 0 ? <div className="rounded-lg border border-dashed border-border bg-muted/45 p-8 text-center text-muted-foreground">{t('gallery.empty')}</div> : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {visible.map((job) => <GalleryCard key={job.id} job={job} selected={selectedJobId === job.id} retrying={retryingJobId === job.id} draggable={draggableSucceeded && job.status === 'succeeded'} onSelect={onSelect} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} onDeleteJob={onDeleteJob} onSaveToPack={onSaveToPack} onRemoveFromPack={onRemoveFromPack} onSaveSequenceAlignment={onSaveSequenceAlignment} />)}
        </div>
      )}
      {ordered.length > pageSize && <div className="mt-5 flex justify-center gap-2"><Button type="button" variant="outline" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{t('gallery.previous')}</Button><Button type="button" variant="outline" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>{t('gallery.next')}</Button></div>}
    </PixPanel>
  )
}

function GalleryCard({ job, selected, retrying, draggable, onSelect, onCandidatePixelize, onRetryJob, onDeleteJob, onSaveToPack, onRemoveFromPack, onSaveSequenceAlignment }: { job: GenerationJob; selected: boolean; retrying: boolean; draggable: boolean; onSelect: (job: GenerationJob) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void>; onDeleteJob?: (job: GenerationJob) => void | Promise<void>; onSaveToPack?: (job: GenerationJob) => void | Promise<void>; onRemoveFromPack?: (job: GenerationJob) => void | Promise<void>; onSaveSequenceAlignment?: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void> }) {
  const { language, t } = useI18n()
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const downloadOptions = output ? buildDownloadOptions(job, output, t) : []
  const [alignmentOpen, setAlignmentOpen] = useState(false)
  const [savingAlignment, setSavingAlignment] = useState(false)
  const isActive = isActiveJob(job)
  const previewUrl = isActive ? null : output ? signedFileUrl(output.pixelized_url || output.preview_url || output.source_url || undefined) : signedFileUrl(job.input_image_url)
  const spriteSheetUrl = isActive ? null : signedFileUrl(output?.sprite_sheet_url || undefined)
  const spriteFps = spriteFpsFromJob(job)
  const typeLabel = jobTypeLabel(job.job_type, language)
  const sizeTag = jobPixelSizeTag(job, output)
  const displayName = jobDisplayName(job, t)
  const summary = jobDisplaySummary(job, displayName, t)
  function startDrag(event: DragEvent<HTMLElement>) {
    if (!draggable) return
    event.dataTransfer.effectAllowed = 'copy'
    event.dataTransfer.setData('application/x-pix-job-id', String(job.id))
    event.dataTransfer.setData('text/plain', String(job.id))
  }

  async function saveAlignment(payload: SequenceAlignmentRequest) {
    if (!onSaveSequenceAlignment) return
    setSavingAlignment(true)
    try {
      await onSaveSequenceAlignment(job, payload)
      setAlignmentOpen(false)
    } finally {
      setSavingAlignment(false)
    }
  }

  return (
    <article
      tabIndex={0}
      aria-expanded={selected}
      draggable={draggable}
      onDragStart={startDrag}
      onClick={() => onSelect(job)}
      onKeyDown={(event) => {
        if (event.currentTarget !== event.target) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect(job)
        }
      }}
      className={`cursor-pointer overflow-hidden rounded-lg border bg-card transition-colors hover:border-primary/55 hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-[hsl(var(--pix-dark-card))] ${isActive ? 'pix-work-card-loading' : ''} ${selected ? 'border-primary shadow-[0_4px_12px_rgba(15,15,15,0.08)] ring-2 ring-primary/15' : job.status === 'failed' ? 'border-destructive/40' : 'border-border dark:border-[hsl(var(--pix-dark-hairline))]'}`}
    >
      <SpriteSequencePreview sheetUrl={spriteSheetUrl} frames={output?.sprite_frames ?? []} fps={spriteFps} fallbackUrl={previewUrl} loading={isActive} label={isActive ? jobStatusLabel(job, t) : job.status === 'succeeded' ? 'PIX' : t('gallery.waitingOutput')} className="h-36 min-h-0 rounded-none border-0 border-b sm:h-40 xl:h-36 2xl:h-40" imageClassName="absolute inset-0 h-full max-h-none w-full p-0 bg-contain" ><div className="absolute right-2 top-2"><PixStatusBadge status={job.status} /></div></SpriteSequencePreview>
      <div className="grid gap-2.5 p-3">
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline">#{job.id}</Badge>
            <Badge variant="secondary" className="dark:border-[hsl(var(--pix-brand-purple-300)/.24)] dark:bg-[hsl(var(--pix-brand-purple-800)/.42)] dark:text-[hsl(var(--pix-brand-purple-300))]">{typeLabel}</Badge>
            {sizeTag && <Badge variant="outline" className={pixelSizeBadgeClass(sizeTag.size)} title={sizeTag.title}>{sizeTag.label}</Badge>}
          </div>
          <div>
            <h3 className="line-clamp-2 text-sm font-semibold leading-snug">{displayName}</h3>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{summary}</p>
          </div>
        </div>
        {selected && <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{t('common.points', { count: job.price_credits })}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge>{job.batch_name && <Badge variant="outline">{job.batch_name}</Badge>}<QuickParameterBadges job={job} output={output} /></div>}
        {selected && job.status === 'failed' && <JobErrorSummary error={job.error_message} compact />}
        {selected && output && <CandidateMiniGrid job={job} output={output} onCandidatePixelize={onCandidatePixelize} />}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={selected ? 'default' : 'outline'} onClick={(event) => { event.stopPropagation(); onSelect(job) }}>{selected ? t('gallery.expanded') : t('gallery.details')}</Button>
          {output && <JobParameterSnapshotDialog job={job} output={output} />}
          {!output && <JobParameterSnapshotDialog job={job} />}
          {job.status === 'succeeded' && output && output.sprite_frames.length > 0 && onSaveSequenceAlignment && <Dialog open={alignmentOpen} onOpenChange={setAlignmentOpen}>
            <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); setAlignmentOpen(true) }}><Crosshair />{t('gallery.alignFrames')}</Button>
            <DialogContent onClick={(event) => event.stopPropagation()} className="left-1/2 top-1/2 flex h-[min(92vh,900px)] w-[min(96vw,1180px)] max-w-none -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden p-0 sm:max-w-none">
              <div className="shrink-0 border-b border-border px-6 py-5 pr-12 dark:border-[hsl(var(--pix-dark-hairline))]">
                <DialogHeader>
                  <DialogTitle>{t('alignment.title')}</DialogTitle>
                  <DialogDescription>{t('alignment.description')}</DialogDescription>
                </DialogHeader>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                <SpriteSequenceAlignmentEditor job={job} output={output} saving={savingAlignment} onSave={saveAlignment} />
              </div>
            </DialogContent>
          </Dialog>}
          {job.status === 'succeeded' && onSaveToPack && <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); void onSaveToPack(job) }}><PackagePlus />{t('packs.saveWork')}</Button>}
          {onRemoveFromPack && <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); void onRemoveFromPack(job) }}><X />{t('packs.removeWork')}</Button>}
          {job.status === 'failed' && onRetryJob && <Button size="sm" variant="destructive" disabled={retrying} onClick={(event) => { event.stopPropagation(); void onRetryJob(job) }}><RotateCcw />{retrying ? t('gallery.retrying') : t('gallery.retry')}</Button>}
          {downloadOptions.length > 0 && <DownloadDialog job={job} options={downloadOptions} />}
          {onDeleteJob && !['pending', 'running'].includes(job.status) && <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); void onDeleteJob(job) }}><Trash2 />{t('gallery.delete')}</Button>}
        </div>
      </div>
    </article>
  )
}

function QuickParameterBadges({ job, output }: { job: GenerationJob; output?: JobOutput }) {
  const params = asRecord(job.params_json)
  const pixelize = asRecord(params?.pixelize)
  const sprite = asRecord(params?.sprite)
  const model = typeof params?.image_model === 'string' && params.image_model ? params.image_model : null
  const colors = Number(pixelize?.colors)
  const requestedSize = asNumberPair(pixelize?.output_size)
  const realSize = asNumberPair(output?.pixelized_size)
  const size = realSize ?? requestedSize
  const chips: string[] = []
  if (size) chips.push(size[0] === size[1] ? `${size[0]}×${size[0]}` : `${size[0]}×${size[1]}`)
  if (Number.isFinite(colors) && colors > 0) chips.push(`${Math.round(colors)} 色`)
  if (model) chips.push(model)
  if (job.job_type === 'sprite_sheet') {
    const frameCount = Number(sprite?.frame_count)
    const fps = Number(sprite?.fps)
    if (Number.isFinite(frameCount) && frameCount > 0) chips.push(`${Math.round(frameCount)} 帧`)
    if (Number.isFinite(fps) && fps > 0) chips.push(`${Math.round(fps)} FPS`)
  }
  return <>{chips.slice(0, 5).map((chip) => <Badge key={chip} variant="outline">{chip}</Badge>)}</>
}

function DownloadDialog({ job, options }: { job: GenerationJob; options: DownloadOption[] }) {
  const { t } = useI18n()
  const defaultSelected = options.find((option) => option.id === 'pixelized')?.id ?? options[0]?.id
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<DownloadKind[]>(defaultSelected ? [defaultSelected] : [])
  const selectedSet = new Set(selected)
  const selectedOptions = options.filter((option) => selectedSet.has(option.id))

  function toggleOption(id: DownloadKind, checked: boolean) {
    setSelected((current) => checked ? Array.from(new Set([...current, id])) : current.filter((item) => item !== id))
  }

  function downloadSelected() {
    for (const option of selectedOptions) {
      downloadImage(option.url, option.filename)
    }
    setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); setOpen(true) }}><Download />{t('downloads.image')}</Button>
      <DialogContent onClick={(event) => event.stopPropagation()} className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('downloads.dialogTitle')}</DialogTitle>
          <DialogDescription>{t('downloads.dialogDescription', { id: job.id })}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          {options.map((option) => (
            <label key={option.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-muted/30 p-3 transition hover:bg-muted/55 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
              <Checkbox checked={selectedSet.has(option.id)} onCheckedChange={(checked) => toggleOption(option.id, Boolean(checked))} className="mt-0.5" />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 text-sm font-semibold"><FileDown className="h-4 w-4 text-primary" />{option.label}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{option.description}</span>
              </span>
            </label>
          ))}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
          <Button type="button" disabled={selectedOptions.length === 0} onClick={downloadSelected}>{t('downloads.selected', { count: selectedOptions.length })}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function isActiveJob(job: GenerationJob) {
  return job.status === 'pending' || job.status === 'running'
}

function jobStatusLabel(job: GenerationJob, t: (key: string, options?: Record<string, unknown>) => string) {
  return job.status === 'pending' ? t('jobs.status.pending') : job.status === 'running' ? t('jobs.status.running') : t('gallery.waitingOutput')
}

function CandidateMiniGrid({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { t } = useI18n()
  if (!output.candidates?.length) return null
  return <div className="grid grid-cols-3 gap-2">{output.candidates.slice(0, 9).map((candidate) => <button type="button" key={candidate.path} className="rounded-lg border border-border bg-muted/35 p-1.5 text-xs dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]" onClick={(event) => { event.stopPropagation(); void onCandidatePixelize?.(job, candidate) }} title={candidate.reason ?? undefined}><img src={signedFileUrl(candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined)} alt={t('gallery.candidate', { index: candidate.index })} className="mx-auto aspect-square w-full object-contain [image-rendering:pixelated]" /><span>{candidate.rank ? `#${candidate.rank}` : t('gallery.candidate', { index: candidate.index })}</span></button>)}</div>
}

function buildDownloadOptions(job: GenerationJob, output: JobOutput, t: (key: string, options?: Record<string, unknown>) => string): DownloadOption[] {
  const specs: Array<{ id: DownloadKind; label: string; description: string; path?: string | null; url?: string | null; fallback: string }> = [
    { id: 'source', label: t('downloads.source'), description: t('downloads.sourceDescription'), path: output.source_path, url: output.source_url, fallback: '01_source.png' },
    { id: 'pixelized', label: t('downloads.pixelized'), description: t('downloads.pixelizedDescription'), path: output.pixelized_path, url: output.pixelized_url, fallback: '03_pixelized.png' },
    { id: 'sprite_gif', label: t('downloads.spriteGif'), description: t('downloads.spriteGifDescription'), path: output.sprite_gif_path, url: output.sprite_gif_url, fallback: 'sprite.gif' },
    { id: 'sprite_sheet', label: t('downloads.spriteSheet'), description: t('downloads.spriteSheetDescription'), path: output.sprite_sheet_path, url: output.sprite_sheet_url, fallback: 'sprite-sheet.png' },
    { id: 'sequence_json', label: t('downloads.sequenceJson'), description: t('downloads.sequenceJsonDescription'), path: output.sequence_json_path, url: output.sequence_json_url, fallback: 'sequence.json' },
    { id: 'contact_sheet', label: t('downloads.contactSheet'), description: t('downloads.contactSheetDescription'), path: output.contact_sheet_path, url: output.contact_sheet_url, fallback: 'contact-sheet.png' },
  ]
  return specs.flatMap((spec) => {
    const url = signedFileUrl(spec.url)
    if (!url) return []
    return [{ id: spec.id, label: spec.label, description: spec.description, path: spec.path || '', url, filename: downloadFileName(job, spec.path || spec.fallback) }]
  })
}

function downloadImage(url: string, filename: string) {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

function downloadFileName(job: GenerationJob, path: string) {
  const raw = safeFileNamePart(fileName(path || `pix-job-${job.id}.png`))
  const prefix = jobFileNamePrefix(job)
  if (!raw) return `${prefix}.png`
  return raw.startsWith(`${prefix}_`) ? raw : `${prefix}_${raw}`
}

function jobFileNamePrefix(job: GenerationJob) {
  const asset = asRecord(job.params_json?.asset)
  const assetName = typeof asset?.name === 'string' ? asset.name.trim() : ''
  const prompt = (job.prompt ?? '').replace(/\s+/g, ' ').trim()
  return safeFileNamePart(assetName || prompt || `pix-job-${job.id}`).slice(0, 80) || `pix-job-${job.id}`
}

function safeFileNamePart(value: string) {
  return value.trim().replace(/\s+/g, '_').replace(/[<>:"/\\|?*\x00-\x1F]/g, '_').replace(/^\.+$/, '').replace(/^_+|_+$/g, '')
}

function jobDisplayName(job: GenerationJob, t: (key: string, options?: Record<string, unknown>) => string) {
  const asset = asRecord(job.params_json?.asset)
  const assetName = typeof asset?.name === 'string' ? asset.name.trim() : ''
  if (assetName) return clampText(assetName, 42)
  const prompt = (job.prompt ?? '').replace(/\s+/g, ' ').trim()
  if (prompt) return clampText(prompt, 42)
  if (job.input_image_path) return t('gallery.uploadedImage')
  return `#${job.id}`
}

function jobDisplaySummary(job: GenerationJob, displayName: string, t: (key: string, options?: Record<string, unknown>) => string) {
  const asset = asRecord(job.params_json?.asset)
  const extraPrompt = typeof asset?.extra_prompt === 'string' ? asset.extra_prompt.trim() : ''
  if (extraPrompt) return clampText(extraPrompt, 96)
  const summary = jobInputSummary(job, t('gallery.noInputSummary'))
  return summary === displayName ? t('gallery.expandHint') : summary
}

function jobPixelSizeTag(job: GenerationJob, output?: JobOutput): { size: [number, number]; label: string; title: string } | null {
  const realSize = asNumberPair(output?.pixelized_size)
  const requestedSize = asNumberPair(asRecord(job.params_json?.pixelize)?.output_size)
  const size = realSize ?? requestedSize
  if (!size) return null
  const [width, height] = size
  const label = width === height ? `${width}x` : `${width}×${height}`
  return {
    size,
    label,
    title: realSize ? `真实输出尺寸：${width}×${height}` : `请求尺寸：${width}×${height}`,
  }
}

function asNumberPair(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) return null
  const width = Number(value[0])
  const height = Number(value[1])
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null
  return [Math.round(width), Math.round(height)]
}

function pixelSizeBadgeClass(size: [number, number]) {
  const side = Math.max(size[0], size[1])
  if (side <= 16) return 'border-[hsl(var(--pix-brand-green)/.28)] bg-[hsl(var(--pix-mint)/.84)] text-[hsl(var(--pix-brand-green))] dark:border-[hsl(var(--pix-brand-green)/.42)] dark:bg-[hsl(var(--pix-brand-green)/.18)] dark:text-[hsl(var(--pix-mint))]'
  if (side <= 24) return 'border-[hsl(var(--pix-brand-teal)/.28)] bg-[hsl(var(--pix-sky)/.88)] text-[hsl(var(--pix-brand-teal))] dark:border-[hsl(var(--pix-brand-teal)/.42)] dark:bg-[hsl(var(--pix-brand-teal)/.18)] dark:text-[hsl(var(--pix-sky))]'
  if (side <= 32) return 'border-[hsl(var(--pix-brand-yellow)/.42)] bg-[hsl(var(--pix-yellow)/.9)] text-[hsl(var(--pix-brand-brown))] dark:border-[hsl(var(--pix-brand-yellow)/.5)] dark:bg-[hsl(var(--pix-brand-yellow)/.18)] dark:text-[hsl(var(--pix-yellow))]'
  if (side <= 64) return 'border-[hsl(var(--pix-brand-purple)/.26)] bg-[hsl(var(--pix-lavender)/.9)] text-[hsl(var(--pix-brand-purple-800))] dark:border-[hsl(var(--pix-brand-purple-300)/.36)] dark:bg-[hsl(var(--pix-brand-purple-800)/.46)] dark:text-[hsl(var(--pix-brand-purple-300))]'
  return 'border-[hsl(var(--pix-brand-orange)/.28)] bg-[hsl(var(--pix-peach)/.92)] text-[hsl(var(--pix-brand-orange-deep))] dark:border-[hsl(var(--pix-brand-orange)/.45)] dark:bg-[hsl(var(--pix-brand-orange)/.18)] dark:text-[hsl(var(--pix-peach))]'
}

function spriteFpsFromJob(job: GenerationJob) {
  const sprite = asRecord(job.params_json?.sprite)
  const fps = Number(sprite?.fps)
  return Number.isFinite(fps) && fps > 0 ? fps : 8
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function clampText(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max)}…` : value
}
