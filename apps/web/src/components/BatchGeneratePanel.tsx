import { FormEvent, useMemo, useState } from 'react'
import { api } from '../api'
import type { JobCreateRequest, JobType, PricingRule, UploadResponse } from '../types'
import { buildPixelize, parsePixelSize } from '../pixelize'

type BatchMode = 'text_to_image' | 'image_to_image' | 'local_pixelize'

type BatchUpload = {
  id: string
  name: string
  status: 'uploading' | 'uploaded' | 'failed'
  error?: string
  upload?: UploadResponse
}

type BatchGeneratePanelProps = {
  pricing: PricingRule[]
  loading: boolean
  token: string
  onSubmitMany: (payloads: JobCreateRequest[], batchName: string, mode: string) => Promise<void>
}

export function BatchGeneratePanel({ pricing, loading, token, onSubmitMany }: BatchGeneratePanelProps) {
  const [batchMode, setBatchMode] = useState<BatchMode>('text_to_image')
  const [batchName, setBatchName] = useState('RPG 材料包')
  const [prompts, setPrompts] = useState('血气灵玉\n紫髓铁\n幽香腐骨菇\n玉石原石\n紫檀木')
  const [sharedPrompt, setSharedPrompt] = useState('保留主体，统一改造成清晰的像素游戏图标风格')
  const [uploads, setUploads] = useState<BatchUpload[]>([])
  const [uploading, setUploading] = useState(false)
  const [pixelSize, setPixelSize] = useState('64x64')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [skipVl, setSkipVl] = useState(false)

  const lines = useMemo(() => prompts.split('\n').map((line) => line.trim()).filter(Boolean), [prompts])
  const uploaded = uploads.filter((item) => item.status === 'uploaded' && item.upload)
  const unitPrice = pricing.find((item) => item.key === batchMode)?.price_credits ?? 0
  const taskCount = batchMode === 'text_to_image' ? lines.length : uploaded.length
  const totalPrice = taskCount * unitPrice

  async function uploadFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setUploading(true)
    const selected = Array.from(files)
    const initial = selected.map((file) => ({ id: crypto.randomUUID(), name: file.name, status: 'uploading' as const }))
    setUploads(initial)
    const next: BatchUpload[] = []
    for (const [index, file] of selected.entries()) {
      const current = initial[index]
      try {
        const result = await api.uploadImage(token, file)
        next.push({ ...current, status: 'uploaded', upload: result })
      } catch (error) {
        next.push({ ...current, status: 'failed', error: error instanceof Error ? error.message : '上传失败' })
      }
      setUploads([...next, ...initial.slice(index + 1)])
    }
    setUploading(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const pixelize = buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg })
    let payloads: JobCreateRequest[] = []
    if (batchMode === 'text_to_image') {
      payloads = lines.map((prompt) => ({
        job_type: 'text_to_image',
        prompt,
        input_image_path: null,
        client_request_id: crypto.randomUUID(),
        skip_vl: skipVl,
        pixelize,
      }))
    } else if (batchMode === 'image_to_image') {
      payloads = uploaded.map((item) => ({
        job_type: 'image_to_image',
        prompt: sharedPrompt,
        input_image_path: item.upload?.path ?? null,
        client_request_id: crypto.randomUUID(),
        skip_vl: skipVl,
        pixelize,
      }))
    } else {
      payloads = uploaded.map((item) => ({
        job_type: 'local_pixelize',
        prompt: null,
        input_image_path: item.upload?.path ?? null,
        client_request_id: crypto.randomUUID(),
        skip_vl: true,
        pixelize,
      }))
    }
    await onSubmitMany(payloads, batchName, batchMode)
  }

  return (
    <section className="panel composer-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Batch</p>
          <h2>批量生产</h2>
        </div>
        <span className="price-tag">{taskCount} 个 · 预计 {totalPrice} credits</span>
      </div>
      <form className="stack" onSubmit={submit}>
        <label>
          素材包名称
          <input value={batchName} onChange={(event) => setBatchName(event.target.value)} placeholder="例如：RPG 材料包" />
        </label>
        <label>
          批量类型
          <select value={batchMode} onChange={(event) => setBatchMode(event.target.value as BatchMode)}>
            <option value="text_to_image">批量文生图</option>
            <option value="image_to_image">批量图生图</option>
            <option value="local_pixelize">批量本地像素化</option>
          </select>
        </label>

        {batchMode === 'text_to_image' ? (
          <label>
            批量 Prompt（每行一个素材）
            <textarea rows={8} value={prompts} onChange={(event) => setPrompts(event.target.value)} />
          </label>
        ) : (
          <div className="stack upload-block">
            {batchMode === 'image_to_image' && (
              <label>
                共用 AI 微调描述
                <textarea rows={4} value={sharedPrompt} onChange={(event) => setSharedPrompt(event.target.value)} />
              </label>
            )}
            <label>
              批量上传图片
              <input type="file" multiple accept="image/png,image/jpeg,image/webp" disabled={uploading} onChange={(event) => uploadFiles(event.target.files)} />
            </label>
            <UploadList uploads={uploads} />
          </div>
        )}

        <div className="two-columns">
          <label>像素尺寸<input value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} /></label>
          <label>颜色数<input type="number" min={2} max={256} value={colors} onChange={(event) => setColors(Number(event.target.value))} /></label>
        </div>
        <label className="check-row"><input type="checkbox" checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />透明背景</label>
        <label className="check-row"><input type="checkbox" checked={skipVl} disabled={batchMode === 'local_pixelize'} onChange={(event) => setSkipVl(event.target.checked)} />跳过 VL 分析</label>
        <button disabled={loading || uploading || taskCount === 0}>{loading ? '提交中…' : `批量入队 ${taskCount} 个任务`}</button>
      </form>
    </section>
  )
}

function UploadList({ uploads }: { uploads: BatchUpload[] }) {
  if (uploads.length === 0) return <p className="muted">选择多张图片后会先上传，再批量创建任务。</p>
  const ok = uploads.filter((item) => item.status === 'uploaded').length
  const failed = uploads.filter((item) => item.status === 'failed').length
  return (
    <div className="batch-upload-list">
      <p className="muted">已上传 {ok} / {uploads.length}{failed ? `，失败 ${failed}` : ''}</p>
      {uploads.map((item) => (
        <div className="batch-upload-item" key={item.id}>
          {item.upload?.url ? <img src={item.upload.url} alt={item.name} /> : <span className="upload-placeholder">{item.status}</span>}
          <div>
            <strong>{item.name}</strong>
            <p>{item.error || item.upload?.path || item.status}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
