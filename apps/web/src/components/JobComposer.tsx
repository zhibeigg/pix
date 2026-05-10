import { FormEvent, useMemo, useState } from 'react'
import type { JobCreateRequest, JobType, PixelizeParams, PricingRule } from '../types'

const defaultPixelize: PixelizeParams = {
  output_size: [128, 128],
  colors: 16,
  dither: 'floyd_steinberg',
  preset: 'auto',
  preview_scale: 4,
  edge_enhance: 0.1,
  saturation: 1,
  resample: 'smart',
  snap_to_grid: true,
  remove_bg: false,
  bg_tolerance: 12,
  bg_feather: 0,
  edge_style: 'hard',
  auto_crop: false,
  crop_padding: 0.12,
  crop_square: true,
}

type JobComposerProps = {
  pricing: PricingRule[]
  onSubmit: (payload: JobCreateRequest) => Promise<void>
  loading: boolean
}

export function JobComposer({ pricing, onSubmit, loading }: JobComposerProps) {
  const [jobType, setJobType] = useState<JobType>('text_to_image')
  const [prompt, setPrompt] = useState('A fantasy crystal item icon, isolated, pixel art ready')
  const [inputImagePath, setInputImagePath] = useState('')
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [dither, setDither] = useState('floyd_steinberg')
  const [removeBg, setRemoveBg] = useState(false)
  const [skipVl, setSkipVl] = useState(false)

  const price = useMemo(() => pricing.find((item) => item.key === jobType)?.price_credits ?? 0, [pricing, jobType])
  const needsImage = jobType !== 'text_to_image'
  const needsPrompt = jobType === 'text_to_image' || jobType === 'image_to_image'

  async function submit(event: FormEvent) {
    event.preventDefault()
    const [w, h] = pixelSize.toLowerCase().split('x').map((v) => Number(v.trim()))
    const pixelize: PixelizeParams = {
      ...defaultPixelize,
      output_size: [Number.isFinite(w) ? w : 128, Number.isFinite(h) ? h : 128],
      colors,
      dither,
      remove_bg: removeBg,
    }
    await onSubmit({
      job_type: jobType,
      prompt: needsPrompt ? prompt : null,
      input_image_path: needsImage ? inputImagePath : null,
      client_request_id: crypto.randomUUID(),
      skip_vl: skipVl,
      pixelize,
    })
  }

  return (
    <section className="panel composer-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Create</p>
          <h2>生成任务</h2>
        </div>
        <span className="price-tag">预计 {price} credits</span>
      </div>
      <form onSubmit={submit} className="stack">
        <label>
          任务类型
          <select value={jobType} onChange={(event) => setJobType(event.target.value as JobType)}>
            <option value="text_to_image">文生图</option>
            <option value="image_to_image">图生图</option>
            <option value="local_pixelize">本地像素化</option>
            <option value="repixelize">重新像素化</option>
          </select>
        </label>
        {needsPrompt && (
          <label>
            Prompt
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} />
          </label>
        )}
        {needsImage && (
          <label>
            输入图片路径（服务器可访问）
            <input value={inputImagePath} onChange={(event) => setInputImagePath(event.target.value)} placeholder="D:\\images\\source.png" />
          </label>
        )}
        <div className="two-columns">
          <label>
            像素尺寸
            <input value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} />
          </label>
          <label>
            颜色数
            <input type="number" min={2} max={256} value={colors} onChange={(event) => setColors(Number(event.target.value))} />
          </label>
        </div>
        <div className="two-columns">
          <label>
            抖动
            <select value={dither} onChange={(event) => setDither(event.target.value)}>
              <option value="none">无</option>
              <option value="ordered">Ordered</option>
              <option value="floyd_steinberg">Floyd-Steinberg</option>
            </select>
          </label>
          <label className="check-row">
            <input type="checkbox" checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />
            自动透明背景
          </label>
        </div>
        <label className="check-row">
          <input type="checkbox" checked={skipVl} onChange={(event) => setSkipVl(event.target.checked)} />
          跳过 VL 分析
        </label>
        <button disabled={loading}>{loading ? '提交中…' : '创建任务并入队'}</button>
      </form>
    </section>
  )
}
