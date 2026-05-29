import { FormEvent, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import { defaultPixelize, summarizePrompt } from '../pixelize'
import type { CreditBalance, GenerationJob, JobCreateRequest, PricingRule } from '../types'
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
import { JobErrorSummary, summarizeJobError } from '../components/JobErrorSummary'

type Props = {
  pricing: PricingRule[]
  balance: CreditBalance | null
  jobs: GenerationJob[]
  loading: boolean
  selectedJobId: number | null
  onSelectJob: (jobId: number) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRefresh: () => void | Promise<void>
}

const imageSizes = ['1024x1024', '1536x1024', '1024x1536', '2048x1024', '1024x2048', 'auto']
const qualityOptions = ['auto', 'low', 'medium', 'high']
const RAW_IMAGE_PROMPT_MAX_LENGTH = 3000

export function RawImagePage({ pricing, balance, jobs, loading, selectedJobId, onSelectJob, onCreateJob, onRefresh }: Props) {
  const { text } = useI18n()
  const [model, setModel] = useState('gpt-image-2')
  const [imageSize, setImageSize] = useState('1024x1024')
  const [quality, setQuality] = useState('auto')
  const [prompt, setPrompt] = useState(() => text('生成一张 1024×1024 方形应用图标风格的奇幻 RPG 治疗药水，深翡翠背景，轮廓清晰，电影感光照。', 'Create one polished 1024x1024 square app icon artwork for a fantasy RPG healing potion, deep emerald background, crisp silhouette, cinematic lighting.'))
  const rawJobs = useMemo(() => jobs.filter(isRawImageJob).sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const selectedJob = rawJobs.find((job) => job.id === selectedJobId) ?? rawJobs[0] ?? null
  const price = pricing.find((item) => item.key === 'text_to_image')?.price_credits ?? 0
  const promptTooLong = prompt.length > RAW_IMAGE_PROMPT_MAX_LENGTH
  const insufficientCredits = typeof balance?.available_credits === 'number' && balance.available_credits < price
  const isSelectedActive = selectedJob?.status === 'pending' || selectedJob?.status === 'running'
  const mainImageUrl = isSelectedActive ? null : rawSourceUrl(selectedJob)
  const failedError = selectedJob?.status === 'failed' ? summarizeJobError(selectedJob.error_message, text) : null
  const mainImageLabel = failedError?.title ?? text('原始单图', 'Raw single image')
  const thumbs = useMemo(() => buildThumbs(rawJobs, selectedJob?.id ?? null), [rawJobs, selectedJob?.id])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const basePrompt = prompt.trim()
    if (!basePrompt || insufficientCredits) return
    await onCreateJob(buildRawPayload({ prompt: basePrompt, imageSize, quality, model }))
  }

  return (
    <form className="grid gap-5" onSubmit={submit}>
      <PixPanel
        eyebrow={text('原图炉', 'Raw forge')}
        title={text('原始生图', 'Raw image generation')}
        description={text('一次只出一张原图，不做候选、评分、抠图或像素化后处理。', 'Generate exactly one source image with no candidates, ranking, matting, or pixel post-processing.')}
        action={<div className="flex flex-wrap gap-2"><Badge variant="outline">{text(`余额 ${balance?.available_credits ?? '—'} 点`, `Balance ${balance?.available_credits ?? '—'} credits`)}</Badge><Badge variant={insufficientCredits ? 'danger' : 'info'}>{text(`预计 ${price} 点`, `Estimated ${price} credits`)}</Badge><Button type="button" variant="outline" onClick={() => void onRefresh()}><RefreshCw />{text('刷新', 'Refresh')}</Button></div>}
      >
        <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)_148px]">
          <div className="grid content-start gap-4">
            <PixField label={text('提供商', 'Provider')}><Input value="packyapi-image" disabled /></PixField>
            <PixField label={text('模型', 'Model')}><Select value={model} onValueChange={setModel}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="gpt-image-2">gpt-image-2</SelectItem></SelectContent></Select></PixField>
            <PixField label={text('图片尺寸', 'Image size')}><Select value={imageSize} onValueChange={setImageSize}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{imageSizes.map((size) => <SelectItem value={size} key={size}>{size}</SelectItem>)}</SelectContent></Select></PixField>
            <PixField label={text('质量', 'Quality')}><Select value={quality} onValueChange={setQuality}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{qualityOptions.map((item) => <SelectItem value={item} key={item}>{item}</SelectItem>)}</SelectContent></Select></PixField>
            <Alert variant="info">{text('固定生成 1 张原图；后端会跳过候选图、VL 分析和像素化输出。', 'Always generates 1 source image; the backend skips candidates, vision analysis, and pixelized outputs.')}</Alert>
          </div>

          <div className="grid gap-4 rounded-lg border border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-paper-soft))] p-4 text-[hsl(var(--pix-ink))] shadow-[inset_0_1px_0_rgba(255,255,255,0.68)] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card-raised))] dark:text-white dark:shadow-[0_22px_70px_-46px_rgba(0,0,0,0.95)]">
            <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-primary dark:text-[hsl(var(--pix-brand-purple-300))]">{text('预览画布', 'Preview canvas')}</p><h3 className="text-xl font-semibold">{selectedJob ? `#${selectedJob.id} · ${mainImageLabel}` : text('等待第一张原图', 'Waiting for the first source image')}</h3></div>{selectedJob && <PixStatusBadge status={selectedJob.status} />}</div>
            <PixPreviewFrame url={mainImageUrl} loading={isSelectedActive} label={selectedJob ? rawStateLabel(selectedJob, text) : text('等待提示词点火', 'Waiting for prompt ignition')} className="min-h-[420px] border-[hsl(var(--pix-paper-border))] bg-card dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]" imageClassName="[image-rendering:auto]" />
            {selectedJob?.status === 'failed' && <JobErrorSummary error={selectedJob.error_message} />}
            <p className="text-sm text-muted-foreground dark:text-white/60">{selectedJob ? summarizePrompt(selectedJob.prompt, text('无提示词', 'No prompt')) : text('输入提示词后，生成结果会停留在本页。', 'After entering a prompt, generated results stay on this page.')}</p>
          </div>

          <div className="grid content-start gap-2 rounded-lg border border-border bg-card p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{text('最近', 'Recent')}</p>
            {thumbs.length ? thumbs.slice(0, 8).map((thumb) => <button key={thumb.key} type="button" title={thumb.label} onClick={() => onSelectJob(thumb.job.id)} className={`overflow-hidden rounded-lg border p-1 ${thumb.selected ? 'border-primary bg-primary/10 dark:bg-primary/18' : 'border-border bg-muted/30 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]'}`}><img src={thumb.url} alt={thumb.label} className="aspect-square w-full object-cover" /></button>) : <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">{text('暂无缩略图', 'No thumbnails yet')}</div>}
          </div>
        </div>
      </PixPanel>

      <PixPanel><div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_190px]"><div className="grid gap-2"><Textarea value={prompt} rows={5} required maxLength={RAW_IMAGE_PROMPT_MAX_LENGTH} onChange={(event) => setPrompt(event.target.value)} placeholder={text('描述你要生成的图片：主体、风格、构图、颜色、用途。', 'Describe the image: subject, style, composition, colors, and intended use.')} /><div className="flex justify-end text-xs text-muted-foreground">{prompt.length}/{RAW_IMAGE_PROMPT_MAX_LENGTH}</div></div><div className="grid content-between gap-3"><Badge variant="outline">{imageSize} · {quality} · {text('1 张', '1 image')}</Badge>{promptTooLong && <Badge variant="danger">{text('提示词最多 3000 字', 'Prompt max 3000 characters')}</Badge>}<Button type="submit" size="lg" disabled={loading || !prompt.trim() || promptTooLong || insufficientCredits}>{loading ? text('提交中…', 'Submitting…') : text('生成单图', 'Generate image')}</Button></div></div></PixPanel>
    </form>
  )
}

function buildRawPayload({ prompt, imageSize, quality, model }: { prompt: string; imageSize: string; quality: string; model: string }): JobCreateRequest {
  return {
    job_type: 'text_to_image',
    prompt,
    input_image_path: null,
    client_request_id: `raw-image-${crypto.randomUUID()}`,
    image_size: imageSize,
    image_quality: quality,
    image_model: model,
    skip_vl: true,
    source_only: true,
    pixelize: { ...defaultPixelize, preview_scale: 0, remove_bg: false, auto_crop: false },
    grid: { mode: 'off' },
  }
}

function isRawImageJob(job: GenerationJob) {
  const grid = job.params_json?.grid
  const gridMode = typeof grid === 'object' && grid !== null && 'mode' in grid ? (grid as { mode?: unknown }).mode : null
  return job.job_type === 'text_to_image' && (job.params_json?.source_only === true || (job.params_json?.skip_vl === true && gridMode === 'off'))
}

function firstOutput(job: GenerationJob | null | undefined) { return Array.isArray(job?.outputs) ? job.outputs[0] : undefined }
function rawSourceUrl(job: GenerationJob | null | undefined) { return signedFileUrl(firstOutput(job)?.source_url) || null }
function buildThumbs(rawJobs: GenerationJob[], selectedJobId: number | null) { const thumbs: Array<{ key: string; job: GenerationJob; url: string; label: string; selected: boolean }> = []; for (const job of rawJobs) { const url = rawSourceUrl(job); if (url) thumbs.push({ key: `job-${job.id}`, job, url, label: `任务 #${job.id}`, selected: job.id === selectedJobId }) } return thumbs }
function rawStateLabel(job: GenerationJob, text: (zh: string, en: string) => string) { if (job.status === 'failed') return summarizeJobError(job.error_message, text).title; if (job.status === 'running' || job.status === 'pending') return text('正在生成单张原图', 'Generating one source image'); return text('暂未拿到源图链接', 'No source image link yet') }
