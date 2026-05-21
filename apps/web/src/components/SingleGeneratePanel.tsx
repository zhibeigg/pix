import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../api'
import type { JobCreateRequest, JobType, PricingRule } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, hasInvalidSubAssetSize, parsePixelSize } from '../pixelize'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Input } from './ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { Badge } from './ui/badge'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixelControls } from './PixelControls'

type Props = { pricing: PricingRule[]; loading: boolean; token: string; onSubmit: (payload: JobCreateRequest) => Promise<void> }

export function SingleGeneratePanel({ pricing, loading, token, onSubmit }: Props) {
  const [jobType, setJobType] = useState<JobType>('asset')
  const [assetName, setAssetName] = useState('血气灵玉')
  const [assetExtraPrompt, setAssetExtraPrompt] = useState('红色晶体、深色描边、适合 RPG 背包图标')
  const [prompt, setPrompt] = useState('一枚幻想 RPG 魔法药水图标，居中构图，轮廓清晰，透明背景')
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(12)
  const [removeBg, setRemoveBg] = useState(true)
  const [skipVl, setSkipVl] = useState(false)
  const [durationMs, setDurationMs] = useState(120)

  const price = useMemo(() => pricing.find((item) => item.key === jobType)?.price_credits ?? 0, [pricing, jobType])
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const isAsset = jobType === 'asset'
  const isSprite = jobType === 'sprite_sheet'
  const needsPrompt = jobType === 'text_to_image' || jobType === 'image_to_image' || isSprite
  const needsImage = jobType !== 'asset' && jobType !== 'text_to_image' && !isSprite
  const submitBlocked = invalidSubAssetSize || (isAsset && !assetName.trim()) || (needsPrompt && !prompt.trim()) || (needsImage && !inputImagePath.trim())

  useEffect(() => {
    if (jobType === 'asset') { setPixelSize('16x16'); setColors(12); setRemoveBg(true) }
    else if (jobType === 'sprite_sheet') { setPixelSize('64x64'); setColors(16); setRemoveBg(false) }
    else { setPixelSize('128x128'); setColors(16); setRemoveBg(true) }
  }, [jobType])

  async function uploadFile(file: File | undefined) {
    if (!file) return
    setUploading(true); setUploadMessage('上传中…')
    try {
      const uploaded = await api.uploadImage(token, file)
      setInputImagePath(uploaded.path); setUploadUrl(uploaded.url ?? ''); setUploadMessage(`已上传 ${uploaded.filename}`)
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : '上传失败')
    } finally { setUploading(false) }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (isAsset) {
      await onSubmit({ job_type: 'asset', prompt: assetName.trim(), input_image_path: null, client_request_id: crypto.randomUUID(), pixelize: buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }), grid: buildGridDesign(), asset: { name: assetName.trim(), extra_prompt: assetExtraPrompt.trim(), no_preview: false } })
      return
    }
    await onSubmit({ job_type: jobType, prompt: needsPrompt ? prompt : null, input_image_path: needsImage ? inputImagePath : null, client_request_id: crypto.randomUUID(), skip_vl: skipVl, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: isSprite ? false : removeBg }), grid: buildGridDesign(), sprite: isSprite ? { duration_ms: durationMs, loop: 0, rows: 3, cols: 3 } : undefined })
  }

  return (
    <PixPanel eyebrow="单张试做" title="任务配方" action={<Badge variant="info">预计 {price} 点</Badge>}>
      <form className="grid gap-5" onSubmit={submit}>
        <PixField label="模式">
          <Select value={jobType} onValueChange={(value) => setJobType(value as JobType)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="asset">游戏素材直出</SelectItem>
              <SelectItem value="text_to_image">文生图</SelectItem>
              <SelectItem value="image_to_image">图生图 / AI 微调</SelectItem>
              <SelectItem value="sprite_sheet">九宫格动画精灵表</SelectItem>
              <SelectItem value="local_pixelize">本地像素化</SelectItem>
            </SelectContent>
          </Select>
        </PixField>

        {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><PixField label="素材名称" hint="会注入 pix asset 的游戏物品 Prompt 模板。"><Input value={assetName} onChange={(e) => setAssetName(e.target.value)} /></PixField><PixField label="额外风格描述"><Textarea value={assetExtraPrompt} rows={3} onChange={(e) => setAssetExtraPrompt(e.target.value)} /></PixField></div>}
        {needsPrompt && <PixField label="素材描述" hint="写清主体、材质和用途。"><Textarea value={prompt} rows={5} onChange={(e) => setPrompt(e.target.value)} /></PixField>}
        {needsImage && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? '上传中…' : '上传图片'}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => void uploadFile(event.currentTarget.files?.[0])} /></label></Button>{uploadMessage && <Alert variant={uploadMessage.includes('失败') ? 'destructive' : 'info'}>{uploadMessage}</Alert>}<PixPreviewFrame url={uploadUrl} label="等待上传预览" /><PixField label="图片路径"><Input value={inputImagePath} placeholder="上传后自动填充" onChange={(e) => setInputImagePath(e.target.value)} /></PixField></div>}

        <PixelControls pixelLabel={isSprite ? '单帧尺寸' : '像素尺寸'} pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} />
        {isSprite && <PixField label="GIF 帧间隔(ms)"><Input type="number" value={durationMs} onChange={(e) => setDurationMs(Number(e.target.value))} /></PixField>}
        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={removeBg} disabled={isSprite} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />透明背景</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={isSprite || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? '素材直出默认 VL 策略' : '跳过参考图理解'}</label></div>
        {invalidSubAssetSize && <Alert variant="destructive">素材最低支持 16×16。</Alert>}
        {isAsset && <Alert variant="info">素材直出会按 CLI `pix asset` 策略使用白底单图模板、Pixel Grid 提取和透明 PNG 输出。</Alert>}
        <Button type="submit" size="lg" disabled={loading || submitBlocked}>{loading ? '提交中…' : isSprite ? '生成动画精灵表' : isAsset ? '生成游戏素材' : '生成单张素材'}</Button>
      </form>
    </PixPanel>
  )
}
