import { FormEvent, useMemo, useState } from 'react'
import type { JobCreateRequest, PricingRule } from '../types'
import { buildPixelize, parsePixelSize } from '../pixelize'

type BatchGeneratePanelProps = {
  pricing: PricingRule[]
  loading: boolean
  onSubmitMany: (payloads: JobCreateRequest[]) => Promise<void>
}

export function BatchGeneratePanel({ pricing, loading, onSubmitMany }: BatchGeneratePanelProps) {
  const [prompts, setPrompts] = useState('血气灵玉\n紫髓铁\n幽香腐骨菇\n玉石原石\n紫檀木')
  const [pixelSize, setPixelSize] = useState('64x64')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [skipVl, setSkipVl] = useState(false)

  const lines = useMemo(() => prompts.split('\n').map((line) => line.trim()).filter(Boolean), [prompts])
  const unitPrice = pricing.find((item) => item.key === 'text_to_image')?.price_credits ?? 0
  const totalPrice = lines.length * unitPrice

  async function submit(event: FormEvent) {
    event.preventDefault()
    const pixelize = buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg })
    await onSubmitMany(lines.map((prompt) => ({
      job_type: 'text_to_image',
      prompt,
      input_image_path: null,
      client_request_id: crypto.randomUUID(),
      skip_vl: skipVl,
      pixelize,
    })))
  }

  return (
    <section className="panel composer-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Batch</p>
          <h2>批量生产</h2>
        </div>
        <span className="price-tag">{lines.length} 个 · 预计 {totalPrice} credits</span>
      </div>
      <form className="stack" onSubmit={submit}>
        <label>
          批量 Prompt（每行一个素材）
          <textarea rows={8} value={prompts} onChange={(event) => setPrompts(event.target.value)} />
        </label>
        <div className="two-columns">
          <label>像素尺寸<input value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} /></label>
          <label>颜色数<input type="number" min={2} max={256} value={colors} onChange={(event) => setColors(Number(event.target.value))} /></label>
        </div>
        <label className="check-row"><input type="checkbox" checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />透明背景</label>
        <label className="check-row"><input type="checkbox" checked={skipVl} onChange={(event) => setSkipVl(event.target.checked)} />跳过 VL 分析</label>
        <button disabled={loading || lines.length === 0}>{loading ? '提交中…' : `批量入队 ${lines.length} 个任务`}</button>
      </form>
    </section>
  )
}
