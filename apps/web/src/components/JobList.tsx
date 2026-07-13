import { RefreshCw } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import { jobTypeLabel } from '../labels'
import { jobInputSummary } from '../pixelize'
import type { ContactSheetCandidate, GenerationJob, JobOutput } from '../types'
import { formatDateTime } from '../lib/utils'
import { spriteFpsFromJob, spriteFrameCountFromJob, spriteSheetUrlFromJob } from '../lib/spritePreview'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { PixPanel } from './pix/PixPanel'
import { PixStatusBadge } from './pix/PixStatusBadge'
import { JobErrorSummary } from './JobErrorSummary'
import { SpriteSequencePreview } from './SpriteSequencePreview'

type JobListProps = { jobs: GenerationJob[]; onRefresh: () => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }

export function JobList({ jobs, onRefresh, onCandidatePixelize }: JobListProps) {
  const { t } = useI18n()
  return (
    <PixPanel eyebrow={t('queue.eyebrow')} title={t('queue.title')} action={<Button variant="outline" onClick={onRefresh}><RefreshCw />{t('common.refresh')}</Button>}>
      {jobs.length === 0 ? <EmptyQueueState /> : <div className="grid gap-3">{jobs.map((job) => <JobCard job={job} key={job.id} onCandidatePixelize={onCandidatePixelize} />)}</div>}
    </PixPanel>
  )
}

function EmptyQueueState() {
  const { t } = useI18n()
  return <div className="rounded-lg border border-dashed border-border bg-muted/45 p-5 text-sm text-muted-foreground"><p className="font-bold text-foreground">{t('queue.emptyTitle')}</p><p>{t('queue.emptyDescription')}</p></div>
}

function JobCard({ job, onCandidatePixelize }: { job: GenerationJob; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { language, t } = useI18n()
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const isActive = job.status === 'pending' || job.status === 'running' || job.status === 'waiting'
  const preview = isActive ? null : signedFileUrl(output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url)
  const spriteSheetUrl = isActive ? null : signedFileUrl(spriteSheetUrlFromJob(job, output) || undefined)
  const spriteFrameCount = spriteFrameCountFromJob(job, output)
  const spriteFps = spriteFpsFromJob(job)
  return (
    <article className={`grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-[120px_minmax(0,1fr)] ${isActive ? 'pix-work-card-loading' : ''}`}>
      <SpriteSequencePreview sheetUrl={spriteSheetUrl} frames={output?.sprite_frames ?? []} frameCount={spriteFrameCount} fps={spriteFps} fallbackUrl={preview} loading={isActive} label={job.status === 'pending' ? t('jobs.status.pending') : job.status === 'running' ? t('jobs.status.running') : job.status === 'waiting' ? t('jobs.status.waiting') : job.status} className="min-h-28" />
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">#{job.id} · {jobTypeLabel(job.job_type, language)}</h3><p className="mt-1 text-sm text-muted-foreground">{jobInputSummary(job, t('gallery.noInputSummary'))}</p></div><PixStatusBadge status={job.status} /></div>
        <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{t('common.points', { count: job.price_credits })}</Badge><Badge variant="outline">{t('queue.reserved', { count: job.reserved_credits })}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge></div>
        {output && <GridQualitySummary output={output} />}
        {output && <CandidateStrip job={job} output={output} onCandidatePixelize={onCandidatePixelize} />}
        {job.status === 'failed' && <JobErrorSummary error={job.error_message} compact />}
      </div>
    </article>
  )
}

function CandidateStrip({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { t } = useI18n()
  const candidates = output.candidates ?? []
  if (!candidates.length) return null
  return <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 md:grid-cols-8">{candidates.map((candidate) => <div key={`${candidate.candidate_kind ?? 'candidate'}-${candidate.path}`} className={`rounded-lg border bg-muted/35 p-1.5 text-center ${candidate.selected ? 'border-primary ring-1 ring-primary/30' : 'border-border'}`} title={candidateTooltip(candidate, t)}><img src={signedFileUrl(candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined)} alt={candidateLabel(candidate, t)} className="mx-auto h-14 w-14 object-contain [image-rendering:pixelated]" /><p className="mt-1 text-[11px] text-muted-foreground">{candidateLabel(candidate, t)}</p>{candidate.candidate_kind === 'size_retry_attempt' && <div className="mt-1 flex flex-wrap justify-center gap-1">{candidate.matched && <Badge variant="success">{t('queue.sizeRetryMatched')}</Badge>}{candidate.selected && <Badge variant="outline">{t('queue.delivered')}</Badge>}</div>}{onCandidatePixelize && <Button size="sm" variant="ghost" className="mt-1 h-6 text-[11px]" onClick={() => onCandidatePixelize(job, candidate)}>{candidate.candidate_kind === 'size_retry_attempt' ? t('queue.chooseCandidate') : t('queue.retune')}</Button>}</div>)}</div>
}

function candidateLabel(candidate: ContactSheetCandidate, t: (key: string, options?: Record<string, unknown>) => string) {
  if (candidate.candidate_kind === 'size_retry_attempt') {
    const index = candidate.attempt ?? candidate.index
    const size = formatCandidateSize(candidate.final_size)
    return size ? t('queue.sizeRetryAttemptWithSize', { index, size }) : t('queue.sizeRetryAttempt', { index })
  }
  return candidate.rank ? `#${candidate.rank}` : t('queue.candidate', { index: candidate.index })
}

function candidateTooltip(candidate: ContactSheetCandidate, t: (key: string, options?: Record<string, unknown>) => string) {
  if (candidate.reason) return candidate.reason
  if (candidate.candidate_kind === 'size_retry_attempt') {
    const target = formatCandidateSize(candidate.target_size)
    const finalSize = formatCandidateSize(candidate.final_size)
    if (target && finalSize) return t('queue.sizeRetryTooltip', { target, finalSize })
  }
  return undefined
}

function formatCandidateSize(size?: [number, number] | null) {
  return size ? `${size[0]}×${size[1]}` : ''
}

function GridQualitySummary({ output }: { output: JobOutput }) {
  const { t } = useI18n()
  const report = output.grid_readability
  if (!report) return null
  return <div className="flex flex-wrap gap-1.5"><Badge variant={report.ok ? 'success' : 'warning'}>{report.ok ? t('queue.readabilityPassed') : t('queue.needsReview')}</Badge><Badge variant="outline">{t('queue.colors', { count: report.color_count })}</Badge><Badge variant="outline">{t('queue.subject', { percent: Math.round(report.bbox_coverage * 100) })}</Badge></div>
}
