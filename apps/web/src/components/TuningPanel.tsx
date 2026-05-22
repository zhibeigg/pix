import { FormEvent, useEffect, useMemo, useState } from 'react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'
import { buildGridDesign, buildPixelize, hasInvalidSubAssetSize, parsePixelSize, summarizePrompt } from '../pixelize'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Textarea } from './ui/textarea'
import { Badge } from './ui/badge'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixStatusBadge } from './pix/PixStatusBadge'
import { PixelControls } from './PixelControls'

export function TuningPanel({ job, pricing, loading, onSubmit }: { job: GenerationJob | null; pricing: PricingRule[]; loading: boolean; onSubmit: (payload: JobCreateRequest) => Promise<void> }) {
  const { text } = useI18n()
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [aiPrompt, setAiPrompt] = useState(() => text('保留主体，优化材质和颜色', 'Keep the subject, improve material and color'))
  const aiPrice = useMemo(() => pricing.find((item) => item.key === 'image_to_image')?.price_credits ?? 0, [pricing])

  useEffect(() => {
    if (!job) return
    const pixelize = asRecord(job.params_json?.pixelize)
    if (!pixelize) return
    const size = pixelize.output_size
    if (Array.isArray(size) && size.length >= 2) {
      setPixelSize(`${size[0]}x${size[1]}`)
    }
    if (Number.isFinite(pixelize.colors)) {
      setColors(Number(pixelize.colors))
    }
    if (typeof pixelize.remove_bg === 'boolean') {
      setRemoveBg(pixelize.remove_bg)
    }
  }, [job?.id])

  if (!job) return <PixPanel eyebrow={text('微调工位', 'Tuning station')} title={text('选择作品进行微调', 'Select a work to tune')} description={text('选择作品后可重新像素化或 AI 微调。', 'After selecting a work, you can repixelize it or run AI tuning.')} />

  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const sourcePath = output?.source_path || output?.pixelized_path || job.input_image_path || ''
  const previewUrl = signedFileUrl(output?.pixelized_url || output?.preview_url || output?.source_url || job.input_image_url || '')
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)

  async function submitLocal(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({ job_type: 'repixelize', prompt: null, input_image_path: sourcePath, client_request_id: crypto.randomUUID(), skip_vl: true, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }), grid: buildGridDesign() })
  }

  async function submitAi(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({ job_type: 'image_to_image', prompt: aiPrompt, input_image_path: sourcePath, client_request_id: crypto.randomUUID(), skip_vl: false, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }), grid: buildGridDesign() })
  }

  return (
    <div className="sticky top-24 grid gap-4">
      <PixPanel eyebrow={text('微调工位', 'Tuning station')} title={`#${job.id}`} description={summarizePrompt(job.prompt || job.input_image_path)} action={<PixStatusBadge status={job.status} />}>
        <PixPreviewFrame url={previewUrl} label={text('暂无可预览源图', 'No source preview available')} className="min-h-44" />
      </PixPanel>
      {invalidSubAssetSize && <Alert variant="destructive">{text('素材最低支持 16×16。', 'Minimum asset size is 16×16.')}</Alert>}
      <form className="grid gap-4 rounded-lg border border-border bg-[hsl(var(--pix-mint)/.46)] p-5" onSubmit={submitLocal}>
        <div className="flex items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">{text('本地像素化', 'Local pixelize')}</h3><p className="text-sm text-muted-foreground">{text('免费 · 不消耗点数', 'Free · no credits used')}</p></div><Badge variant="secondary">FREE</Badge></div>
        <PixelControls compact pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} />
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={removeBg} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{text('透明背景', 'Transparent background')}</label>
        <Button type="submit" disabled={loading || !sourcePath || invalidSubAssetSize}>{text('重新像素化', 'Repixelize')}</Button>
      </form>
      <form className="grid gap-4 rounded-lg border border-border bg-[hsl(var(--pix-lavender)/.54)] p-5" onSubmit={submitAi}>
        <div className="flex items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">{text('AI 微调', 'AI tuning')}</h3><p className="text-sm text-muted-foreground">{text(`消耗 ${aiPrice} 点`, `Uses ${aiPrice} credits`)}</p></div><Badge variant="outline">{text(`${aiPrice} 点`, `${aiPrice} credits`)}</Badge></div>
        {!sourcePath && <Alert variant="warning">{text('当前作品没有可用源图路径，暂时无法微调。', 'This work has no source image path, so tuning is unavailable for now.')}</Alert>}
        <Textarea value={aiPrompt} rows={3} onChange={(event) => setAiPrompt(event.target.value)} />
        <Button type="submit" variant="outline" disabled={loading || !sourcePath || invalidSubAssetSize}>{text('AI 微调并入队', 'Queue AI tuning')}</Button>
      </form>
    </div>
  )
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}
