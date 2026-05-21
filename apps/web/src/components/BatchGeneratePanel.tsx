import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../api'
import type { CreditBalance, JobCreateRequest, PricingRule, UploadResponse } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, hasInvalidSubAssetSize, parsePixelSize } from '../pixelize'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Input } from './ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixelControls } from './PixelControls'

type BatchMode = 'asset' | 'text_to_image' | 'image_to_image' | 'local_pixelize'
type BatchUpload = { id: string; name: string; status: 'uploading' | 'uploaded' | 'failed'; error?: string; upload?: UploadResponse }
type Props = { pricing: PricingRule[]; balance: CreditBalance | null; loading: boolean; token: string; onSubmitMany: (payloads: JobCreateRequest[], batchName: string, mode: string) => Promise<void> }

export function BatchGeneratePanel({ pricing, balance, loading, token, onSubmitMany }: Props) {
  const [batchMode, setBatchMode] = useState<BatchMode>('asset')
  const [batchName, setBatchName] = useState('RPG 材料包')
  const [prompts, setPrompts] = useState('血气灵玉\n紫髓铁\n幽香腐骨菇\n玉石原石\n紫檀木')
  const [assetExtraPrompt, setAssetExtraPrompt] = useState('统一为清晰的经典 RPG 背包物品图标，深色描边，居中构图')
  const [sharedPrompt, setSharedPrompt] = useState('保留主体，统一改造成清晰的像素游戏图标风格')
  const [uploads, setUploads] = useState<BatchUpload[]>([])
  const [uploading, setUploading] = useState(false)
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(12)
  const [removeBg, setRemoveBg] = useState(true)
  const [skipVl, setSkipVl] = useState(false)

  const lines = useMemo(() => prompts.split('\n').map((line) => line.trim()).filter(Boolean), [prompts])
  const uploaded = uploads.filter((item) => item.status === 'uploaded' && item.upload)
  const unitPrice = pricing.find((item) => item.key === batchMode)?.price_credits ?? 0
  const taskCount = batchMode === 'text_to_image' || batchMode === 'asset' ? lines.length : uploaded.length
  const totalPrice = taskCount * unitPrice
  const availableCredits = balance?.available_credits ?? null
  const insufficientCredits = availableCredits !== null && totalPrice > availableCredits
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const isAsset = batchMode === 'asset'

  useEffect(() => {
    if (batchMode === 'asset') { setPixelSize('16x16'); setColors(12); setRemoveBg(true) }
    else { setPixelSize('64x64'); setColors(16); setRemoveBg(true) }
  }, [batchMode])

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    const selected = Array.from(files)
    const initial = selected.map((file) => ({ id: crypto.randomUUID(), name: file.name, status: 'uploading' as const }))
    setUploads(initial)
    const next: BatchUpload[] = []
    for (const [index, file] of selected.entries()) {
      const current = initial[index]
      try { next.push({ ...current, status: 'uploaded', upload: await api.uploadImage(token, file) }) }
      catch (error) { next.push({ ...current, status: 'failed', error: error instanceof Error ? error.message : '上传失败' }) }
      setUploads([...next, ...initial.slice(index + 1)])
    }
    setUploading(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const pixelize = isAsset ? buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }) : buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg })
    const grid = buildGridDesign()
    let payloads: JobCreateRequest[] = []
    if (batchMode === 'asset') payloads = lines.map((name) => ({ job_type: 'asset', prompt: name, input_image_path: null, client_request_id: crypto.randomUUID(), pixelize, grid, asset: { name, extra_prompt: assetExtraPrompt.trim(), no_preview: false } }))
    else if (batchMode === 'text_to_image') payloads = lines.map((prompt) => ({ job_type: 'text_to_image', prompt, input_image_path: null, client_request_id: crypto.randomUUID(), skip_vl: skipVl, pixelize, grid }))
    else if (batchMode === 'image_to_image') payloads = uploaded.map((item) => ({ job_type: 'image_to_image', prompt: sharedPrompt, input_image_path: item.upload?.path ?? null, client_request_id: crypto.randomUUID(), skip_vl: skipVl, pixelize, grid }))
    else payloads = uploaded.map((item) => ({ job_type: 'local_pixelize', prompt: null, input_image_path: item.upload?.path ?? null, client_request_id: crypto.randomUUID(), skip_vl: true, pixelize, grid }))
    if (payloads.length >= 10 && !window.confirm(`入队 ${payloads.length} 个任务并冻结 ${totalPrice} 点？`)) return
    await onSubmitMany(payloads, batchName, batchMode)
  }

  return (
    <PixPanel eyebrow="素材包生产" title="批量生产" action={<Badge variant={insufficientCredits ? 'danger' : 'info'}>{taskCount} 个 · 预计 {totalPrice} 点</Badge>}>
      <form className="grid gap-5" onSubmit={submit}>
        <BatchCostSummary taskCount={taskCount} unitPrice={unitPrice} totalPrice={totalPrice} availableCredits={availableCredits} insufficientCredits={insufficientCredits} />
        <PixField label="素材包名称"><Input value={batchName} onChange={(event) => setBatchName(event.target.value)} /></PixField>
        <PixField label="批量类型"><Select value={batchMode} onValueChange={(value) => setBatchMode(value as BatchMode)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="asset">批量游戏素材直出</SelectItem><SelectItem value="text_to_image">批量文生图</SelectItem><SelectItem value="image_to_image">批量图生图</SelectItem><SelectItem value="local_pixelize">批量本地像素化</SelectItem></SelectContent></Select></PixField>
        {batchMode === 'asset' || batchMode === 'text_to_image' ? <div className="grid gap-4">{isAsset && <PixField label="统一额外风格描述"><Textarea value={assetExtraPrompt} rows={3} onChange={(e) => setAssetExtraPrompt(e.target.value)} /></PixField>}<PixField label={isAsset ? '素材名称（每行一个）' : '素材描述（每行一个）'}><Textarea value={prompts} rows={8} onChange={(e) => setPrompts(e.target.value)} /></PixField></div> : <div className="grid gap-4 rounded-2xl border border-border bg-muted/45 p-4">{batchMode === 'image_to_image' && <PixField label="共用微调描述"><Textarea value={sharedPrompt} rows={4} onChange={(e) => setSharedPrompt(e.target.value)} /></PixField>}<Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? '上传中…' : '批量上传图片'}<input type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => void uploadFiles(e.currentTarget.files)} /></label></Button><UploadList uploads={uploads} /></div>}
        <PixelControls pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} />
        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={removeBg} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />透明背景</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={batchMode === 'local_pixelize' || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? '素材直出默认 VL 策略' : '跳过参考图理解'}</label></div>
        {invalidSubAssetSize && <Alert variant="destructive">素材最低支持 16×16。</Alert>}
        {isAsset && <Alert variant="info">素材直出默认使用 `pix asset` 的白底单图模板、Pixel Grid 提取和透明 PNG 输出。</Alert>}
        {insufficientCredits && <Button type="button" variant="outline" onClick={() => { window.location.hash = '/billing' }}>点数不足，前往点数中心</Button>}
        <Button type="submit" size="lg" disabled={loading || uploading || taskCount === 0 || insufficientCredits || invalidSubAssetSize}>{loading ? '提交中…' : `入队 ${taskCount} 个素材任务`}</Button>
      </form>
    </PixPanel>
  )
}

function BatchCostSummary({ taskCount, unitPrice, totalPrice, availableCredits, insufficientCredits }: { taskCount: number; unitPrice: number; totalPrice: number; availableCredits: number | null; insufficientCredits: boolean }) {
  return <Alert variant={insufficientCredits ? 'warning' : 'info'}>{taskCount} 个素材 · 单价 {unitPrice} 点 · 预计冻结 {totalPrice} 点 · 当前可用 {availableCredits ?? '—'} 点。入队冻结点数，失败退回。</Alert>
}

function UploadList({ uploads }: { uploads: BatchUpload[] }) {
  if (!uploads.length) return <Alert variant="info">先上传图片。</Alert>
  return <div className="grid gap-2">{uploads.map((item) => <div key={item.id} className="grid grid-cols-[64px_minmax(0,1fr)] gap-3 rounded-2xl border border-border bg-card p-2">{item.upload?.url ? <img src={item.upload.url} alt={item.name} className="h-16 w-16 rounded-xl object-contain [image-rendering:pixelated]" /> : <PixPreviewFrame className="min-h-16" label={item.status} />}<div className="min-w-0 self-center"><p className="truncate text-sm font-bold">{item.name}</p><p className="truncate text-xs text-muted-foreground">{item.error || item.upload?.path || item.status}</p></div></div>)}</div>
}
