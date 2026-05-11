import { FormEvent, useMemo, useState } from 'react'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'
import { buildPixelize, parsePixelSize, summarizePrompt } from '../pixelize'

type TuningPanelProps = {
  job: GenerationJob | null
  pricing: PricingRule[]
  loading: boolean
  onSubmit: (payload: JobCreateRequest) => Promise<void>
}

export function TuningPanel({ job, pricing, loading, onSubmit }: TuningPanelProps) {
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [aiPrompt, setAiPrompt] = useState('保留主体，调整材质和颜色，使其更适合像素游戏图标')
  const aiPrice = useMemo(() => pricing.find((item) => item.key === 'image_to_image')?.price_credits ?? 0, [pricing])

  if (!job) {
    return (
      <section className="panel tuning-panel">
        <p className="eyebrow">Tune</p>
        <h2>选择作品进行微调</h2>
        <p className="muted">点击作品网格中的任意卡片，即可免费重新像素化，或使用 AI 图生图微调。</p>
      </section>
    )
  }

  const output = job.outputs[0]
  const sourcePath = output?.source_path || output?.pixelized_path || job.input_image_path || ''
  const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''

  async function submitLocal(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({
      job_type: 'repixelize',
      prompt: null,
      input_image_path: sourcePath,
      client_request_id: crypto.randomUUID(),
      skip_vl: true,
      pixelize: buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg }),
    })
  }

  async function submitAi(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({
      job_type: 'image_to_image',
      prompt: aiPrompt,
      input_image_path: sourcePath,
      client_request_id: crypto.randomUUID(),
      skip_vl: false,
      pixelize: buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg }),
    })
  }

  return (
    <section className="panel tuning-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Tune</p>
          <h2>微调 #{job.id}</h2>
          <p className="muted">{summarizePrompt(job.prompt || job.input_image_path)}</p>
        </div>
        <span className="pill">{job.status}</span>
      </div>
      {previewUrl && <img className="inline-preview tune-preview" src={previewUrl} alt="微调对象预览" loading="lazy" decoding="async" />}

      <form className="stack tune-block" onSubmit={submitLocal}>
        <div>
          <h3>免费本地微调</h3>
          <p className="muted">不调用 AI，只重新像素化，因此不消耗点数。</p>
        </div>
        <div className="two-columns">
          <label>像素尺寸<input value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} /></label>
          <label>颜色数<input type="number" min={2} max={256} value={colors} onChange={(event) => setColors(Number(event.target.value))} /></label>
        </div>
        <label className="check-row"><input type="checkbox" checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />透明背景</label>
        <button disabled={loading || !sourcePath}>免费重新像素化</button>
      </form>

      <form className="stack tune-block" onSubmit={submitAi}>
        <div>
          <h3>AI 微调</h3>
          <p className="muted">调用图生图接口，会消耗 {aiPrice} credits。</p>
        </div>
        <label>微调描述<textarea rows={4} value={aiPrompt} onChange={(event) => setAiPrompt(event.target.value)} /></label>
        <button disabled={loading || !sourcePath}>AI 微调并入队</button>
      </form>
    </section>
  )
}
