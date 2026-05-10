import { FormEvent, useMemo, useState } from 'react'
import { api } from '../api'
import type { JobCreateRequest, JobType, PricingRule } from '../types'
import { buildPixelize, parsePixelSize } from '../pixelize'

type SingleGeneratePanelProps = {
  pricing: PricingRule[]
  loading: boolean
  token: string
  onSubmit: (payload: JobCreateRequest) => Promise<void>
}

export function SingleGeneratePanel({ pricing, loading, token, onSubmit }: SingleGeneratePanelProps) {
  const [jobType, setJobType] = useState<JobType>('text_to_image')
  const [prompt, setPrompt] = useState('A single fantasy RPG item icon, centered, clean silhouette')
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [skipVl, setSkipVl] = useState(false)

  const price = useMemo(() => pricing.find((item) => item.key === jobType)?.price_credits ?? 0, [pricing, jobType])
  const needsPrompt = jobType === 'text_to_image' || jobType === 'image_to_image'
  const needsImage = jobType !== 'text_to_image'

  async function uploadFile(file: File | undefined) {
    if (!file) return
    setUploading(true)
    setUploadMessage('上传中…')
    try {
      const uploaded = await api.uploadImage(token, file)
      setInputImagePath(uploaded.path)
      setUploadUrl(uploaded.url ?? '')
      setUploadMessage(`已上传 ${uploaded.filename}`)
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    await onSubmit({
      job_type: jobType,
      prompt: needsPrompt ? prompt : null,
      input_image_path: needsImage ? inputImagePath : null,
      client_request_id: crypto.randomUUID(),
      skip_vl: skipVl,
      pixelize: buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg }),
    })
  }

  return (
    <section className="panel composer-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Single</p>
          <h2>单图生成</h2>
        </div>
        <span className="price-tag">预计 {price} credits</span>
      </div>
      <form className="stack" onSubmit={submit}>
        <label>
          模式
          <select value={jobType} onChange={(event) => setJobType(event.target.value as JobType)}>
            <option value="text_to_image">文生图</option>
            <option value="image_to_image">图生图 / AI 微调</option>
            <option value="local_pixelize">本地像素化</option>
          </select>
        </label>
        {needsPrompt && <label>Prompt<textarea rows={5} value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label>}
        {needsImage && (
          <div className="stack upload-block">
            <label>
              上传图片
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={uploading}
                onChange={(event) => uploadFile(event.target.files?.[0])}
              />
            </label>
            {uploadMessage && <p className="muted">{uploadMessage}</p>}
            {uploadUrl && <img className="inline-preview" src={uploadUrl} alt="上传预览" />}
            <label>
              输入图片路径（可手动覆盖）
              <input value={inputImagePath} onChange={(event) => setInputImagePath(event.target.value)} placeholder="上传后自动填充" />
            </label>
          </div>
        )}
        <div className="two-columns">
          <label>像素尺寸<input value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} /></label>
          <label>颜色数<input type="number" min={2} max={256} value={colors} onChange={(event) => setColors(Number(event.target.value))} /></label>
        </div>
        <label className="check-row"><input type="checkbox" checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />透明背景</label>
        <label className="check-row"><input type="checkbox" checked={skipVl} onChange={(event) => setSkipVl(event.target.checked)} />跳过 VL 分析</label>
        <button disabled={loading}>{loading ? '提交中…' : '生成单张作品'}</button>
      </form>
    </section>
  )
}
