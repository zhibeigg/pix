import { useMemo, useState } from 'react'
import { Copy, RotateCcw } from 'lucide-react'
import { useI18n } from '../i18n'
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
  const { text } = useI18n()
  const [page, setPage] = useState(1)
  const pageSize = 48
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <PixPanel eyebrow={text('作品库', 'Gallery')} title={text('作品网格', 'Work grid')} description={subtitle} action={<div className="flex gap-2"><Badge variant="info">{text(`${ordered.length} 件`, `${ordered.length} items`)}</Badge><Badge variant="outline">{text(`第 ${safePage}/${totalPages} 页`, `Page ${safePage}/${totalPages}`)}</Badge></div>}>
      {ordered.length === 0 ? <div className="rounded-lg border border-dashed border-border bg-muted/45 p-8 text-center text-muted-foreground">{text('暂无作品，先创建一个任务。', 'No works yet. Create a job first.')}</div> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((job) => <GalleryCard key={job.id} job={job} selected={selectedJobId === job.id} retrying={retryingJobId === job.id} onSelect={onSelect} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} />)}
        </div>
      )}
      {ordered.length > pageSize && <div className="mt-5 flex justify-center gap-2"><Button type="button" variant="outline" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{text('上一页', 'Previous')}</Button><Button type="button" variant="outline" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>{text('下一页', 'Next')}</Button></div>}
    </PixPanel>
  )
}

function GalleryCard({ job, selected, retrying, onSelect, onCopyPath, onCandidatePixelize, onRetryJob }: { job: GenerationJob; selected: boolean; retrying: boolean; onSelect: (job: GenerationJob) => void; onCopyPath: (path: string) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void> }) {
  const { language, text } = useI18n()
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const mainPath = output?.sprite_sheet_path || output?.pixelized_path || output?.source_path || job.input_image_path || ''
  const previewUrl = output?.sprite_gif_url || output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url || ''
  return (
    <article className={`overflow-hidden rounded-lg border bg-card transition-colors hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] ${selected ? 'border-primary shadow-[0_4px_12px_rgba(15,15,15,0.08)] ring-2 ring-primary/15' : job.status === 'failed' ? 'border-destructive/40' : 'border-border'}`}>
      <PixPreviewFrame url={previewUrl} label={job.status === 'succeeded' ? 'PIX' : text('等待输出', 'Waiting for output')} className="min-h-40 rounded-none border-0 border-b" ><div className="absolute right-3 top-3"><PixStatusBadge status={job.status} /></div></PixPreviewFrame>
      <div className="grid gap-3 p-4">
        <div><h3 className="truncate font-semibold">#{job.id} · {jobTypeLabel(job.job_type, language)}</h3><p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{jobInputSummary(job)}</p></div>
        {selected && <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{text(`${job.price_credits} 点`, `${job.price_credits} credits`)}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge>{job.batch_name && <Badge variant="outline">{job.batch_name}</Badge>}</div>}
        {selected && output && <CandidateMiniGrid job={job} output={output} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} />}
        <div className="flex flex-wrap gap-2"><Button size="sm" variant={selected ? 'default' : 'outline'} onClick={() => onSelect(job)}>{selected ? text('已展开', 'Expanded') : text('详情', 'Details')}</Button>{job.status === 'failed' && onRetryJob && <Button size="sm" variant="destructive" disabled={retrying} onClick={() => onRetryJob(job)}><RotateCcw />{retrying ? text('重试中…', 'Retrying…') : text('重试', 'Retry')}</Button>}{mainPath && <Button size="sm" variant="ghost" onClick={() => onCopyPath(mainPath)}><Copy />{text('复制路径', 'Copy path')}</Button>}</div>
      </div>
    </article>
  )
}

function CandidateMiniGrid({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCopyPath: (path: string) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { text } = useI18n()
  if (!output.candidates?.length) return null
  return <div className="grid grid-cols-3 gap-2">{output.candidates.slice(0, 9).map((candidate) => <button type="button" key={candidate.path} className="rounded-lg border border-border bg-muted/35 p-1.5 text-xs" onClick={() => onCandidatePixelize?.(job, candidate)} title={candidate.reason ?? undefined}><img src={candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined} alt={text(`候选 ${candidate.index}`, `Candidate ${candidate.index}`)} className="mx-auto aspect-square w-full object-contain [image-rendering:pixelated]" /><span>{candidate.rank ? `#${candidate.rank}` : text(`候选${candidate.index}`, `Candidate ${candidate.index}`)}</span></button>)}</div>
}
