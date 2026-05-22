import { FormEvent, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useI18n } from '../i18n'
import { defaultPixelize, summarizePrompt } from '../pixelize'
import type { ContactSheetCandidate, CreditBalance, GenerationJob, JobCreateRequest, PricingRule } from '../types'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Input } from '../components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { Textarea } from '../components/ui/textarea'
import { Alert } from '../components/ui/alert'
import { PixField } from '../components/pix/PixField'
import { PixPanel } from '../components/pix/PixPanel'
import { PixPreviewFrame } from '../components/pix/PixPreviewFrame'
import { PixStatusBadge } from '../components/pix/PixStatusBadge'

type Props = { pricing: PricingRule[]; balance: CreditBalance | null; jobs: GenerationJob[]; loading: boolean; selectedJobId: number | null; onSelectJob: (jobId: number) => void; onCreateJob: (payload: JobCreateRequest) => Promise<void>; onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>; onRefresh: () => void | Promise<void> }
type PreviewOverride = { jobId: number; url: string; label: string }
const imageSizes = ['1024x1024', '1536x1024', '1024x1536', '2048x1024', '1024x2048', 'auto']
const qualityOptions = ['auto', 'low', 'medium', 'high']

export function RawImagePage({ pricing, balance, jobs, loading, selectedJobId, onSelectJob, onCreateJob, onCreateJobs, onRefresh }: Props) {
  const { text } = useI18n()
  const [model, setModel] = useState('gpt-image-2')
  const [imageSize, setImageSize] = useState('1024x1024')
  const [quality, setQuality] = useState('auto')
  const [generationCount, setGenerationCount] = useState(1)
  const [prompt, setPrompt] = useState(() => text('生成一张 1024×1024 方形应用图标风格的奇幻 RPG 治疗药水，深翡翠背景，轮廓清晰，电影感光照。', 'Create a polished 1024x1024 square app icon artwork for a fantasy RPG healing potion, deep emerald background, crisp silhouette, cinematic lighting.'))
  const [previewOverride, setPreviewOverride] = useState<PreviewOverride | null>(null)
  const rawJobs = useMemo(() => jobs.filter(isRawImageJob).sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const selectedJob = rawJobs.find((job) => job.id === selectedJobId) ?? rawJobs[0] ?? null
  const price = pricing.find((item) => item.key === 'text_to_image')?.price_credits ?? 0
  const safeCount = Math.max(1, Math.min(4, Math.trunc(Number.isFinite(generationCount) ? generationCount : 1)))
  const estimatedCredits = price * safeCount
  const insufficientCredits = typeof balance?.available_credits === 'number' && balance.available_credits < estimatedCredits
  const hasPreviewOverride = previewOverride !== null && selectedJob !== null && previewOverride.jobId === selectedJob.id
  const mainImageUrl = hasPreviewOverride ? previewOverride.url : rawSourceUrl(selectedJob)
  const mainImageLabel = hasPreviewOverride ? previewOverride.label : text('原始源图', 'Raw source')
  const thumbs = useMemo(() => buildThumbs(rawJobs, selectedJob?.id ?? null, previewOverride), [previewOverride, rawJobs, selectedJob?.id])
  useEffect(() => setPreviewOverride(null), [selectedJob?.id])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const basePrompt = prompt.trim()
    if (!basePrompt || insufficientCredits) return
    const payloads = Array.from({ length: safeCount }, (_, index) => buildRawPayload({ prompt: variationPrompt(basePrompt, index, safeCount), imageSize, quality, model }))
    if (payloads.length === 1) await onCreateJob(payloads[0])
    else await onCreateJobs(payloads, text(`原始生图 ${new Date().toLocaleString()}`, `Raw images ${new Date().toLocaleString()}`), 'raw_image')
  }

  return (
    <form className="grid gap-5" onSubmit={submit}>
      <PixPanel eyebrow={text('原图炉', 'Raw forge')} title={text('原始生图', 'Raw image generation')} description={text('只做文生原图：调基础参数、提交提示词、在画布里看源图。', 'Generate source images only: tune base parameters, submit a prompt, and review the source on canvas.')} action={<div className="flex flex-wrap gap-2"><Badge variant="outline">{text(`余额 ${balance?.available_credits ?? '—'} 点`, `Balance ${balance?.available_credits ?? '—'} credits`)}</Badge><Badge variant={insufficientCredits ? 'danger' : 'info'}>{text(`预计 ${estimatedCredits} 点`, `Estimated ${estimatedCredits} credits`)}</Badge><Button type="button" variant="outline" onClick={() => void onRefresh()}><RefreshCw />{text('刷新', 'Refresh')}</Button></div>}>
        <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)_148px]">
          <div className="grid content-start gap-4">
            <PixField label={text('提供商', 'Provider')}><Input value="packyapi-image" disabled /></PixField>
            <PixField label={text('模型', 'Model')}><Select value={model} onValueChange={setModel}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="gpt-image-2">gpt-image-2</SelectItem></SelectContent></Select></PixField>
            <PixField label={text('图片尺寸', 'Image size')}><Select value={imageSize} onValueChange={setImageSize}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{imageSizes.map((size) => <SelectItem value={size} key={size}>{size}</SelectItem>)}</SelectContent></Select></PixField>
            <PixField label={text('质量', 'Quality')}><Select value={quality} onValueChange={setQuality}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{qualityOptions.map((item) => <SelectItem value={item} key={item}>{item}</SelectItem>)}</SelectContent></Select></PixField>
            <PixField label={text('生成数量', 'Generation count')} hint={text('1-4 张；多张会作为轻量变体任务提交。', '1-4 images; multiple images submit as lightweight variation jobs.')}><Input type="number" min={1} max={4} value={generationCount} onChange={(event) => setGenerationCount(Number(event.target.value))} /></PixField>
          </div>
          <div className="grid gap-4 rounded-lg bg-[hsl(var(--pix-navy))] p-4 text-white">
            <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-white/55">{text('预览画布', 'Preview deck')}</p><h3 className="text-xl font-semibold">{selectedJob ? `#${selectedJob.id} · ${mainImageLabel}` : text('等待第一张原图', 'Waiting for the first source image')}</h3></div>{selectedJob && <PixStatusBadge status={selectedJob.status} />}</div>
            <PixPreviewFrame url={mainImageUrl} label={selectedJob ? rawStateLabel(selectedJob, text) : text('等待提示词点火', 'Waiting for prompt ignition')} className="min-h-[420px]" />
            <p className="text-sm text-white/60">{selectedJob ? summarizePrompt(selectedJob.prompt, text('无提示词', 'No prompt')) : text('输入提示词后，生成结果会停留在本页。', 'After entering a prompt, generated results stay on this page.')}</p>
          </div>
          <div className="grid content-start gap-2 rounded-lg border border-border bg-card p-3"><p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('最近', 'Recent')}</p>{thumbs.length ? thumbs.slice(0, 8).map((thumb) => <button key={thumb.key} type="button" title={thumb.label} onClick={() => { onSelectJob(thumb.job.id); setPreviewOverride(thumb.candidate ? { jobId: thumb.job.id, url: thumb.url, label: thumb.label } : null) }} className={`overflow-hidden rounded-lg border p-1 ${thumb.selected ? 'border-primary bg-primary/10' : 'border-border bg-muted/30'}`}><img src={thumb.url} alt={thumb.label} className="aspect-square w-full object-cover [image-rendering:pixelated]" /></button>) : <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">{text('暂无缩略图', 'No thumbnails yet')}</div>}</div>
        </div>
      </PixPanel>
      <PixPanel><div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_190px]"><Textarea value={prompt} rows={3} required onChange={(event) => setPrompt(event.target.value)} placeholder={text('描述你要生成的原始图片：主体、风格、构图、颜色、用途。', 'Describe the source image: subject, style, composition, colors, and intended use.')} /><div className="grid content-between gap-3"><Badge variant="outline">{imageSize} · {quality} · {text(`${safeCount} 张`, `${safeCount} images`)}</Badge><Button type="submit" size="lg" disabled={loading || !prompt.trim() || insufficientCredits}>{loading ? text('提交中…', 'Submitting…') : text('生成原图', 'Generate source')}</Button></div></div></PixPanel>
    </form>
  )
}

function buildRawPayload({ prompt, imageSize, quality, model }: { prompt: string; imageSize: string; quality: string; model: string }): JobCreateRequest { return { job_type: 'text_to_image', prompt, input_image_path: null, client_request_id: `raw-image-${crypto.randomUUID()}`, image_size: imageSize, image_quality: quality, image_model: model, skip_vl: true, pixelize: { ...defaultPixelize, output_size: [128, 128], preview_scale: 0, remove_bg: false, auto_crop: false }, grid: { mode: 'off' } } }
function variationPrompt(basePrompt: string, index: number, count: number) { return count <= 1 ? basePrompt : `${basePrompt}\n\nVariation ${index + 1}/${count}: keep the requested subject and style, but use a distinct composition and detail arrangement.` }
function isRawImageJob(job: GenerationJob) { const grid = job.params_json?.grid; const gridMode = typeof grid === 'object' && grid !== null && 'mode' in grid ? (grid as { mode?: unknown }).mode : null; return job.job_type === 'text_to_image' && job.params_json?.skip_vl === true && gridMode === 'off' }
function firstOutput(job: GenerationJob | null | undefined) { return Array.isArray(job?.outputs) ? job.outputs[0] : undefined }
function rawSourceUrl(job: GenerationJob | null | undefined) { return firstOutput(job)?.source_url || null }
function candidateRawUrl(candidate: ContactSheetCandidate) { return candidate.url || candidate.pixelized_url || candidate.preview_url || null }
function buildThumbs(rawJobs: GenerationJob[], selectedJobId: number | null, previewOverride: PreviewOverride | null) { const thumbs: Array<{ key: string; job: GenerationJob; url: string; label: string; selected: boolean; candidate?: ContactSheetCandidate }> = []; for (const job of rawJobs) { const output = firstOutput(job); const candidates = Array.isArray(output?.candidates) ? output.candidates : []; if (job.id === selectedJobId) for (const candidate of candidates) { const url = candidateRawUrl(candidate); if (url) thumbs.push({ key: `candidate-${job.id}-${candidate.path}`, job, url, label: candidate.rank ? `候选 #${candidate.rank}` : `候选 ${candidate.index}`, selected: previewOverride?.jobId === job.id && previewOverride.url === url, candidate }) } const url = rawSourceUrl(job); if (url) thumbs.push({ key: `job-${job.id}`, job, url, label: `任务 #${job.id}`, selected: previewOverride?.jobId !== job.id && job.id === selectedJobId }) } return thumbs }
function rawStateLabel(job: GenerationJob, text: (zh: string, en: string) => string) { if (job.status === 'failed') return job.error_message || text('生成失败', 'Generation failed'); if (job.status === 'running' || job.status === 'pending') return text('炉膛正在出图', 'The forge is generating'); return text('暂未拿到源图链接', 'No source image link yet') }
