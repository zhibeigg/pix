import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useI18n } from '../i18n'
import { useConfirm } from './ConfirmDialog'
import type { CreditBalance, ImageModelInfo, ImageModelsResponse, JobCreateRequest, PricingDiscount, PricingRule, StyleProfile, TextureKind, UploadResponse } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, edgeStylePixelize, hasInvalidSubAssetSize, parsePixelSize, type EdgeStyleChoice } from '../pixelize'
import { promptLimitsFromModels } from '../lib/promptLimits'
import { validateImageFile, imageValidationMessage } from '../lib/upload'
import { ImageDropzone } from './ImageDropzone'
import { applyDiscount, discountPercentOff, discountZhe } from '../lib/pricing'
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
import { PromptPreviewDialog } from './PromptPreviewDialog'
import { SizeRetryControls, DEFAULT_SIZE_RETRY, type SizeRetryState } from './SizeRetryControls'
import { StyleProfileControls, compactStyleProfile } from './StyleProfileControls'

type BatchMode = 'asset' | 'local_pixelize'
type AssetKindChoice = 'item_icon' | 'ui_component' | 'tile_texture' | 'game_logo' | 'character'
type BatchUpload = { id: string; status: 'uploading' | 'uploaded' | 'failed'; error?: string; upload?: UploadResponse }
type Props = { pricing: PricingRule[]; discount?: PricingDiscount | null; balance: CreditBalance | null; loading: boolean; token: string; imageModels: ImageModelsResponse; onSubmitMany: (payloads: JobCreateRequest[], batchName: string, mode: string) => Promise<void> }

const LOGO_SIZE_OPTIONS = ['64x32', '96x48', '128x64', '192x96', '256x128']
const UI_COMPONENT_IMAGE_SIZE = 'auto'
const TEXTURE_KIND_VALUES: TextureKind[] = [
  'auto',
  'generic_texture',
  'terrain_ground',
  'path_floor',
  'wall_surface',
  'wood_planks',
  'water_liquid',
  'foliage_canopy',
  'roof_tile',
  'metal_panel',
  'fabric_carpet',
]

function modelItems(imageModels: ImageModelsResponse): ImageModelInfo[] {
  const byId = new Map((imageModels.items ?? []).map((item) => [item.id, item]))
  return imageModels.models.map((id) => byId.get(id) ?? {
    id,
    label: id,
    providers: [],
    operations: ['text_to_image', 'image_to_image'],
    sizes: [],
    qualities: [],
    output_formats: [],
    protocols: [],
    provider_count: 0,
  })
}

function modelOptionLabel(model: ImageModelInfo) {
  return model.label || model.id
}

export function BatchGeneratePanel({ pricing, discount, balance, loading, token, imageModels, onSubmitMany }: Props) {
  const { t } = useTranslation()
  const { text, isEnglish } = useI18n()
  const confirm = useConfirm()
  const [batchMode, setBatchMode] = useState<BatchMode>('asset')
  const [imageModel, setImageModel] = useState(imageModels.default)
  const promptLimits = useMemo(() => promptLimitsFromModels(imageModels), [imageModels])
  const maxUploadBytes = promptLimits.max_upload_bytes ?? 10 * 1024 * 1024
  const availableImageModels = useMemo(() => modelItems(imageModels), [imageModels])
  const [prompts, setPrompts] = useState(() => t('batchForm.defaults.prompts'))
  const [assetKind, setAssetKind] = useState<AssetKindChoice>('item_icon')
  const [textureKind, setTextureKind] = useState<TextureKind>('auto')
  const [uploads, setUploads] = useState<BatchUpload[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [pixelSize, setPixelSize] = useState('16x16')
  const [colors, setColors] = useState(12)
  const [removeBg, setRemoveBg] = useState(true)
  const [edgeStyle, setEdgeStyle] = useState<EdgeStyleChoice>('outline')
  const [skipVl, setSkipVl] = useState(false)
  // 角色三视图：默认生成正/侧/背横向三视图拼合图（画布横向 3 倍宽）；可关闭回落单张角色。
  const [characterThreeView, setCharacterThreeView] = useState(true)
  const [sizeRetry, setSizeRetry] = useState<SizeRetryState>(DEFAULT_SIZE_RETRY)
  const [styleProfile, setStyleProfile] = useState<StyleProfile>({})

  const lines = useMemo(() => prompts.split('\n').map((line) => line.trim()).filter(Boolean), [prompts])
  const assetSubjectMaxLength = promptLimits.asset_subject_max_chars
  const overlongSubject = lines.find((line) => line.length > assetSubjectMaxLength) ?? ''
  const uploaded = uploads.filter((item) => item.status === 'uploaded' && item.upload)
  const unitPrice = pricing.find((item) => item.key === batchMode)?.price_credits ?? 0
  const discountedUnit = applyDiscount(unitPrice, discount)
  const taskCount = batchMode === 'asset' ? lines.length : uploaded.length
  const totalPrice = taskCount * discountedUnit
  const originalTotalPrice = taskCount * unitPrice
  const discountActive = !!discount?.active && discountedUnit < unitPrice
  const availableCredits = balance?.available_credits ?? null
  const insufficientCredits = availableCredits !== null && totalPrice > availableCredits
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)
  const isAsset = batchMode === 'asset'
  const isTileAsset = isAsset && assetKind === 'tile_texture'
  const isLogoAsset = isAsset && assetKind === 'game_logo'
  const isCharacterAsset = isAsset && assetKind === 'character'
  const subjectKind = assetKind === 'ui_component' ? 'single_ui' : assetKind === 'tile_texture' ? 'tileable_pattern' : assetKind === 'game_logo' ? 'logo_mark' : assetKind === 'character' ? 'single_character' : 'single_prop'
  const uiComponentImageSize = assetKind === 'ui_component' ? UI_COMPONENT_IMAGE_SIZE : undefined
  const assetSubjectsLabel = isLogoAsset ? t('batchForm.logoSubjects') : isTileAsset ? t('batchForm.textureSubjects') : isCharacterAsset ? t('batchForm.characterSubjects') : t('batchForm.assetSubjects')
  const assetSubjectPlaceholder = isLogoAsset ? t('batchForm.logoSubjectPlaceholder') : isTileAsset ? t('batchForm.textureSubjectPlaceholder') : isCharacterAsset ? t('batchForm.characterSubjectPlaceholder') : t('batchForm.assetSubjectPlaceholder')

  useEffect(() => {
    if (!availableImageModels.some((item) => item.id === imageModel)) {
      setImageModel(imageModels.default || availableImageModels[0]?.id || 'image2')
    }
  }, [availableImageModels, imageModel, imageModels.default])

  useEffect(() => {
    if (batchMode === 'asset') { setPixelSize('16x16'); setColors(8); setRemoveBg(true); setEdgeStyle('hard') }
    else { setPixelSize('64x64'); setColors(16); setRemoveBg(true) }
  }, [batchMode])

  useEffect(() => {
    if (batchMode !== 'asset') return
    if (assetKind === 'tile_texture') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(false); setEdgeStyle('hard'); setTextureKind('auto')
    } else if (assetKind === 'game_logo') {
      setPixelSize('128x64'); setColors(24); setRemoveBg(true); setEdgeStyle('hard')
    } else if (assetKind === 'character') {
      setPixelSize('64x64'); setColors(32); setRemoveBg(true); setEdgeStyle('hard')
    } else if (assetKind === 'item_icon') {
      setPixelSize('16x16'); setColors(8); setRemoveBg(true); setEdgeStyle('hard')
    } else if (assetKind === 'ui_component') {
      setPixelSize('32x32'); setColors(12); setRemoveBg(true); setEdgeStyle('outline')
    }
  }, [assetKind, batchMode])

  async function uploadFiles(files: File[]) {
    if (!files.length) return
    setUploading(true)
    const selected = files
    const items = selected.map(() => ({ id: crypto.randomUUID(), status: 'uploading' as const }))
    setUploads(items)
    const results = await Promise.allSettled(selected.map(async (file, index) => {
      try {
        const upload = await api.uploadImage(token, file)
        return { index, upload } as const
      } catch {
        throw { index } as const
      }
    }))
    const next: BatchUpload[] = items.map((item, index) => {
      const result = results[index]
      if (result.status === 'fulfilled') return { ...item, status: 'uploaded', upload: result.value.upload }
      return { ...item, status: 'failed', error: t('batchForm.uploadFailed') }
    })
    setUploads(next)
    setUploading(false)
  }

  function buildAssetPayload(name: string, clientRequestId: string = crypto.randomUUID()): JobCreateRequest {
    const edge = edgeStylePixelize(edgeStyle)
    const pixelize = buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge })
    const grid = buildGridDesign()
    const modelOverride = imageModel !== imageModels.default ? imageModel : undefined
    const styleProfilePayload = compactStyleProfile(styleProfile)
    const styleProfileFields = styleProfilePayload ? { style_profile: styleProfilePayload } : {}
    const sizeRetryFields = sizeRetry.enabled
      ? {
          size_retry_enabled: true,
          size_retry_mode: sizeRetry.mode,
          size_retry_max_attempts: sizeRetry.maxAttempts,
          size_retry_max_credits: sizeRetry.maxCredits,
        }
      : {}
    return { job_type: 'asset', prompt: name, input_image_path: null, client_request_id: clientRequestId, image_size: uiComponentImageSize, image_model: modelOverride, ...sizeRetryFields, ...styleProfileFields, pixelize, grid, asset: { name, asset_kind: assetKind, subject_kind: subjectKind, texture_kind: isTileAsset ? textureKind : undefined, character_views: isCharacterAsset ? (characterThreeView ? 'three_view' : 'single') : undefined, no_preview: false } }
  }

  function buildBatchPreviewPayload(): JobCreateRequest | null {
    if (!isAsset || overlongSubject || invalidSubAssetSize) return null
    const name = lines[0] || (isLogoAsset ? t('batchForm.logoSubjectPlaceholder') : isTileAsset ? t('batchForm.textureSubjectPlaceholder') : isCharacterAsset ? t('batchForm.characterSubjectPlaceholder') : t('batchForm.assetSubjectPlaceholder'))
    return buildAssetPayload(name, 'prompt-preview')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (overlongSubject) return
    const edge = edgeStylePixelize(edgeStyle)
    const pixelize = isAsset ? buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge }) : buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg, ...edge })
    const grid = buildGridDesign()
    let payloads: JobCreateRequest[] = []
    if (batchMode === 'asset') payloads = lines.map((name) => buildAssetPayload(name))
    else payloads = uploaded.map((item) => ({ job_type: 'local_pixelize', prompt: null, input_image_path: item.upload?.path ?? null, client_request_id: crypto.randomUUID(), skip_vl: true, pixelize, grid }))
    if (payloads.length >= 10 && !(await confirm({ title: t('batchForm.title'), description: t('batchForm.confirmQueue', { count: payloads.length, total: totalPrice }), confirmText: t('common.confirm') }))) return
    await onSubmitMany(payloads, '', batchMode)
  }

  return (
    <PixPanel eyebrow={t('batchForm.eyebrow')} title={t('batchForm.title')} description={t('batchForm.description')} action={(
      <div className="flex flex-wrap items-center gap-2">
        {/* Batch 价格走 i18next 插值 key（taskBadge），无法塞进 EstimateBadge 的 text(zh,en) 结构，
            因此这里复用已折后的 total，并在旁边单独渲染折扣标签 + 原价划线。 */}
        <Badge variant={insufficientCredits ? 'danger' : 'info'}>{t('batchForm.taskBadge', { count: taskCount, total: totalPrice })}</Badge>
        {discountActive && (
          <span className="inline-flex items-center gap-1 text-xs">
            <span className="font-semibold text-amber-600">{(discount?.label || '').trim() || text(`${discountZhe(discount?.rate ?? 1)} 折`, `${discountPercentOff(discount?.rate ?? 1)}% OFF`)}</span>
            <del className="opacity-60">{text(`${originalTotalPrice} 点`, `${originalTotalPrice} credits`)}</del>
          </span>
        )}
      </div>
    )}>
      <form className="grid gap-5" onSubmit={submit}>
        <BatchCostSummary taskCount={taskCount} unitPrice={discountedUnit} totalPrice={totalPrice} availableCredits={availableCredits} insufficientCredits={insufficientCredits} />
        <PixField label={t('batchForm.typeLabel')}><Select value={batchMode} onValueChange={(value) => setBatchMode(value as BatchMode)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="asset">{t('batchForm.types.asset')}</SelectItem><SelectItem value="local_pixelize">{t('batchForm.types.local_pixelize')}</SelectItem></SelectContent></Select></PixField>
        {batchMode === 'asset' && <PixField label={text('生图模型', 'Image model')}><Select value={imageModel} onValueChange={setImageModel}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{availableImageModels.map((m) => <SelectItem value={m.id} key={m.id}>{modelOptionLabel(m)}</SelectItem>)}</SelectContent></Select></PixField>}
        {batchMode === 'asset' ? <div className="grid gap-4">
          {isAsset && <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4">
            <PixField label={t('batchForm.assetKindLabel')}><Select value={assetKind} onValueChange={(value) => setAssetKind(value as AssetKindChoice)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="item_icon">{t('batchForm.assetKinds.item_icon')}</SelectItem><SelectItem value="ui_component">{t('batchForm.assetKinds.ui_component')}</SelectItem><SelectItem value="tile_texture">{t('batchForm.assetKinds.tile_texture')}</SelectItem><SelectItem value="game_logo">{t('batchForm.assetKinds.game_logo')}</SelectItem><SelectItem value="character">{t('batchForm.assetKinds.character')}</SelectItem></SelectContent></Select></PixField>
            {isTileAsset && <PixField label={t('batchForm.textureKindLabel')} hint={t('batchForm.textureKindHint')}><Select value={textureKind} onValueChange={(value) => setTextureKind(value as TextureKind)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{TEXTURE_KIND_VALUES.map((value) => <SelectItem key={value} value={value}>{t(`batchForm.textureKinds.${value}`)}</SelectItem>)}</SelectContent></Select></PixField>}
            {isCharacterAsset && <Alert variant="info">{t('batchForm.characterAutoSaveHint')}</Alert>}
            {isCharacterAsset && (
              <label className="flex items-start gap-2 rounded-lg border border-border bg-background/45 p-3 text-sm">
                <Checkbox checked={characterThreeView} onCheckedChange={(value) => setCharacterThreeView(Boolean(value))} />
                <span className="grid gap-1">
                  <span className="font-medium">{t('batchForm.characterThreeViewLabel')}</span>
                  <span className="text-xs text-muted-foreground">{t('batchForm.characterThreeViewHint')}</span>
                </span>
              </label>
            )}
          </div>}
          <PixField label={assetSubjectsLabel} hint={text(`每行最多 ${assetSubjectMaxLength} 字。`, `Up to ${assetSubjectMaxLength} characters per line.`)}><Textarea value={prompts} rows={8} placeholder={assetSubjectPlaceholder} onChange={(e) => setPrompts(e.target.value)} /></PixField>
          <StyleProfileControls value={styleProfile} onChange={setStyleProfile} />
        </div> : <div className="grid gap-4 rounded-lg border border-border bg-muted/45 p-4"><ImageDropzone maxBytes={maxUploadBytes} multiple disabled={uploading} label={uploading ? t('batchForm.uploading') : t('batchForm.uploadImages')} ariaLabel={t('batchForm.uploadImages')} onFiles={(files) => { setUploadError(''); void uploadFiles(files) }} onError={(message) => setUploadError(message)} />{uploadError && <Alert variant="destructive">{uploadError}</Alert>}<UploadList uploads={uploads} /></div>}
        <PixelControls pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} sizeOptions={isLogoAsset ? LOGO_SIZE_OPTIONS : undefined} edgeStyle={edgeStyle} onEdgeStyleChange={setEdgeStyle} edgeStyleDisabled={isTileAsset || !removeBg} />
        {isAsset && !isTileAsset && !isLogoAsset && <SizeRetryControls value={sizeRetry} onChange={setSizeRetry} basePrice={unitPrice} discount={discount} imageSize={pixelSize} />}
        <div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><Checkbox checked={isTileAsset ? false : removeBg} disabled={isTileAsset} onCheckedChange={(v) => setRemoveBg(Boolean(v))} />{t('batchForm.transparentBackground')}</label><label className="flex items-center gap-2"><Checkbox checked={skipVl} disabled={batchMode === 'local_pixelize' || isAsset} onCheckedChange={(v) => setSkipVl(Boolean(v))} />{isAsset ? t('batchForm.defaultVisionPolicy') : t('batchForm.skipReference')}</label></div>
        {invalidSubAssetSize && <Alert variant="destructive">{t('batchForm.minSize')}</Alert>}
        {overlongSubject && <Alert variant="destructive">{text(`存在超过 ${assetSubjectMaxLength} 字的主体描述：${overlongSubject.slice(0, 32)}…`, `One subject exceeds ${assetSubjectMaxLength} characters: ${overlongSubject.slice(0, 32)}…`)}</Alert>}
        {insufficientCredits && <Button type="button" variant="outline" onClick={() => { window.location.hash = '/billing' }}>{t('batchForm.insufficient')}</Button>}
        <div className="flex flex-wrap items-center gap-3">
          {isAsset && <PromptPreviewDialog token={token} buildPayload={buildBatchPreviewPayload} disabled={invalidSubAssetSize || Boolean(overlongSubject)} label={text('预览示例 Prompt', 'Preview sample prompt')} />}
          <Button type="submit" size="lg" disabled={loading || uploading || taskCount === 0 || insufficientCredits || invalidSubAssetSize || Boolean(overlongSubject)}>{loading ? t('batchForm.submitting') : t('batchForm.submit', { count: taskCount })}</Button>
        </div>
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
