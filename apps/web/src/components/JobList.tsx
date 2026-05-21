import { RefreshCw } from 'lucide-react'
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
  return (
    <PixPanel eyebrow="生产队列" title="正在生产" action={<Button variant="outline" onClick={onRefresh}><RefreshCw />刷新</Button>}>
      {jobs.length === 0 ? <EmptyQueueState /> : <div className="grid gap-3">{jobs.map((job) => <JobCard job={job} key={job.id} onCandidatePixelize={onCandidatePixelize} />)}</div>}
    </PixPanel>
  )
}

function EmptyQueueState() {
  return <div className="rounded-lg border border-dashed border-border bg-muted/45 p-5 text-sm text-muted-foreground"><p className="font-bold text-foreground">炉火正安静</p><p>暂无生产中任务，可以开一组新素材。</p></div>
}

function JobCard({ job, onCandidatePixelize }: { job: GenerationJob; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const preview = output?.sprite_gif_url || output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url
  return (
    <article className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-[120px_minmax(0,1fr)]">
      <PixPreviewFrame url={preview} label={job.status} className="min-h-28" />
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">#{job.id} · {jobTypeLabel(job.job_type)}</h3><p className="mt-1 text-sm text-muted-foreground">{jobInputSummary(job)}</p></div><PixStatusBadge status={job.status} /></div>
        <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{job.price_credits} 点</Badge><Badge variant="outline">冻结 {job.reserved_credits}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge></div>
        {output && <GridQualitySummary output={output} />}
        {output && <CandidateStrip job={job} output={output} onCandidatePixelize={onCandidatePixelize} />}
        {job.error_message && <pre className="max-h-36 overflow-auto rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">{job.error_message.slice(0, 600)}</pre>}
      </div>
    </article>
  )
}

function CandidateStrip({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  if (!output.candidates?.length) return null
  return <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 md:grid-cols-8">{output.candidates.slice(0, 12).map((candidate) => <div key={candidate.path} className="rounded-lg border border-border bg-muted/35 p-1.5 text-center" title={candidate.reason ?? undefined}><img src={candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined} alt={`候选 ${candidate.index}`} className="mx-auto h-14 w-14 object-contain [image-rendering:pixelated]" /><p className="mt-1 text-[11px] text-muted-foreground">{candidate.rank ? `#${candidate.rank}` : `候选${candidate.index}`}</p>{onCandidatePixelize && <Button size="sm" variant="ghost" className="mt-1 h-6 text-[11px]" onClick={() => onCandidatePixelize(job, candidate)}>重调</Button>}</div>)}</div>
}

function GridQualitySummary({ output }: { output: JobOutput }) {
  const report = output.grid_readability
  if (!report) return null
  return <div className="flex flex-wrap gap-1.5"><Badge variant={report.ok ? 'success' : 'warning'}>{report.ok ? '可读性通过' : '需检查'}</Badge><Badge variant="outline">{report.color_count} 色</Badge><Badge variant="outline">主体 {Math.round(report.bbox_coverage * 100)}%</Badge></div>
}
