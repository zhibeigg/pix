import { lazy, Suspense, useEffect, useMemo, useState, type DragEvent, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { CopyPlus, Crosshair, Download, FileDown, PackagePlus, RotateCcw, Share2, Trash2, X } from 'lucide-react'
import { fileName, signedFileUrl, spriteActionsZipUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { ContactSheetCandidate, GalleryQuota, GenerationJob, JobOutput, SequenceAlignmentRequest } from '../types'
import { jobInputSummary } from '../pixelize'
import { jobTypeLabel } from '../labels'
import { formatDateTime } from '../lib/utils'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Checkbox } from './ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogOverlay, DialogPortal, DialogTitle } from './ui/dialog'
import { PixPanel } from './pix/PixPanel'
import { PixStatusBadge } from './pix/PixStatusBadge'
import { JobErrorSummary } from './JobErrorSummary'
import { SpriteSequencePreview } from './SpriteSequencePreview'
import { JobParameterSnapshotDialog } from './JobParameterSnapshotDialog'

const SpriteSequenceAlignmentEditor = lazy(() => import('./SpriteSequenceAlignmentEditor').then((m) => ({ default: m.SpriteSequenceAlignmentEditor })))

type GalleryGridProps = { jobs: GenerationJob[]; selectedJobId: number | null; subtitle?: string; retryingJobId?: number | null; galleryQuota?: GalleryQuota | null; showRetentionQuota?: boolean; onExpandGalleryQuota?: () => void; onSelect: (job: GenerationJob) => void; onReuseJob?: (job: GenerationJob) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void>; onDeleteJob?: (job: GenerationJob) => void | Promise<void>; onDeleteJobs?: (jobs: GenerationJob[]) => void | Promise<void>; onSaveToPack?: (job: GenerationJob) => void | Promise<void>; onRemoveFromPack?: (job: GenerationJob) => void | Promise<void>; onSaveSequenceAlignment?: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void>; onPublishShare?: (job: GenerationJob) => void | Promise<void>; onUnpublishShare?: (job: GenerationJob) => void | Promise<void>; onActiveActionChange?: (action: SpriteRowAction | null) => void; renderJobBadges?: (job: GenerationJob) => ReactNode; draggableSucceeded?: boolean }
type DownloadKind = 'source' | 'pixelized' | 'dual_grid_atlas' | 'dual_grid_preview' | 'sprite_gif' | 'sprite_sheet' | 'sprite_mosaic' | 'sequence_json' | 'contact_sheet' | 'sprite_action_current' | 'sprite_actions_zip'
type DownloadOption = { id: DownloadKind; label: string; description: string; path: string; url: string; filename: string }

export function GalleryGrid({ jobs, subtitle, selectedJobId, retryingJobId = null, galleryQuota = null, showRetentionQuota = true, onExpandGalleryQuota, onSelect, onReuseJob, onCandidatePixelize, onRetryJob, onDeleteJob, onDeleteJobs, onSaveToPack, onRemoveFromPack, onSaveSequenceAlignment, onPublishShare, onUnpublishShare, onActiveActionChange, renderJobBadges, draggableSucceeded = false }: GalleryGridProps) {
  const { t } = useI18n()
  const [page, setPage] = useState(1)
  const [bulkMode, setBulkMode] = useState(false)
  const [bulkSelectedIds, setBulkSelectedIds] = useState<number[]>([])
  const pageSize = 48
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const galleryLimit = galleryQuota?.retained_limit ?? 10
  const galleryUsed = galleryQuota?.retained_count ?? ordered.filter((job) => job.status === 'succeeded' && job.outputs.length > 0).length
  const expandPrice = galleryQuota?.expand_price_credits ?? 60
  const expandSlots = galleryQuota?.expand_slots ?? 10
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)
  const deletableJobsById = useMemo(() => new Map(ordered.filter(isBulkDeletableJob).map((job) => [job.id, job])), [ordered])
  const selectedBulkJobs = useMemo(() => bulkSelectedIds.map((id) => deletableJobsById.get(id)).filter((job): job is GenerationJob => Boolean(job)), [bulkSelectedIds, deletableJobsById])
  const visibleDeletableJobs = visible.filter(isBulkDeletableJob)
  const allVisibleSelected = visibleDeletableJobs.length > 0 && visibleDeletableJobs.every((job) => bulkSelectedIds.includes(job.id))
  const hasBulkActions = Boolean(onDeleteJobs)

  useEffect(() => {
    setBulkSelectedIds((current) => current.filter((id) => deletableJobsById.has(id)))
  }, [deletableJobsById])

  function enterBulkMode() {
    setBulkMode(true)
    onActiveActionChange?.(null)
  }

  function exitBulkMode() {
    setBulkMode(false)
    setBulkSelectedIds([])
  }

  function toggleBulkJob(job: GenerationJob, checked?: boolean) {
    if (!isBulkDeletableJob(job)) return
    setBulkSelectedIds((current) => {
      const selected = current.includes(job.id)
      const nextChecked = checked ?? !selected
      if (nextChecked && !selected) return [...current, job.id]
      if (!nextChecked && selected) return current.filter((id) => id !== job.id)
      return current
    })
  }

  function selectVisibleJobs() {
    const ids = visibleDeletableJobs.map((job) => job.id)
    setBulkSelectedIds((current) => Array.from(new Set([...current, ...ids])))
  }

  function clearBulkSelection() {
    setBulkSelectedIds([])
  }

  function deleteSelectedJobs() {
    if (!onDeleteJobs || selectedBulkJobs.length === 0) return
    void onDeleteJobs(selectedBulkJobs)
  }

  const panelAction = <div className="flex flex-wrap items-center gap-2"><Badge variant="info">{t('gallery.itemCount', { count: ordered.length })}</Badge>{showRetentionQuota && <Badge variant={galleryUsed >= galleryLimit ? 'warning' : 'outline'}>{t('gallery.retentionQuota', { used: galleryUsed, limit: galleryLimit })}</Badge>}<Badge variant="outline">{t('gallery.page', { page: safePage, total: totalPages })}</Badge>{bulkMode && <Badge variant="secondary">{t('gallery.bulkSelected', { count: selectedBulkJobs.length })}</Badge>}{showRetentionQuota && onExpandGalleryQuota && <Button type="button" size="sm" variant="outline" onClick={onExpandGalleryQuota}>{t('gallery.expandQuotaButton', { price: expandPrice, slots: expandSlots })}</Button>}{hasBulkActions && !bulkMode && <Button type="button" size="sm" variant="outline" disabled={ordered.length === 0} onClick={enterBulkMode}>{t('gallery.bulkSelect')}</Button>}{hasBulkActions && bulkMode && <><Button type="button" size="sm" variant="outline" disabled={visibleDeletableJobs.length === 0 || allVisibleSelected} onClick={selectVisibleJobs}>{t('gallery.bulkSelectPage')}</Button><Button type="button" size="sm" variant="outline" disabled={selectedBulkJobs.length === 0} onClick={clearBulkSelection}>{t('gallery.bulkClear')}</Button><Button type="button" size="sm" variant="destructive" disabled={selectedBulkJobs.length === 0} onClick={deleteSelectedJobs}><Trash2 />{t('gallery.bulkDelete')}</Button><Button type="button" size="sm" variant="ghost" onClick={exitBulkMode}>{t('gallery.bulkExit')}</Button></>}</div>

  return (
    <PixPanel eyebrow={t('gallery.eyebrow')} title={t('gallery.title')} description={subtitle} action={panelAction}>
      {ordered.length === 0 ? <div className="rounded-lg border border-dashed border-border bg-muted/45 p-8 text-center text-muted-foreground">{t('gallery.empty')}</div> : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {visible.map((job) => <GalleryCard key={job.id} job={job} selected={selectedJobId === job.id} bulkMode={bulkMode} bulkSelected={bulkSelectedIds.includes(job.id)} bulkDisabled={!isBulkDeletableJob(job)} retrying={retryingJobId === job.id} draggable={!bulkMode && draggableSucceeded && job.status === 'succeeded'} onSelect={onSelect} onBulkToggle={toggleBulkJob} onReuseJob={onReuseJob} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} onDeleteJob={onDeleteJob} onSaveToPack={onSaveToPack} onRemoveFromPack={onRemoveFromPack} onSaveSequenceAlignment={onSaveSequenceAlignment} onPublishShare={onPublishShare} onUnpublishShare={onUnpublishShare} onActiveActionChange={onActiveActionChange} renderJobBadges={renderJobBadges} />)}
        </div>
      )}
      {ordered.length > pageSize && <div className="mt-5 flex justify-center gap-2"><Button type="button" variant="outline" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{t('gallery.previous')}</Button><Button type="button" variant="outline" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>{t('gallery.next')}</Button></div>}
    </PixPanel>
  )
}

function isBulkDeletableJob(job: GenerationJob) {
  return !['pending', 'running', 'waiting'].includes(job.status)
}

function GalleryCard({ job, selected, bulkMode, bulkSelected, bulkDisabled, retrying, draggable, onSelect, onBulkToggle, onReuseJob, onCandidatePixelize, onRetryJob, onDeleteJob, onSaveToPack, onRemoveFromPack, onSaveSequenceAlignment, onPublishShare, onUnpublishShare, onActiveActionChange, renderJobBadges }: { job: GenerationJob; selected: boolean; bulkMode: boolean; bulkSelected: boolean; bulkDisabled: boolean; retrying: boolean; draggable: boolean; onSelect: (job: GenerationJob) => void; onBulkToggle: (job: GenerationJob, checked?: boolean) => void; onReuseJob?: (job: GenerationJob) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void>; onDeleteJob?: (job: GenerationJob) => void | Promise<void>; onSaveToPack?: (job: GenerationJob) => void | Promise<void>; onRemoveFromPack?: (job: GenerationJob) => void | Promise<void>; onSaveSequenceAlignment?: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void>; onPublishShare?: (job: GenerationJob) => void | Promise<void>; onUnpublishShare?: (job: GenerationJob) => void | Promise<void>; onActiveActionChange?: (action: SpriteRowAction | null) => void; renderJobBadges?: (job: GenerationJob) => ReactNode }) {
  const { language, t } = useI18n()
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const rowActions = useMemo(() => output ? spriteRowActions(output, t, language) : [], [output, t, language])
  const [selectedActionIndex, setSelectedActionIndex] = useState(0)
  const [selectedSizeRetryCandidateKey, setSelectedSizeRetryCandidateKey] = useState<string | null>(null)
  const safeSelectedActionIndex = rowActions.length > 0 ? Math.min(selectedActionIndex, rowActions.length - 1) : 0
  const selectedAction = rowActions[safeSelectedActionIndex]
  const sizeRetryCandidates = output?.candidates?.filter(isSizeRetryCandidate) ?? []
  const defaultSizeRetryCandidate = sizeRetryCandidates.find((candidate) => candidate.selected) ?? null
  const selectedSizeRetryCandidate = selectedSizeRetryCandidateKey ? sizeRetryCandidates.find((candidate) => candidateKey(candidate) === selectedSizeRetryCandidateKey) ?? null : null
  const displayedSizeRetryCandidate = selectedSizeRetryCandidate ?? defaultSizeRetryCandidate
  const displayedSizeRetryCandidateKey = displayedSizeRetryCandidate ? candidateKey(displayedSizeRetryCandidate) : null
  const downloadOptions = useMemo(() => output ? buildDownloadOptions(job, output, t, rowActions, selectedAction, displayedSizeRetryCandidate) : [], [job, output, t, rowActions, selectedAction, displayedSizeRetryCandidate])
  const alignmentOutput = useMemo(() => output ? actionScopedOutput(output, selectedAction) : undefined, [output, selectedAction])
  const [alignmentOpen, setAlignmentOpen] = useState(false)
  const [savingAlignment, setSavingAlignment] = useState(false)
  const isActive = isActiveJob(job)
  const actionPreviewUrl = selectedAction ? signedFileUrl(selectedAction.gifUrl || selectedAction.sheetUrl || undefined) : null
  const sizeRetryPreviewUrl = displayedSizeRetryCandidate ? signedFileUrl(displayedSizeRetryCandidate.preview_url ?? displayedSizeRetryCandidate.pixelized_url ?? displayedSizeRetryCandidate.url ?? undefined) : null
  const previewUrl = isActive ? null : actionPreviewUrl || sizeRetryPreviewUrl || (output ? signedFileUrl(output.dual_grid_preview_url || output.pixelized_url || output.preview_url || output.source_url || undefined) : signedFileUrl(job.input_image_url))
  const spriteSheetUrl = isActive || selectedAction || displayedSizeRetryCandidate ? null : signedFileUrl(output?.sprite_sheet_url || undefined)
  const spriteFrames = selectedAction || displayedSizeRetryCandidate ? [] : (output?.sprite_frames ?? [])
  const spriteFps = spriteFpsFromJob(job)
  const typeLabel = jobTypeLabel(job.job_type, language)
  const sizeTag = sizeRetryPixelSizeTag(displayedSizeRetryCandidate) ?? jobPixelSizeTag(job, output)
  const displayName = jobDisplayName(job, t)
  const summary = jobDisplaySummary(job, displayName, t)
  const previewLabel = isActive ? jobStatusLabel(job, t) : selectedAction ? selectedAction.label : displayedSizeRetryCandidate ? candidateLabel(displayedSizeRetryCandidate, t) : job.status === 'succeeded' ? 'PIX' : t('gallery.waitingOutput')
  const detailsVisible = selected && !bulkMode
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
      aria-expanded={bulkMode ? undefined : selected}
      aria-selected={bulkMode ? bulkSelected : undefined}
      aria-disabled={bulkMode && bulkDisabled ? true : undefined}
      draggable={draggable}
      onDragStart={startDrag}
      onClick={() => { if (bulkMode) { onBulkToggle(job); return } onSelect(job); onActiveActionChange?.(selectedAction ?? null) }}
      onKeyDown={(event) => {
        if (event.currentTarget !== event.target) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          if (bulkMode) {
            onBulkToggle(job)
            return
          }
          onSelect(job)
          onActiveActionChange?.(selectedAction ?? null)
        }
      }}
      className={`overflow-hidden rounded-lg border bg-card transition-colors hover:border-primary/55 hover:pix-shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-[hsl(var(--pix-dark-card))] ${bulkMode && bulkDisabled ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'} ${isActive ? 'pix-work-card-loading' : ''} ${bulkMode ? (bulkSelected ? 'border-primary bg-primary/5 pix-shadow-raised ring-2 ring-primary/20' : 'border-border dark:border-[hsl(var(--pix-dark-hairline))]') : selected ? 'border-primary pix-shadow-raised ring-2 ring-primary/15' : job.status === 'failed' ? 'border-destructive/40' : 'border-border dark:border-[hsl(var(--pix-dark-hairline))]'}`}
    >
      <SpriteSequencePreview sheetUrl={spriteSheetUrl} frames={spriteFrames} fps={spriteFps} fallbackUrl={previewUrl} loading={isActive} label={previewLabel} className="h-36 min-h-0 rounded-none border-0 border-b sm:h-40 xl:h-36 2xl:h-40" imageClassName="absolute inset-0 h-full max-h-none w-full p-0 bg-contain" trim ><div className="absolute right-2 top-2"><PixStatusBadge status={job.status} /></div>{bulkMode && <div className="absolute left-2 top-2 rounded-lg border border-border bg-card/92 p-1.5 shadow-sm backdrop-blur dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised)/.92)]" onClick={(event) => event.stopPropagation()}><Checkbox checked={bulkSelected} disabled={bulkDisabled} aria-label={t('gallery.bulkToggleWork', { id: job.id })} onCheckedChange={(checked) => onBulkToggle(job, checked === true)} /></div>}</SpriteSequencePreview>
      <div className="grid gap-2.5 p-3">
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline">#{job.id}</Badge>
            <Badge variant="secondary" className="dark:border-[hsl(var(--pix-brand-purple-300)/.24)] dark:bg-[hsl(var(--pix-brand-purple-800)/.42)] dark:text-[hsl(var(--pix-brand-purple-300))]">{typeLabel}</Badge>
            {renderJobBadges?.(job)}
            {job.share?.status === 'active' && <Badge variant="success">{t('share.galleryBadge', { count: job.share.like_count })}</Badge>}
            {job.share?.status === 'hidden' && <Badge variant="outline">{t('share.hiddenBadge')}</Badge>}
            {rowActions.length > 1 && <Badge variant="outline">{t('gallery.actionCount', { count: rowActions.length })}</Badge>}
            {sizeTag && <Badge variant="outline" className={pixelSizeBadgeClass(sizeTag.size)} title={sizeTag.title}>{sizeTag.label}</Badge>}
          </div>
          {rowActions.length > 1 && <div className="flex flex-wrap gap-1.5" aria-label={t('gallery.actionTags')}>
            {rowActions.map((action, index) => <button key={`${job.id}-action-${action.rowIndex}`} type="button" title={action.title} className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${index === safeSelectedActionIndex ? 'border-primary bg-primary text-primary-foreground shadow-sm' : 'border-border bg-muted/45 text-muted-foreground hover:border-primary/45 hover:text-foreground dark:border-[hsl(var(--pix-dark-hairline))]'}`} onClick={(event) => { event.stopPropagation(); setSelectedActionIndex(index); if (detailsVisible) onActiveActionChange?.(action) }}>{action.label}</button>)}
          </div>}
          <div>
            <h3 className="line-clamp-2 text-sm font-semibold leading-snug">{displayName}</h3>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{summary}</p>
          </div>
        </div>
        {detailsVisible && <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{t('common.points', { count: job.price_credits })}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge>{job.batch_name && <Badge variant="outline">{job.batch_name}</Badge>}<QuickParameterBadges job={job} output={output} /></div>}
        {detailsVisible && job.status === 'failed' && <JobErrorSummary error={job.error_message} compact />}
        {detailsVisible && output && <CandidateMiniGrid job={job} output={output} displayedSizeRetryCandidateKey={displayedSizeRetryCandidateKey} onSizeRetrySelect={(candidate) => setSelectedSizeRetryCandidateKey(candidateKey(candidate))} onCandidatePixelize={onCandidatePixelize} />}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={detailsVisible ? 'default' : 'outline'} onClick={(event) => { event.stopPropagation(); onSelect(job) }}>{detailsVisible ? t('gallery.expanded') : t('gallery.details')}</Button>
          {onReuseJob && <Button size="sm" variant="outline" title={t('gallery.reuseTitle')} onClick={(event) => { event.stopPropagation(); onReuseJob(job) }}><CopyPlus />{t('gallery.reuse')}</Button>}
          {output && <JobParameterSnapshotDialog job={job} output={output} />}
          {!output && <JobParameterSnapshotDialog job={job} />}
          {job.status === 'succeeded' && output && onPublishShare && job.share?.status !== 'active' && <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); void onPublishShare(job) }}><Share2 />{t('share.publishButton')}</Button>}
          {job.status === 'succeeded' && output && onUnpublishShare && job.share?.status === 'active' && <Button size="sm" variant="outline" title={t('share.unpublishTitle')} onClick={(event) => { event.stopPropagation(); void onUnpublishShare(job) }}><Share2 />{t('share.publishedButton', { count: job.share.like_count })}</Button>}
          {job.status === 'succeeded' && output && alignmentOutput && alignmentOutput.sprite_frames.length > 0 && onSaveSequenceAlignment && <Dialog open={alignmentOpen} onOpenChange={setAlignmentOpen}>
            <Button size="sm" variant="outline" title={selectedAction ? t('gallery.alignActionTitle', { action: selectedAction.label }) : t('gallery.alignFrames')} onClick={(event) => { event.stopPropagation(); setAlignmentOpen(true) }}><Crosshair />{t('gallery.alignFrames')}</Button>
            <DialogPortal>
              <DialogOverlay />
              <DialogPrimitive.Content
                onClick={(event) => event.stopPropagation()}
                onCloseAutoFocus={(event) => event.preventDefault()}
                className="fixed z-50 flex flex-col overflow-hidden rounded-lg border border-border bg-card p-0 pix-shadow-overlay focus:outline-none dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))]"
                style={{
                  height: 'min(900px, calc(100dvh - 32px))',
                  left: '50%',
                  maxHeight: 'calc(100dvh - 32px)',
                  maxWidth: 'none',
                  position: 'fixed',
                  top: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: 'min(1180px, calc(100vw - 32px))',
                }}
              >
                <div className="shrink-0 border-b border-border px-6 py-5 pr-12 dark:border-[hsl(var(--pix-dark-hairline))]">
                  <DialogHeader>
                    <DialogTitle>{selectedAction ? t('alignment.titleWithAction', { action: selectedAction.label }) : t('alignment.title')}</DialogTitle>
                    <DialogDescription>{selectedAction ? t('alignment.descriptionWithAction', { action: selectedAction.label, count: alignmentOutput.sprite_frames.length }) : t('alignment.description')}</DialogDescription>
                  </DialogHeader>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                  <Suspense fallback={<div className="grid min-h-[240px] place-items-center text-sm text-muted-foreground">···</div>}>
                    <SpriteSequenceAlignmentEditor job={job} output={alignmentOutput} saving={savingAlignment} onSave={saveAlignment} />
                  </Suspense>
                </div>
                <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring">
                  <X className="h-4 w-4" />
                  <span className="sr-only">{t('common.close')}</span>
                </DialogPrimitive.Close>
              </DialogPrimitive.Content>
            </DialogPortal>
          </Dialog>}
          {job.status === 'succeeded' && onSaveToPack && <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); void onSaveToPack(job) }}><PackagePlus />{t('packs.saveWork')}</Button>}
          {onRemoveFromPack && <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); void onRemoveFromPack(job) }}><X />{t('packs.removeWork')}</Button>}
          {job.status === 'failed' && onRetryJob && <Button size="sm" variant="destructive" disabled={retrying} onClick={(event) => { event.stopPropagation(); void onRetryJob(job) }}><RotateCcw />{retrying ? t('gallery.retrying') : t('gallery.retry')}</Button>}
          {downloadOptions.length > 0 && <DownloadDialog job={job} options={downloadOptions} />}
          {onDeleteJob && !['pending', 'running', 'waiting'].includes(job.status) && <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); void onDeleteJob(job) }}><Trash2 />{t('gallery.delete')}</Button>}
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
    if (sprite?.mode === 'video_bridge') chips.push('视频补间')
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

  async function downloadSelected() {
    setOpen(false)
    for (const option of selectedOptions) {
      try {
        await downloadFile(option.url, option.filename)
      } catch (error) {
        // 关键：打包/鉴权失败时后端返回的是 JSON 错误体，绝不能当作 .zip/.png 落盘，
        // 否则用户拿到的“压缩包”无法解压。校验失败时提示而非保存损坏文件。
        const reason = error instanceof Error ? error.message : String(error)
        window.alert(t('downloads.failed', { reason }))
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); setOpen(true) }}><Download />{t('downloads.image')}</Button>
      <DialogContent onClick={(event) => event.stopPropagation()} className="w-[min(calc(100vw-32px),520px)] max-w-none gap-0 overflow-hidden p-0">
        <DialogHeader className="px-6 pb-4 pt-6 pr-12">
          <DialogTitle>{t('downloads.dialogTitle')}</DialogTitle>
          <DialogDescription>{t('downloads.dialogDescription', { id: job.id })}</DialogDescription>
        </DialogHeader>
        <div className="grid max-h-[min(60dvh,480px)] gap-2 overflow-y-auto px-6 py-2">
          {options.map((option) => (
            <label key={option.id} className="flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-muted/30 p-3 transition hover:bg-muted/55 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
              <Checkbox checked={selectedSet.has(option.id)} onCheckedChange={(checked) => toggleOption(option.id, Boolean(checked))} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 text-sm font-semibold"><FileDown className="h-4 w-4 text-primary" />{option.label}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{option.description}</span>
              </span>
            </label>
          ))}
        </div>
        <DialogFooter className="border-t border-border px-6 py-4 dark:border-[hsl(var(--pix-dark-hairline))]">
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
          <Button type="button" disabled={selectedOptions.length === 0} onClick={downloadSelected}>{t('downloads.selected', { count: selectedOptions.length })}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function isActiveJob(job: GenerationJob) {
  return job.status === 'pending' || job.status === 'running' || job.status === 'waiting'
}

function jobStatusLabel(job: GenerationJob, t: (key: string, options?: Record<string, unknown>) => string) {
  return job.status === 'pending' ? t('jobs.status.pending') : job.status === 'running' ? t('jobs.status.running') : job.status === 'waiting' ? t('jobs.status.waiting') : t('gallery.waitingOutput')
}

function CandidateMiniGrid({ job, output, displayedSizeRetryCandidateKey, onSizeRetrySelect, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; displayedSizeRetryCandidateKey?: string | null; onSizeRetrySelect?: (candidate: ContactSheetCandidate) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { t } = useI18n()
  const candidates = output.candidates ?? []
  if (!candidates.length) return null
  return (
    <div className="grid grid-cols-3 gap-2">
      {candidates.map((candidate) => {
        const sizeRetry = isSizeRetryCandidate(candidate)
        const displayed = sizeRetry && displayedSizeRetryCandidateKey === candidateKey(candidate)
        const highlighted = sizeRetry ? displayed || (!displayedSizeRetryCandidateKey && candidate.selected) : candidate.selected
        return (
          <button
            type="button"
            key={`${candidate.candidate_kind ?? 'candidate'}-${candidate.path}`}
            aria-pressed={sizeRetry ? highlighted : undefined}
            className={`min-h-[44px] rounded-lg border bg-muted/35 p-2 text-xs transition hover:border-primary/45 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))] ${highlighted ? 'border-primary ring-1 ring-primary/30' : 'border-border'}`}
            onClick={(event) => {
              event.stopPropagation()
              if (sizeRetry) {
                onSizeRetrySelect?.(candidate)
                return
              }
              void onCandidatePixelize?.(job, candidate)
            }}
            title={candidateTooltip(candidate, t)}
          >
            <img src={signedFileUrl(candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined)} alt={candidateLabel(candidate, t)} className="mx-auto aspect-square w-full object-contain [image-rendering:pixelated]" />
            <span className="mt-1 block">{candidateLabel(candidate, t)}</span>
            {sizeRetry && <span className="mt-1 flex flex-wrap justify-center gap-1">{candidate.matched && <Badge variant="success">{t('gallery.sizeRetryMatched')}</Badge>}{candidate.selected && <Badge variant="outline">{t('gallery.delivered')}</Badge>}{displayed && !candidate.selected && <Badge variant="outline">{t('gallery.displaying')}</Badge>}</span>}
          </button>
        )
      })}
    </div>
  )
}

function isSizeRetryCandidate(candidate: ContactSheetCandidate) {
  return candidate.candidate_kind === 'size_retry_attempt'
}

function candidateKey(candidate: ContactSheetCandidate) {
  return `${candidate.candidate_kind ?? 'candidate'}-${candidate.path || candidate.pixelized_path || candidate.preview_path || candidate.index}`
}

function candidateLabel(candidate: ContactSheetCandidate, t: (key: string, options?: Record<string, unknown>) => string) {
  if (isSizeRetryCandidate(candidate)) {
    const index = candidate.attempt ?? candidate.index
    const size = formatCandidateSize(candidate.final_size)
    return size ? t('gallery.sizeRetryAttemptWithSize', { index, size }) : t('gallery.sizeRetryAttempt', { index })
  }
  return candidate.rank ? `#${candidate.rank}` : t('gallery.candidate', { index: candidate.index })
}

function candidateTooltip(candidate: ContactSheetCandidate, t: (key: string, options?: Record<string, unknown>) => string) {
  if (candidate.reason) return candidate.reason
  if (isSizeRetryCandidate(candidate)) {
    const target = formatCandidateSize(candidate.target_size)
    const finalSize = formatCandidateSize(candidate.final_size)
    if (target && finalSize) return t('gallery.sizeRetryTooltip', { target, finalSize })
  }
  return undefined
}

function formatCandidateSize(size?: [number, number] | null) {
  return size ? `${size[0]}×${size[1]}` : ''
}

export type SpriteRowAction = { rowIndex: number; frameIndices: number[]; label: string; title: string; gifUrl: string | null; sheetUrl: string | null }

function actionScopedOutput(output: JobOutput, action?: SpriteRowAction): JobOutput {
  if (!action) return output
  const indexSet = new Set(action.frameIndices)
  let frames = indexSet.size > 0
    ? output.sprite_frames.filter((frame) => indexSet.has(Number(frame.index)))
    : []
  if (frames.length === 0) {
    frames = output.sprite_frames.filter((frame) => Number(frame.row) === action.rowIndex)
  }
  if (frames.length === 0) return output
  return { ...output, sprite_frames: frames.sort((a, b) => Number(a.index) - Number(b.index)) }
}

function spriteRowActions(output: JobOutput, t: (key: string, options?: Record<string, unknown>) => string, language: string): SpriteRowAction[] {
  const rows = Array.isArray(output.sprite_rows_outputs) ? output.sprite_rows_outputs : []
  return rows.flatMap((row, index) => {
    const hasPreview = Boolean(row.gif_url || row.sheet_url)
    if (!hasPreview) return []
    const rowIndex = Number.isFinite(Number(row.row_index)) ? Number(row.row_index) : index
    const phase = typeof row.action_phase === 'string' ? row.action_phase.trim() : ''
    return [{
      rowIndex,
      frameIndices: Array.isArray(row.frame_indices) ? row.frame_indices.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0) : [],
      label: actionLabelFromPhase(phase, rowIndex, t, language),
      title: phase || t('gallery.actionFallback', { index: rowIndex + 1 }),
      gifUrl: row.gif_url ?? null,
      sheetUrl: row.sheet_url ?? null,
    }]
  })
}

function actionLabelFromPhase(phase: string, rowIndex: number, t: (key: string, options?: Record<string, unknown>) => string, language: string) {
  const text = phase.toLowerCase()
  const zh = language.toLowerCase().startsWith('zh')
  const direction = /正面|front|forward|facing camera/.test(text) ? (zh ? '正面' : 'Front')
    : /背面|背部|back|away/.test(text) ? (zh ? '背面' : 'Back')
      : /右侧|向右|right/.test(text) ? (zh ? '右侧' : 'Right')
        : /左侧|向左|left/.test(text) ? (zh ? '左侧' : 'Left')
          : ''
  const action = /拔剑|draw/.test(text) ? (zh ? '拔剑' : 'Draw')
    : /攻击|挥砍|slash|attack|sword/.test(text) ? (zh ? '攻击' : 'Attack')
      : /待机|idle|stand/.test(text) ? (zh ? '待机' : 'Idle')
        : /行走|走|walk/.test(text) ? (zh ? '行走' : 'Walk')
          : ''
  const label = [direction, action].filter(Boolean).join(zh ? '' : ' ')
  if (label) return label
  const cleaned = phase.replace(/^row\s*\d+\s*[:：-]?\s*/i, '').replace(/\s+/g, ' ').trim()
  if (cleaned) return clampText(cleaned, 12)
  return t('gallery.actionFallback', { index: rowIndex + 1 })
}

function outputWithSizeRetryCandidate(output: JobOutput, candidate: ContactSheetCandidate): JobOutput {
  const pixelizedUrl = candidate.pixelized_url ?? candidate.url ?? output.pixelized_url
  const pixelizedPath = candidate.pixelized_path || candidate.path || output.pixelized_path
  return {
    ...output,
    source_path: candidate.source_path || output.source_path,
    source_url: candidate.source_url ?? output.source_url,
    pixelized_path: pixelizedPath,
    pixelized_url: pixelizedUrl,
    pixelized_size: candidate.final_size ?? output.pixelized_size,
    preview_path: candidate.preview_path ?? output.preview_path,
    preview_url: candidate.preview_url ?? pixelizedUrl ?? output.preview_url,
  }
}

function buildDownloadOptions(job: GenerationJob, output: JobOutput, t: (key: string, options?: Record<string, unknown>) => string, rowActions: SpriteRowAction[], selectedAction: SpriteRowAction | undefined, displayedSizeRetryCandidate?: ContactSheetCandidate | null): DownloadOption[] {
  const downloadOutput = displayedSizeRetryCandidate ? outputWithSizeRetryCandidate(output, displayedSizeRetryCandidate) : output
  const isSpriteOutput = job.job_type === 'sprite_sheet' || downloadOutput.sprite_frames.length > 0 || Boolean(downloadOutput.sprite_sheet_url || downloadOutput.sprite_mosaic_url || downloadOutput.sequence_json_url)
  const isDualGridOutput = Boolean(downloadOutput.dual_grid_atlas_url || downloadOutput.dual_grid_preview_url)
  const specs: Array<{ id: DownloadKind; label: string; description: string; path?: string | null; url?: string | null; fallback: string }> = isSpriteOutput ? [
    { id: 'sprite_gif', label: t('downloads.spriteGif'), description: t('downloads.spriteGifDescription'), path: downloadOutput.sprite_gif_path, url: downloadOutput.sprite_gif_url, fallback: 'sprite.gif' },
    { id: 'sprite_sheet', label: t('downloads.spriteSheet'), description: t('downloads.spriteSheetDescription'), path: downloadOutput.sprite_sheet_path || downloadOutput.pixelized_path, url: downloadOutput.sprite_sheet_url || downloadOutput.pixelized_url, fallback: 'sprite-sheet.png' },
    { id: 'sprite_mosaic', label: t('downloads.spriteMosaic'), description: t('downloads.spriteMosaicDescription'), path: downloadOutput.sprite_mosaic_path || downloadOutput.source_path, url: downloadOutput.sprite_mosaic_url || downloadOutput.source_url, fallback: 'sprite-mosaic.png' },
    { id: 'sequence_json', label: t('downloads.sequenceJson'), description: t('downloads.sequenceJsonDescription'), path: downloadOutput.sequence_json_path, url: downloadOutput.sequence_json_url, fallback: 'sequence.json' },
  ] : isDualGridOutput ? [
    { id: 'dual_grid_atlas', label: t('downloads.dualGridAtlas'), description: t('downloads.dualGridAtlasDescription'), path: downloadOutput.dual_grid_atlas_path || downloadOutput.pixelized_path, url: downloadOutput.dual_grid_atlas_url || downloadOutput.pixelized_url, fallback: 'dual_grid_atlas.png' },
    { id: 'dual_grid_preview', label: t('downloads.dualGridPreview'), description: t('downloads.dualGridPreviewDescription'), path: downloadOutput.dual_grid_preview_path || downloadOutput.preview_path, url: downloadOutput.dual_grid_preview_url || downloadOutput.preview_url, fallback: 'dual_grid_preview.png' },
    { id: 'source', label: t('downloads.source'), description: t('downloads.sourceDescription'), path: downloadOutput.source_path, url: downloadOutput.source_url, fallback: '01_source.png' },
  ] : [
    { id: 'source', label: t('downloads.source'), description: t('downloads.sourceDescription'), path: downloadOutput.source_path, url: downloadOutput.source_url, fallback: '01_source.png' },
    { id: 'pixelized', label: t('downloads.pixelized'), description: t('downloads.pixelizedDescription'), path: downloadOutput.pixelized_path, url: downloadOutput.pixelized_url, fallback: '03_pixelized.png' },
    { id: 'contact_sheet', label: t('downloads.contactSheet'), description: t('downloads.contactSheetDescription'), path: downloadOutput.contact_sheet_path, url: downloadOutput.contact_sheet_url, fallback: 'contact-sheet.png' },
  ]
  const seen = new Set<string>()
  const options = specs.flatMap((spec) => {
    const url = signedFileUrl(spec.url)
    if (!url) return []
    const dedupeKey = spec.path || spec.url || url
    if (seen.has(dedupeKey)) return []
    seen.add(dedupeKey)
    return [{ id: spec.id, label: spec.label, description: spec.description, path: spec.path || '', url, filename: downloadFileName(job, spec.path || spec.fallback) }]
  })
  // 多动作序列帧：追加「当前动作图」和「所有动作打包」。
  if (rowActions.length > 1) {
    const prefix = jobFileNamePrefix(job)
    const selectedUrl = signedFileUrl(selectedAction?.sheetUrl ?? undefined)
    if (selectedAction && selectedUrl) {
      const nn = String(selectedAction.rowIndex + 1).padStart(2, '0')
      const phase = safeFileNamePart(selectedAction.title)
      options.push({
        id: 'sprite_action_current',
        label: t('downloads.currentAction', { action: selectedAction.label }),
        description: t('downloads.currentActionDescription'),
        path: '',
        url: selectedUrl,
        filename: phase ? `${prefix}_action${nn}_${phase}.png` : `${prefix}_action${nn}.png`,
      })
    }
    options.push({
      id: 'sprite_actions_zip',
      label: t('downloads.allActions'),
      description: t('downloads.allActionsDescription'),
      path: '',
      url: spriteActionsZipUrl(job.id),
      filename: `${prefix}_sprite_actions.zip`,
    })
  }
  return options
}

async function downloadFile(url: string, filename: string) {
  // token 已包含在 url 查询串里（signedFileUrl / spriteActionsZipUrl），无需额外 header。
  let response: Response
  try {
    response = await fetch(url)
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : '网络错误')
  }
  if (!response.ok) {
    // 读取后端错误体（通常是 {"detail": "..."}），抛出明确原因，避免把它当成文件保存。
    let detail = `HTTP ${response.status}`
    try {
      const text = await response.text()
      const parsed = JSON.parse(text)
      if (parsed && typeof parsed.detail === 'string') detail = parsed.detail
      else if (text.trim()) detail = text.slice(0, 200)
    } catch {
      /* 非 JSON 错误体，沿用状态码 */
    }
    throw new Error(detail)
  }
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
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

function sizeRetryPixelSizeTag(candidate?: ContactSheetCandidate | null): { size: [number, number]; label: string; title: string } | null {
  const size = asNumberPair(candidate?.final_size)
  if (!size) return null
  const [width, height] = size
  return {
    size,
    label: width === height ? `${width}x` : `${width}×${height}`,
    title: `当前显示尺寸重试尝试：${width}×${height}`,
  }
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
