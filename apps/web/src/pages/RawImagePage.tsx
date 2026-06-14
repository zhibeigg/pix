import { FormEvent, useEffect, useMemo, useState } from 'react'
import { RefreshCw, Upload } from 'lucide-react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import { defaultPixelize, summarizePrompt } from '../pixelize'
import type { CreditBalance, GenerationJob, ImageModelInfo, ImageModelsResponse, JobCreateRequest, PricingRule } from '../types'
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
  token: string
  imageModels: ImageModelsResponse
  selectedJobId: number | null
  onSelectJob: (jobId: number) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRefresh: () => void | Promise<void>
}

const imageSizes = ['1024x1024', '1536x1024', '1024x1536', '2048x1024', '1024x2048', 'auto']
const qualityOptions = ['auto', 'low', 'medium', 'high']
const RAW_IMAGE_PROMPT_MAX_LENGTH = 3000

function modelItems(imageModels: ImageModelsResponse): ImageModelInfo[] {
  const byId = new Map((imageModels.items ?? []).map((item) => [item.id, item]))
  return imageModels.models.map((id) => byId.get(id) ?? {
    id,
    label: id,
    providers: [],
    operations: ['text_to_image', 'image_to_image'],
    sizes: imageSizes,
    qualities: qualityOptions,
    output_formats: ['png'],
    protocols: [],
    provider_count: 0,
  })
}

function supportsOperation(model: ImageModelInfo | undefined, operation: string) {
  return !model || model.operations.length === 0 || model.operations.includes(operation)
}

function modelOptionLabel(model: ImageModelInfo) {
  const providers = model.provider_count || model.providers.length
  return providers > 1 ? `${model.label || model.id} · ${providers} providers` : (model.label || model.id)
}

export function RawImagePage({ pricing, balance, jobs, loading, token, imageModels, selectedJobId, onSelectJob, onCreateJob, onRefresh }: Props) {
  const { text } = useI18n()
  const [model, setModel] = useState(imageModels.default || 'gpt-image-2')
  const availableImageModels = useMemo(() => modelItems(imageModels), [imageModels])
  const selectedModelInfo = useMemo(() => availableImageModels.find((item) => item.id === model), [availableImageModels, model])
  const modelSizes = selectedModelInfo?.sizes?.length ? selectedModelInfo.sizes : imageSizes
  const modelQualities = selectedModelInfo?.qualities?.length ? selectedModelInfo.qualities : qualityOptions
  const modelSupportsI2I = supportsOperation(selectedModelInfo, 'image_to_image')
  const [imageSize, setImageSize] = useState('1024x1024')
  const [quality, setQuality] = useState('auto')
  const [prompt, setPrompt] = useState(() => text('生成一张 1024×1024 方形应用图标风格的奇幻 RPG 治疗药水，深翡翠背景，轮廓清晰，电影感光照。', 'Create one polished 1024x1024 square app icon artwork for a fantasy RPG healing potion, deep emerald background, crisp silhouette, cinematic lighting.'))
  const [refImagePath, setRefImagePath] = useState('')
  const [refImageUrl, setRefImageUrl] = useState('')
  const [refUploading, setRefUploading] = useState(false)
  const [refMessage, setRefMessage] = useState('')
  const rawJobs = useMemo(() => jobs.filter(isRawImageJob).sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const selectedJob = rawJobs.find((job) => job.id === selectedJobId) ?? rawJobs[0] ?? null
  const hasReference = !!refImagePath
  const billingKey = hasReference ? 'image_to_image' : 'text_to_image'
  const price = pricing.find((item) => item.key === billingKey)?.price_credits ?? 0
  const promptTooLong = prompt.length > RAW_IMAGE_PROMPT_MAX_LENGTH
  const insufficientCredits = typeof balance?.available_credits === 'number' && balance.available_credits < price
  const isSelectedActive = selectedJob?.status === 'pending' || selectedJob?.status === 'running'
  const mainImageUrl = isSelectedActive ? null : rawSourceUrl(selectedJob)
  const failedError = selectedJob?.status === 'failed' ? summarizeJobError(selectedJob.error_message, text) : null
  const mainImageLabel = failedError?.title ?? text('原始单图', 'Raw single image')
  const thumbs = useMemo(() => buildThumbs(rawJobs, selectedJob?.id ?? null), [rawJobs, selectedJob?.id])

  useEffect(() => {
    if (!availableImageModels.some((item) => item.id === model)) {
      setModel(imageModels.default || availableImageModels[0]?.id || 'gpt-image-2')
    }
  }, [availableImageModels, imageModels.default, model])

  useEffect(() => {
    if (!modelSizes.includes(imageSize)) setImageSize(modelSizes[0] ?? '1024x1024')
  }, [imageSize, modelSizes])

  useEffect(() => {
    if (!modelQualities.includes(quality)) setQuality(modelQualities[0] ?? 'auto')
  }, [modelQualities, quality])

  async function uploadReferenceFile(file: File | undefined) {
    if (!file) return
    setRefUploading(true); setRefMessage(text('上传参考图…', 'Uploading reference…'))
    try {
      const uploaded = await api.uploadImage(token, file)
      setRefImagePath(uploaded.path); setRefImageUrl(signedFileUrl(uploaded.url)); setRefMessage(text('参考图已就绪，提交后将以图生图模式生成。', 'Reference ready. Job will run as image-to-image on submit.'))
    } catch (error) {
      setRefMessage(error instanceof Error ? error.message : text('参考图上传失败', 'Reference upload failed'))
    } finally { setRefUploading(false) }
  }

  function clearReference() {
    setRefImagePath(''); setRefImageUrl(''); setRefMessage('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const basePrompt = prompt.trim()
    if (!basePrompt || insufficientCredits || (hasReference && !modelSupportsI2I)) return
    await onCreateJob(buildRawPayload({ prompt: basePrompt, imageSize, quality, model, referenceImagePath: refImagePath || null }))
  }

  return (
    <form className="grid gap-5" onSubmit={submit}>
      <h1 className="sr-only">{text('原始生图', 'Raw image generation')}</h1>
      <PixPanel
        eyebrow={text('原图炉', 'Raw forge')}
        title={text('原始生图', 'Raw image generation')}
        description={text('一次只出一张原图，不做候选、评分、抠图或像素化后处理。', 'Generate exactly one source image with no candidates, ranking, matting, or pixel post-processing.')}
        action={<div className="flex flex-wrap gap-2"><Badge variant="outline">{text(`余额 ${balance?.available_credits ?? '—'} 点`, `Balance ${balance?.available_credits ?? '—'} credits`)}</Badge><Badge variant={insufficientCredits ? 'danger' : 'info'}>{text(`预计 ${price} 点`, `Estimated ${price} credits`)}</Badge><Button type="button" variant="outline" onClick={() => void onRefresh()}><RefreshCw />{text('刷新', 'Refresh')}</Button></div>}
      >
        <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)_148px]">
          <div className="grid content-start gap-4">
            <PixField label={text('提供商', 'Provider')}><Input value={(selectedModelInfo?.providers ?? []).join(' / ') || text('按后端配置自动选择', 'Auto by backend config')} disabled /></PixField>
            <PixField label={text('模型', 'Model')}><Select value={model} onValueChange={setModel}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{availableImageModels.map((item) => <SelectItem value={item.id} key={item.id}>{modelOptionLabel(item)}</SelectItem>)}</SelectContent></Select></PixField>
            <PixField label={text('图片尺寸', 'Image size')}><Select value={imageSize} onValueChange={setImageSize}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{modelSizes.map((size) => <SelectItem value={size} key={size}>{size}</SelectItem>)}</SelectContent></Select></PixField>
            <PixField label={text('质量', 'Quality')}><Select value={quality} onValueChange={setQuality}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{modelQualities.map((item) => <SelectItem value={item} key={item}>{item}</SelectItem>)}</SelectContent></Select></PixField>
            <PixField label={text('参考图（可选）', 'Reference image (optional)')} hint={text('上传后将以图生图模式生成；留空走文生图。', 'When provided, the job runs as image-to-image; leave empty for text-to-image.')}>
              <div className="grid gap-2">
                <Button type="button" variant="outline" asChild>
                  <label className="cursor-pointer">
                    <Upload />{refUploading ? text('上传中…', 'Uploading…') : refImagePath ? text('替换参考图', 'Replace reference') : text('上传参考图', 'Upload reference')}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => void uploadReferenceFile(event.currentTarget.files?.[0])} />
                  </label>
                </Button>
                {refMessage && <Alert variant={refMessage.includes('失败') || refMessage.toLowerCase().includes('failed') ? 'destructive' : 'info'}>{refMessage}</Alert>}
                {refImagePath && (
                  <div className="grid gap-1">
                    <PixPreviewFrame url={refImageUrl} loading={refUploading} label={text('参考图预览', 'Reference preview')} className="min-h-24" />
                    <Button type="button" variant="ghost" size="sm" onClick={clearReference}>{text('移除参考图', 'Remove reference')}</Button>
                  </div>
                )}
              </div>
            </PixField>
            {hasReference && !modelSupportsI2I ? <Alert variant="warning">{text('当前模型不支持参考图 / 图生图，请切换支持 image-to-image 的模型或移除参考图。', 'The selected model does not support reference images / image-to-image. Switch to a model with image-to-image support or remove the reference.')}</Alert> : <Alert variant="info">{hasReference ? text('已附带参考图：将走图生图（image-to-image）单次出图，仍跳过候选、VL 与像素化。', 'Reference attached: runs as image-to-image (single output) and still skips candidates, vision analysis, and pixelization.') : text('固定生成 1 张原图；后端会跳过候选图、VL 分析和像素化输出。', 'Always generates 1 source image; the backend skips candidates, vision analysis, and pixelized outputs.')}</Alert>}
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

      <PixPanel><div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_190px]"><div className="grid gap-2"><Textarea value={prompt} rows={5} required maxLength={RAW_IMAGE_PROMPT_MAX_LENGTH} onChange={(event) => setPrompt(event.target.value)} placeholder={text('描述你要生成的图片：主体、风格、构图、颜色、用途。', 'Describe the image: subject, style, composition, colors, and intended use.')} /><div className="flex justify-end text-xs text-muted-foreground">{prompt.length}/{RAW_IMAGE_PROMPT_MAX_LENGTH}</div></div><div className="grid content-between gap-3"><Badge variant="outline">{imageSize} · {quality} · {hasReference ? text('图生图', 'image-to-image') : text('1 张', '1 image')}</Badge>{promptTooLong && <Badge variant="danger">{text('提示词最多 3000 字', 'Prompt max 3000 characters')}</Badge>}<Button type="submit" size="lg" disabled={loading || !prompt.trim() || promptTooLong || insufficientCredits || (hasReference && !modelSupportsI2I)}>{loading ? text('提交中…', 'Submitting…') : hasReference ? text('图生图微调', 'Generate (image-to-image)') : text('生成单图', 'Generate image')}</Button></div></div></PixPanel>
    </form>
  )
}

function buildRawPayload({ prompt, imageSize, quality, model, referenceImagePath }: { prompt: string; imageSize: string; quality: string; model: string; referenceImagePath: string | null }): JobCreateRequest {
  if (referenceImagePath) {
    // 参考图存在时走 image_to_image。后端会调 /v1/images/edits 单次出图，
    // source_only=true 让 pipeline 跳过候选 / VL / 像素化后处理，仅落原图。
    return {
      job_type: 'image_to_image',
      prompt,
      input_image_path: referenceImagePath,
      client_request_id: `raw-i2i-${crypto.randomUUID()}`,
      image_size: imageSize,
      image_quality: quality,
      image_model: model,
      skip_vl: true,
      source_only: true,
      pixelize: { ...defaultPixelize, preview_scale: 0, remove_bg: false, auto_crop: false },
      grid: { mode: 'off' },
    }
  }
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
  // 文生图原始图：source_only=true 或 (skip_vl + grid=off)
  if (job.job_type === 'text_to_image' && (job.params_json?.source_only === true || (job.params_json?.skip_vl === true && gridMode === 'off'))) return true
  // 图生图原始图：source_only=true（与「调音 / AI 微调」走 image_to_image 但不带 source_only 的任务区分）
  if (job.job_type === 'image_to_image' && job.params_json?.source_only === true) return true
  return false
}

function firstOutput(job: GenerationJob | null | undefined) { return Array.isArray(job?.outputs) ? job.outputs[0] : undefined }
function rawSourceUrl(job: GenerationJob | null | undefined) { return signedFileUrl(firstOutput(job)?.source_url) || null }
function buildThumbs(rawJobs: GenerationJob[], selectedJobId: number | null) { const thumbs: Array<{ key: string; job: GenerationJob; url: string; label: string; selected: boolean }> = []; for (const job of rawJobs) { const url = rawSourceUrl(job); if (url) thumbs.push({ key: `job-${job.id}`, job, url, label: `任务 #${job.id}`, selected: job.id === selectedJobId }) } return thumbs }
function rawStateLabel(job: GenerationJob, text: (zh: string, en: string) => string) { if (job.status === 'failed') return summarizeJobError(job.error_message, text).title; if (job.status === 'running' || job.status === 'pending') return text('正在生成单张原图', 'Generating one source image'); return text('暂未拿到源图链接', 'No source image link yet') }
