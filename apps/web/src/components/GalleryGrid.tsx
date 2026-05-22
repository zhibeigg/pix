import { useMemo, useState } from 'react'
import { Download, RotateCcw } from 'lucide-react'
import { fileName, signedFileUrl } from '../fileUrls'
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

type GalleryGridProps = { jobs: GenerationJob[]; selectedJobId: number | null; subtitle?: string; retryingJobId?: number | null; onSelect: (job: GenerationJob) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void> }

export function GalleryGrid({ jobs, subtitle, selectedJobId, retryingJobId = null, onSelect, onCandidatePixelize, onRetryJob }: GalleryGridProps) {
  const { text } = useI18n()
  const [page, setPage] = useState(1)
  const pageSize = 48
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <PixPanel eyebrow={text('作品库', 'Gallery')} title={text('作品网格', 'Work grid')} description={subtitle} action={<div className="flex flex-wrap gap-2"><Badge variant="info">{text(`${ordered.length} 件`, `${ordered.length} items`)}</Badge><Badge variant="outline">{text('最多 10 张', 'Max 10 works')}</Badge><Badge variant="outline">{text(`第 ${safePage}/${totalPages} 页`, `Page ${safePage}/${totalPages}`)}</Badge></div>}>
      {ordered.length === 0 ? <div className="rounded-lg border border-dashed border-border bg-muted/45 p-8 text-center text-muted-foreground">{text('暂无作品，先创建一个任务。', 'No works yet. Create a job first.')}</div> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((job) => <GalleryCard key={job.id} job={job} selected={selectedJobId === job.id} retrying={retryingJobId === job.id} onSelect={onSelect} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} />)}
        </div>
      )}
      {ordered.length > pageSize && <div className="mt-5 flex justify-center gap-2"><Button type="button" variant="outline" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{text('上一页', 'Previous')}</Button><Button type="button" variant="outline" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>{text('下一页', 'Next')}</Button></div>}
    </PixPanel>
  )
}

function GalleryCard({ job, selected, retrying, onSelect, onCandidatePixelize, onRetryJob }: { job: GenerationJob; selected: boolean; retrying: boolean; onSelect: (job: GenerationJob) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>; onRetryJob?: (job: GenerationJob) => Promise<void> }) {
  const { language, text } = useI18n()
  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const downloadPath = output?.sprite_gif_path || output?.preview_path || output?.pixelized_path || output?.source_path || job.input_image_path || ''
  const downloadUrl = signedFileUrl(output?.sprite_gif_url || output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url || '')
  const previewUrl = downloadUrl
  const typeLabel = jobTypeLabel(job.job_type, language)
  const displayName = jobDisplayName(job, text)
  const summary = jobDisplaySummary(job, displayName, text)
  return (
    <article
      tabIndex={0}
      aria-expanded={selected}
      onClick={() => onSelect(job)}
      onKeyDown={(event) => {
        if (event.currentTarget !== event.target) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect(job)
        }
      }}
      className={`cursor-pointer overflow-hidden rounded-lg border bg-card transition-colors hover:border-primary/55 hover:shadow-[0_4px_12px_rgba(15,15,15,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-[hsl(var(--pix-dark-card))] ${selected ? 'border-primary shadow-[0_4px_12px_rgba(15,15,15,0.08)] ring-2 ring-primary/15' : job.status === 'failed' ? 'border-destructive/40' : 'border-border dark:border-[hsl(var(--pix-dark-hairline))]'}`}
    >
      <PixPreviewFrame url={previewUrl} label={job.status === 'succeeded' ? 'PIX' : text('等待输出', 'Waiting for output')} className="min-h-40 rounded-none border-0 border-b" ><div className="absolute right-3 top-3"><PixStatusBadge status={job.status} /></div></PixPreviewFrame>
      <div className="grid gap-3 p-4">
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline">#{job.id}</Badge>
            <Badge variant="secondary" className="dark:border-[hsl(var(--pix-brand-purple-300)/.24)] dark:bg-[hsl(var(--pix-brand-purple-800)/.42)] dark:text-[hsl(var(--pix-brand-purple-300))]">{typeLabel}</Badge>
          </div>
          <div>
            <h3 className="line-clamp-2 text-base font-semibold leading-snug">{displayName}</h3>
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted-foreground">{summary}</p>
          </div>
        </div>
        {selected && <div className="flex flex-wrap gap-1.5"><Badge variant="outline">{text(`${job.price_credits} 点`, `${job.price_credits} credits`)}</Badge><Badge variant="outline">{formatDateTime(job.created_at)}</Badge>{job.batch_name && <Badge variant="outline">{job.batch_name}</Badge>}</div>}
        {selected && output && <CandidateMiniGrid job={job} output={output} onCandidatePixelize={onCandidatePixelize} />}
        <div className="flex flex-wrap gap-2"><Button size="sm" variant={selected ? 'default' : 'outline'} onClick={(event) => { event.stopPropagation(); onSelect(job) }}>{selected ? text('已展开', 'Expanded') : text('详情', 'Details')}</Button>{job.status === 'failed' && onRetryJob && <Button size="sm" variant="destructive" disabled={retrying} onClick={(event) => { event.stopPropagation(); void onRetryJob(job) }}><RotateCcw />{retrying ? text('重试中…', 'Retrying…') : text('重试', 'Retry')}</Button>}{downloadUrl && <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); downloadImage(downloadUrl, downloadFileName(job, downloadPath)) }}><Download />{text('下载图片', 'Download image')}</Button>}</div>
      </div>
    </article>
  )
}

function CandidateMiniGrid({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const { text } = useI18n()
  if (!output.candidates?.length) return null
  return <div className="grid grid-cols-3 gap-2">{output.candidates.slice(0, 9).map((candidate) => <button type="button" key={candidate.path} className="rounded-lg border border-border bg-muted/35 p-1.5 text-xs dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]" onClick={(event) => { event.stopPropagation(); void onCandidatePixelize?.(job, candidate) }} title={candidate.reason ?? undefined}><img src={signedFileUrl(candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined)} alt={text(`候选 ${candidate.index}`, `Candidate ${candidate.index}`)} className="mx-auto aspect-square w-full object-contain [image-rendering:pixelated]" /><span>{candidate.rank ? `#${candidate.rank}` : text(`候选${candidate.index}`, `Candidate ${candidate.index}`)}</span></button>)}</div>
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
  const raw = fileName(path || `pix-job-${job.id}.png`)
  const safe = raw.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_')
  return safe || `pix-job-${job.id}.png`
}

function jobDisplayName(job: GenerationJob, text: (zh: string, en: string) => string) {
  const asset = asRecord(job.params_json?.asset)
  const assetName = typeof asset?.name === 'string' ? asset.name.trim() : ''
  if (assetName) return clampText(assetName, 42)
  const prompt = (job.prompt ?? '').replace(/\s+/g, ' ').trim()
  if (prompt) return clampText(prompt, 42)
  if (job.input_image_path) return clampText(fileName(job.input_image_path), 42)
  return text(`任务 #${job.id}`, `Job #${job.id}`)
}

function jobDisplaySummary(job: GenerationJob, displayName: string, text: (zh: string, en: string) => string) {
  const asset = asRecord(job.params_json?.asset)
  const extraPrompt = typeof asset?.extra_prompt === 'string' ? asset.extra_prompt.trim() : ''
  if (extraPrompt) return clampText(extraPrompt, 96)
  const summary = jobInputSummary(job, text('无输入摘要', 'No input summary'))
  return summary === displayName ? text('点击卡片展开查看生成结果。', 'Click the card to expand generated results.') : summary
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function clampText(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max)}…` : value
}
