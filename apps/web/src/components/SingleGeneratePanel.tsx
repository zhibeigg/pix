import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { JobCreateRequest, JobType, PricingRule } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, parsePixelSize, type EdgeStyleChoice } from '../pixelize'
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
type AssetKindChoice = 'item_icon' | 'ui_component'
type SubjectKindChoice = 'single_prop' | 'single_ui'

export function SingleGeneratePanel({ pricing, loading, token, onSubmit }: Props) {
  const { text } = useI18n()
  const [jobType, setJobType] = useState<JobType>('asset')
  const [assetName, setAssetName] = useState(() => text('冰霜之心', 'Frost Heart'))
  const [assetKind, setAssetKind] = useState<AssetKindChoice>('item_icon')
  const [subjectKind, setSubjectKind] = useState<SubjectKindChoice>('single_prop')
  const [assetExtraPrompt, setAssetExtraPrompt] = useState('')
  const [prompt, setPrompt] = useState(() => text('一枚幻想 RPG 魔法药水图标，居中构图，轮廓清晰，透明背景', 'A fantasy RPG magic potion icon, centered composition, clear silhouette, transparent background'))
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(12)
  const [removeBg, setRemoveBg] = useState(true)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('outline')
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
    if (jobType === 'asset') { setPixelSize('16x16'); setColors(12); setRemoveBg(true); setEdgeStyle('outline') }
    else if (jobType === 'sprite_sheet') { setPixelSize('64x64'); setColors(16); setRemoveBg(false) }
    else { setPixelSize('128x128'); setColors(16); setRemoveBg(true) }
  }, [jobType])

  async function uploadFile(file: File | undefined) {
    if (!file) return
    setUploading(true); setUploadMessage(text('上传中…', 'Uploading…'))
    try {
      const uploaded = await api.uploadImage(token, file)
      setInputImagePath(uploaded.path); setUploadUrl(uploaded.url ?? ''); setUploadMessage(text('图片已上传，可继续提交任务。', 'Image uploaded. You can submit the job now.'))
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : text('上传失败', 'Upload failed'))
    } finally { setUploading(false) }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const edge = edgeStylePixelize(edgeStyle)
    if (isAsset) {
      await onSubmit({ job_type: 'asset', prompt: assetName.trim(), input_image_path: null, client_request_id: crypto.randomUUID(), pixelize: buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }), grid: buildGridDesign(), asset: { name: assetName.trim(), extra_prompt: assetExtraPrompt.trim(), asset_kind: assetKind, subject_kind: subjectKind, no_preview: false } })
      return
    }
    await onSubmit({ job_type: jobType, prompt: needsPrompt ? prompt : null, input_image_path: needsImage ? inputImagePath : null, client_request_id: crypto.randomUUID(), skip_vl: skipVl, pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: isSprite ? false : removeBg, ...edge }), grid: buildGridDesign(), sprite: isSprite ? { duration_ms: durationMs, loop: 0, rows: 3, cols: 3 } : undefined })
  }

  return (
      <PixPanel eyebrow={text('单张试做', 'Single test')} title={text('任务配方', 'Job recipe')} action={<Badge variant="info">{text(`预计 ${price} 点`, `Estimated ${price} credits`)}</Badge>}>
      <form className="grid gap-5" onSubmit={submit}>
        <PixField label={text('模式', 'Mode')}>
          <Select value={jobType} onValueChange={(value) => setJobType(value as JobType)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="asset">{text('游戏素材直出', 'Game asset output')}</SelectItem>
              <SelectItem value="text_to_image">{text('文生图', 'Text to image')}</SelectItem>
              <SelectItem value="image_to_image">{text('图生图 / AI 微调', 'Image to image / AI tune')}</SelectItem>
              <SelectItem value="sprite_sheet">{text('九宫格动画精灵表', '3×3 animated sprite sheet')}</SelectItem>
              <SelectItem value="local_pixelize">{text('本地像素化', 'Local pixelize')}</SelectItem>
            </SelectContent>
          </Select>
        </PixField>

        {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <PixField label={text('素材类型', 'Asset type')}>
              <Select value={assetKind} onValueChange={(value) => setAssetKind(value as AssetKindChoice)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="item_icon">{text('物品图标', 'Item icon')}</SelectItem>
                  <SelectItem value="ui_component">{text('UI 组件', 'UI component')}</SelectItem>
                </SelectContent>
              </Select>
            </PixField>
            <PixField label={text('主体类型', 'Subject type')}>
              <Select value={subjectKind} onValueChange={(value) => setSubjectKind(value as SubjectKindChoice)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="single_prop">{text('单个道具', 'Single prop')}</SelectItem>
                  <SelectItem value="single_ui">{text('单个 UI', 'Single UI')}</SelectItem>
                </SelectContent>
              </Select>
            </PixField>
          </div>
          <PixField label={text('主体', 'Subject')} hint={text('只填写“主体：”后面的内容，系统会按尺寸和类型自动拼完整 prompt。', 'Only enter the content after “Subject:”; the system builds the full prompt from size and type.')}><Input value={assetName} placeholder={text('例如：冰霜之心', 'e.g. Frost Heart')} onChange={(e) => setAssetName(e.target.value)} /></PixField>
          <PixField label={text('额外风格描述（可选）', 'Extra style notes (optional)')}><Textarea value={assetExtraPrompt} rows={3} placeholder={text('可留空；如需补充材质、颜色或题材风格再填写。', 'Optional; add material, color, or theme notes if needed.')} onChange={(e) => setAssetExtraPrompt(e.target.value)} /></PixField>
        </div>}
        {needsPrompt && <PixField label={text('素材描述', 'Asset description')} hint={text('写清主体、材质和用途。', 'Describe the subject, material, and use case clearly.')}><Textarea value={prompt} rows={5} onChange={(e) => setPrompt(e.target.value)} /></PixField>}
        {needsImage && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? text('上传中…', 'Uploading…') : text('上传图片', 'Upload image')}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => void uploadFile(event.currentTarget.files?.[0])} /></label></Button>{uploadMessage && <Alert variant={uploadMessage.includes('失败') ? 'destructive' : 'info'}>{uploadMessage}</Alert>}<PixPreviewFrame url={uploadUrl} loading={uploading} label={uploading ? text('上传中…', 'Uploading…') : text('等待上传预览', 'Waiting for upload preview')} /></div>}

        <PixelControls pixelLabel={isSprite ? text('单帧尺寸', 'Frame size') : text('像素尺寸', 'Pixel size')} pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={isSprite || !removeBg} />
        {isSprite && <PixField label={text('GIF 帧间隔(ms)', 'GIF frame interval (ms)')}><Input type="number" value={durationMs} onChange={(e) => setDurationMs(Number(e.target.value))} /></PixField>}
        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={removeBg} disabled={isSprite} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{text('透明背景', 'Transparent background')}</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={isSprite || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? text('素材直出默认视觉理解策略', 'Default vision policy for asset output') : text('跳过参考图理解', 'Skip reference understanding')}</label></div>
        {invalidSubAssetSize && <Alert variant="destructive">{text('素材最低支持 16×16。', 'Minimum asset size is 16×16.')}</Alert>}
        {isAsset && <Alert variant="info">{text('素材直出只需要填写主体；系统会按所选尺寸、素材类型和主体类型拼接像素游戏素材模板。', 'Asset output only needs a subject; the system builds the pixel-game asset prompt from size, asset type, and subject type.')}</Alert>}
        <Button type="submit" size="lg" disabled={loading || submitBlocked}>{loading ? text('提交中…', 'Submitting…') : isSprite ? text('生成动画精灵表', 'Generate animated sprite sheet') : isAsset ? text('生成游戏素材', 'Generate game asset') : text('生成单张素材', 'Generate single asset')}</Button>
      </form>
    </PixPanel>
  )
}
