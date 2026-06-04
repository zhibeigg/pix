import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { CreditBalance, JobCreateRequest, PricingRule, UploadResponse } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, parsePixelSize, type EdgeStyleChoice } from '../pixelize'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { PixField } from './pix/PixField'
import { PixPanel } from './pix/PixPanel'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { PixelControls } from './PixelControls'

type BatchMode = 'asset' | 'local_pixelize'
type AssetKindChoice = 'item_icon' | 'ui_component' | 'tile_texture' | 'game_logo'
type BatchUpload = { id: string; status: 'uploading' | 'uploaded' | 'failed'; error?: string; upload?: UploadResponse }
type Props = { pricing: PricingRule[]; balance: CreditBalance | null; loading: boolean; token: string; onSubmitMany: (payloads: JobCreateRequest[], batchName: string, mode: string) => Promise<void> }

const PROMPT_MAX_LENGTH = 3000
const LOGO_SIZE_OPTIONS = ['64x32', '96x48', '128x64', '192x96', '256x128']

export function BatchGeneratePanel({ pricing, balance, loading, token, onSubmitMany }: Props) {
  const { t } = useTranslation()
  const [batchMode, setBatchMode] = useState<BatchMode>('asset')
  const [prompts, setPrompts] = useState(() => t('batchForm.defaults.prompts'))
  const [assetKind, setAssetKind] = useState<AssetKindChoice>('item_icon')
  const [assetExtraPrompt, setAssetExtraPrompt] = useState(() => t('batchForm.defaults.assetExtraPrompt'))
  const [uploads, setUploads] = useState<BatchUpload[]>([])
  const [uploading, setUploading] = useState(false)
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(12)
  const [removeBg, setRemoveBg] = useState(true)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('outline')
  const [skipVl, setSkipVl] = useState(false)

  const lines = useMemo(() => prompts.split('\n').map((line) => line.trim()).filter(Boolean), [prompts])
  const uploaded = uploads.filter((item) => item.status === 'uploaded' && item.upload)
  const unitPrice = pricing.find((item) => item.key === batchMode)?.price_credits ?? 0
  const taskCount = batchMode === 'asset' ? lines.length : uploaded.length
  const totalPrice = taskCount * unitPrice
  const availableCredits = balance?.available_credits ?? null
  const insufficientCredits = availableCredits !== null && totalPrice > availableCredits
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const isAsset = batchMode === 'asset'
  const isTileAsset = isAsset && assetKind === 'tile_texture'
  const isLogoAsset = isAsset && assetKind === 'game_logo'
  const subjectKind = assetKind === 'ui_component' ? 'single_ui' : assetKind === 'tile_texture' ? 'tileable_pattern' : assetKind === 'game_logo' ? 'logo_mark' : 'single_prop'
  const assetSubjectsLabel = isLogoAsset ? t('batchForm.logoSubjects') : isTileAsset ? t('batchForm.textureSubjects') : t('batchForm.assetSubjects')
  const assetSubjectPlaceholder = isLogoAsset ? t('batchForm.logoSubjectPlaceholder') : isTileAsset ? t('batchForm.textureSubjectPlaceholder') : t('batchForm.assetSubjectPlaceholder')

  useEffect(() => {
    if (batchMode === 'asset') { setPixelSize('16x16'); setColors(12); setRemoveBg(true); setEdgeStyle('outline') }
    else { setPixelSize('64x64'); setColors(16); setRemoveBg(true) }
  }, [batchMode])

  useEffect(() => {
    if (batchMode !== 'asset') return
    if (assetKind === 'tile_texture') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(false); setEdgeStyle('hard')
    } else if (assetKind === 'game_logo') {
      setPixelSize('128x64'); setColors(24); setRemoveBg(true); setEdgeStyle('hard')
    } else if (assetKind === 'item_icon') {
      setPixelSize('16x16'); setColors(12); setRemoveBg(true); setEdgeStyle('outline')
    } else if (assetKind === 'ui_component') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(true); setEdgeStyle('outline')
    }
  }, [assetKind, batchMode])

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    const selected = Array.from(files)
    const initial = selected.map(() => ({ id: crypto.randomUUID(), status: 'uploading' as const }))
    setUploads(initial)
    const next: BatchUpload[] = []
    for (const [index, file] of selected.entries()) {
      const current = initial[index]
      try { next.push({ ...current, status: 'uploaded', upload: await api.uploadImage(token, file) }) }
      catch { next.push({ ...current, status: 'failed', error: t('batchForm.uploadFailed') }) }
      setUploads([...next, ...initial.slice(index + 1)])
    }
    setUploading(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const edge = edgeStylePixelize(edgeStyle)
    const pixelize = isAsset ? buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }) : buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge })
    const grid = buildGridDesign()
    let payloads: JobCreateRequest[] = []
    if (batchMode === 'asset') payloads = lines.map((name) => ({ job_type: 'asset', prompt: name, input_image_path: null, client_request_id: crypto.randomUUID(), pixelize, grid, asset: { name, extra_prompt: assetExtraPrompt.trim(), asset_kind: assetKind, subject_kind: subjectKind, no_preview: false } }))
    else payloads = uploaded.map((item) => ({ job_type: 'local_pixelize', prompt: null, input_image_path: item.upload?.path ?? null, client_request_id: crypto.randomUUID(), skip_vl: true, pixelize, grid }))
    if (payloads.length >= 10 && !window.confirm(t('batchForm.confirmQueue', { count: payloads.length, total: totalPrice }))) return
    await onSubmitMany(payloads, '', batchMode)
  }

  return (
    <PixPanel eyebrow={t('batchForm.eyebrow')} title={t('batchForm.title')} description={t('batchForm.description')} action={<Badge variant={insufficientCredits ? 'danger' : 'info'}>{t('batchForm.taskBadge', { count: taskCount, total: totalPrice })}</Badge>}>
      <form className="grid gap-5" onSubmit={submit}>
        <BatchCostSummary taskCount={taskCount} unitPrice={unitPrice} totalPrice={totalPrice} availableCredits={availableCredits} insufficientCredits={insufficientCredits} />
        <PixField label={t('batchForm.typeLabel')}><Select value={batchMode} onValueChange={(value) => setBatchMode(value as BatchMode)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="asset">{t('batchForm.types.asset')}</SelectItem><SelectItem value="local_pixelize">{t('batchForm.types.local_pixelize')}</SelectItem></SelectContent></Select></PixField>
        {batchMode === 'asset' ? <div className="grid gap-4">
          {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
            <PixField label={t('batchForm.assetKindLabel')}><Select value={assetKind} onValueChange={(value) => setAssetKind(value as AssetKindChoice)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="item_icon">{t('batchForm.assetKinds.item_icon')}</SelectItem><SelectItem value="ui_component">{t('batchForm.assetKinds.ui_component')}</SelectItem><SelectItem value="tile_texture">{t('batchForm.assetKinds.tile_texture')}</SelectItem><SelectItem value="game_logo">{t('batchForm.assetKinds.game_logo')}</SelectItem></SelectContent></Select></PixField>
            <PixField label={t('batchForm.extraStyle')}><Textarea value={assetExtraPrompt} rows={3} maxLength={PROMPT_MAX_LENGTH} placeholder={t('batchForm.extraStylePlaceholder')} onChange={(e) => setAssetExtraPrompt(e.target.value)} /></PixField>
          </div>}
          <PixField label={assetSubjectsLabel}><Textarea value={prompts} rows={8} placeholder={assetSubjectPlaceholder} onChange={(e) => setPrompts(e.target.value)} /></PixField>
        </div> : <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><Button type="button" variant="outline" asChild><label className="cursor-pointer"><Upload />{uploading ? t('batchForm.uploading') : t('batchForm.uploadImages')}<input type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => void uploadFiles(e.currentTarget.files)} /></label></Button><UploadList uploads={uploads} /></div>}
        <PixelControls pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} sizeOptions={isLogoAsset ? LOGO_SIZE_OPTIONS : undefined} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={isTileAsset || !removeBg} />
        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={isTileAsset ? false : removeBg} disabled={isTileAsset} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{t('batchForm.transparentBackground')}</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={batchMode === 'local_pixelize' || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? t('batchForm.defaultVisionPolicy') : t('batchForm.skipReference')}</label></div>
        {invalidSubAssetSize && <Alert variant="destructive">{t('batchForm.minSize')}</Alert>}
        {insufficientCredits && <Button type="button" variant="outline" onClick={() => { window.location.hash = '/billing' }}>{t('batchForm.insufficient')}</Button>}
        <Button type="submit" size="lg" disabled={loading || uploading || taskCount === 0 || insufficientCredits || invalidSubAssetSize}>{loading ? t('batchForm.submitting') : t('batchForm.submit', { count: taskCount })}</Button>
      </form>
    </PixPanel>
  )
}

function BatchCostSummary({ taskCount, unitPrice, totalPrice, availableCredits, insufficientCredits }: { taskCount: number; unitPrice: number; totalPrice: number; availableCredits: number | null; insufficientCredits: boolean }) {
  const { t } = useTranslation()
  return <Alert variant={insufficientCredits ? 'warning' : 'info'}>{t('batchForm.costSummary', { count: taskCount, unit: unitPrice, total: totalPrice, available: availableCredits ?? '—' })}</Alert>
}

function UploadList({ uploads }: { uploads: BatchUpload[] }) {
  const { t } = useTranslation()
  if (!uploads.length) return <Alert variant="info">{t('batchForm.uploadEmpty')}</Alert>
  return <div className="grid gap-2">{uploads.map((item, index) => <div key={item.id} className="grid grid-cols-[64px_minmax(0,1fr)] gap-3 rounded-lg border border-border bg-card p-2">{item.upload?.url ? <img src={item.upload.url} alt={t('batchForm.uploadAlt', { index: index + 1 })} className="h-16 w-16 rounded-md object-contain [image-rendering:pixelated]" /> : <PixPreviewFrame className="min-h-16" label={t(`batchForm.status.${item.status}`)} loading={item.status === 'uploading'} />}<div className="min-w-0 self-center"><p className="truncate text-sm font-bold">{t('batchForm.imageNumber', { index: index + 1 })}</p><p className="truncate text-xs text-muted-foreground">{item.error || (item.status === 'uploaded' ? t('batchForm.uploaded') : t(`batchForm.status.${item.status}`))}</p></div></div>)}</div>
}
