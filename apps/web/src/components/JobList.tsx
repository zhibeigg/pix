import { RefreshCw } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import { jobTypeLabel } from '../labels'
import { jobInputSummary } from '../pixelize'
import type { ContactSheetCandidate, GenerationJob, JobOutput } from '../types'
import { formatDateTime } from '../lib/utils'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixStatusBadge } from './pix/PixStatusBadge'

type JobListProps = { jobs: GenerationJob[]; onRefresh: () => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }

export function JobList({ jobs, onRefresh, onCandidatePixelize }: JobListProps) {
  const { text } = useI18n()
  return (
    <PixPanel eyebrow={text('生产队列', 'Production queue')} title={text('正在生产', 'In production')} action={<Button variant="outline" onClick={onRefresh}><RefreshCw />{text('刷新', 'Refresh')}</Button>}>
      {jobs.length === 0 ? <EmptyQueueState /> : <div className="grid gap-3">{jobs.map((job) => <JobCard job={job} key={job.id} onCandidatePixelize={onCandidatePixelize} />)}</div>}
    </PixPanel>
  )
}

function EmptyQueueState() {
  const { text } = useI18n()
  return <div className="rounded-lg border border-dashed border-border bg-muted/45 p-5 text-sm text-muted-foreground"><p className="font-bold text-foreground">{text('炉火正安静', 'The forge is quiet')}</p><p>{text('暂无生产中任务，可以开一组新素材。', 'No active jobs yet. Start a new asset batch.')}</p></div>
}

function JobCard({ job, onCandidatePixelize }: { job: GenerationJob; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { language, text } = useI18n()
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const preview = signedFileUrl(output?.sprite_gif_url || output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url)
  return (
    <article className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-[120px_minmax(0,1fr)]">
      <PixPreviewFrame url={preview} label={job.status} className="min-h-28" />
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">#{job.id} · {jobTypeLabel(job.job_type, language)}</h3><p className="mt-1 text-sm text-muted-foreground">{jobInputSummary(job)}</p></div><PixStatusBadge status={job.status} /></div>
        <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{text(`${job.price_credits} 点`, `${job.price_credits} credits`)}</Badge><Badge variant="outline">{text(`冻结 ${job.reserved_credits}`, `Reserved ${job.reserved_credits}`)}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge></div>
        {output && <GridQualitySummary output={output} />}
        {output && <CandidateStrip job={job} output={output} onCandidatePixelize={onCandidatePixelize} />}
        {job.error_message && <pre className="max-h-36 overflow-auto rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">{job.error_message.slice(0, 600)}</pre>}
      </div>
    </article>
  )
}

function CandidateStrip({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { text } = useI18n()
  if (!output.candidates?.length) return null
  return <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 md:grid-cols-8">{output.candidates.slice(0, 12).map((candidate) => <div key={candidate.path} className="rounded-lg border border-border bg-muted/35 p-1.5 text-center" title={candidate.reason ?? undefined}><img src={signedFileUrl(candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined)} alt={text(`候选 ${candidate.index}`, `Candidate ${candidate.index}`)} className="mx-auto h-14 w-14 object-contain [image-rendering:pixelated]" /><p className="mt-1 text-[11px] text-muted-foreground">{candidate.rank ? `#${candidate.rank}` : text(`候选${candidate.index}`, `Candidate ${candidate.index}`)}</p>{onCandidatePixelize && <Button size="sm" variant="ghost" className="mt-1 h-6 text-[11px]" onClick={() => onCandidatePixelize(job, candidate)}>{text('重调', 'Retune')}</Button>}</div>)}</div>
}

function GridQualitySummary({ output }: { output: JobOutput }) {
  const { text } = useI18n()
  const report = output.grid_readability
  if (!report) return null
  return <div className="flex flex-wrap gap-1.5"><Badge variant={report.ok ? 'success' : 'warning'}>{report.ok ? text('可读性通过', 'Readability passed') : text('需检查', 'Needs review')}</Badge><Badge variant="outline">{text(`${report.color_count} 色`, `${report.color_count} colors`)}</Badge><Badge variant="outline">{text(`主体 ${Math.round(report.bbox_coverage * 100)}%`, `Subject ${Math.round(report.bbox_coverage * 100)}%`)}</Badge></div>
}
