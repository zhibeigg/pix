import { useMemo, useState } from 'react'
import { Copy, RotateCcw } from 'lucide-react'
import type { ContactSheetCandidate, GenerationJob, JobOutput } from '../types'
import { jobInputSummary } from '../pixelize'
import { jobTypeLabel } from '../labels'
import { formatDateTime } from '../lib/utils'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixStatusBadge } from './pix/PixStatusBadge'

type GalleryGridProps = { jobs: GenerationJob[]; selectedJobId: number | null; subtitle?: string; retryingJobId?: number | null; onSelect: (job: GenerationJob) => void; onCopyPath: (path: string) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void> }

export function GalleryGrid({ jobs, subtitle, selectedJobId, retryingJobId = null, onSelect, onCopyPath, onCandidatePixelize, onRetryJob }: GalleryGridProps) {
  const [page, setPage] = useState(1)
  const pageSize = 48
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <PixPanel eyebrow="作品库" title="作品网格" description={subtitle} action={<div className="flex gap-2"><Badge variant="info">{ordered.length} 件</Badge><Badge variant="outline">第 {safePage}/{totalPages} 页</Badge></div>}>
      {ordered.length === 0 ? <div className="rounded-2xl border border-dashed border-border bg-muted/45 p-8 text-center text-muted-foreground">暂无作品，先创建一个任务。</div> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((job) => <GalleryCard key={job.id} job={job} selected={selectedJobId === job.id} retrying={retryingJobId === job.id} onSelect={onSelect} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} />)}
        </div>
      )}
      {ordered.length > pageSize && <div className="mt-5 flex justify-center gap-2"><Button type="button" variant="outline" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>上一页</Button><Button type="button" variant="outline" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>下一页</Button></div>}
    </PixPanel>
  )
}

function GalleryCard({ job, selected, retrying, onSelect, onCopyPath, onCandidatePixelize, onRetryJob }: { job: GenerationJob; selected: boolean; retrying: boolean; onSelect: (job: GenerationJob) => void; onCopyPath: (path: string) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void> }) {
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const mainPath = output?.sprite_sheet_path || output?.pixelized_path || output?.source_path || job.input_image_path || ''
  const previewUrl = output?.sprite_gif_url || output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url || ''
  return (
    <article className={`overflow-hidden rounded-2xl border bg-card transition-all hover:-translate-y-1 hover:shadow-xl ${selected ? 'border-primary shadow-lg ring-2 ring-primary/15' : job.status === 'failed' ? 'border-destructive/40' : 'border-border'}`}>
      <PixPreviewFrame url={previewUrl} label={job.status === 'succeeded' ? 'PIX' : '等待输出'} className="min-h-40 rounded-none border-0 border-b" ><div className="absolute right-3 top-3"><PixStatusBadge status={job.status} /></div></PixPreviewFrame>
      <div className="grid gap-3 p-4">
        <div><h3 className="truncate font-black">#{job.id} · {jobTypeLabel(job.job_type)}</h3><p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{jobInputSummary(job)}</p></div>
        {selected && <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{job.price_credits} 点</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge>{job.batch_name && <Badge variant="outline">{job.batch_name}</Badge>}</div>}
        {selected && output && <CandidateMiniGrid job={job} output={output} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} />}
        <div className="flex flex-wrap gap-2"><Button size="sm" variant={selected ? 'default' : 'outline'} onClick={() => onSelect(job)}>{selected ? '已展开' : '详情'}</Button>{job.status === 'failed' && onRetryJob && <Button size="sm" variant="destructive" disabled={retrying} onClick={() => onRetryJob(job)}><RotateCcw />{retrying ? '重试中…' : '重试'}</Button>}{mainPath && <Button size="sm" variant="ghost" onClick={() => onCopyPath(mainPath)}><Copy />复制路径</Button>}</div>
      </div>
    </article>
  )
}

function CandidateMiniGrid({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCopyPath: (path: string) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  if (!output.candidates?.length) return null
  return <div className="grid grid-cols-3 gap-2">{output.candidates.slice(0, 9).map((candidate) => <button type="button" key={candidate.path} className="rounded-xl border border-border bg-muted/35 p-1.5 text-xs" onClick={() => onCandidatePixelize?.(job, candidate)} title={candidate.reason ?? undefined}><img src={candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined} alt={`候选 ${candidate.index}`} className="mx-auto aspect-square w-full object-contain [image-rendering:pixelated]" /><span>{candidate.rank ? `#${candidate.rank}` : `候选${candidate.index}`}</span></button>)}</div>
}
