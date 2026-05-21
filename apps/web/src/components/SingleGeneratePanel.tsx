import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api'
import { notionTokens } from '../theme'
import type { JobCreateRequest, JobType, PricingRule } from '../types'
import { buildAssetPixelize, buildGridDesign, buildPixelize, hasInvalidSubAssetSize, parsePixelSize } from '../pixelize'
import { PixelControls } from './PixelControls'

type SingleGeneratePanelProps = {
  pricing: PricingRule[]
  loading: boolean
  token: string
  onSubmit: (payload: JobCreateRequest) => Promise<void>
}

export function SingleGeneratePanel({ pricing, loading, token, onSubmit }: SingleGeneratePanelProps) {
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
    if (jobType === 'asset') {
      setPixelSize('16x16')
      setColors(12)
      setRemoveBg(true)
    } else if (jobType === 'sprite_sheet') {
      setPixelSize('64x64')
      setColors(16)
      setRemoveBg(false)
    } else {
      setPixelSize('128x128')
      setColors(16)
      setRemoveBg(true)
    }
  }, [jobType])

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
    if (isAsset) {
      await onSubmit({
        job_type: 'asset',
        prompt: assetName.trim(),
        input_image_path: null,
        client_request_id: crypto.randomUUID(),
        pixelize: buildAssetPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }),
        grid: buildGridDesign(),
        asset: { name: assetName.trim(), extra_prompt: assetExtraPrompt.trim(), no_preview: false },
      })
      return
    }
    await onSubmit({
      job_type: jobType,
      prompt: needsPrompt ? prompt : null,
      input_image_path: needsImage ? inputImagePath : null,
      client_request_id: crypto.randomUUID(),
      skip_vl: skipVl,
      pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: isSprite ? false : removeBg }),
      grid: buildGridDesign(),
      sprite: isSprite ? { duration_ms: durationMs, loop: 0, rows: 3, cols: 3 } : undefined,
    })
  }

  return (
    <Card variant="outlined" sx={{ overflow: 'hidden', bgcolor: notionTokens.canvas }}>
      <Box sx={{ height: 5, bgcolor: notionTokens.tintYellow }} />
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={3}>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' }, gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>单张试做</Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>单张素材试做</Typography>
            </Box>
            <Chip sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} label={`预计 ${price} 点`} />
          </Stack>

          <Stack component="form" spacing={2.5} onSubmit={submit}>
            <TextField select label="模式" value={jobType} onChange={(event) => setJobType(event.target.value as JobType)}>
              <MenuItem value="asset">游戏素材直出</MenuItem>
              <MenuItem value="text_to_image">文生图</MenuItem>
              <MenuItem value="image_to_image">图生图 / AI 微调</MenuItem>
              <MenuItem value="sprite_sheet">九宫格动画精灵表</MenuItem>
              <MenuItem value="local_pixelize">本地像素化</MenuItem>
            </TextField>

            {isAsset && (
              <Card variant="outlined" sx={{ bgcolor: notionTokens.tintCream }}>
                <CardContent>
                  <Stack spacing={2}>
                    <TextField label="素材名称" helperText="会注入 pix asset 的游戏物品 Prompt 模板。" value={assetName} onChange={(event) => setAssetName(event.target.value)} />
                    <TextField label="额外风格描述" helperText="可写材质、色彩或用途；留空则使用默认素材模板。" value={assetExtraPrompt} multiline minRows={3} onChange={(event) => setAssetExtraPrompt(event.target.value)} />
                  </Stack>
                </CardContent>
              </Card>
            )}

            {needsPrompt && (
              <TextField label="素材描述" helperText="写清主体、材质和用途。" value={prompt} multiline minRows={5} onChange={(event) => setPrompt(event.target.value)} />
            )}

            {needsImage && (
              <Card variant="outlined" sx={{ bgcolor: notionTokens.tintSky }}>
                <CardContent>
                  <Stack spacing={2}>
                    <Button variant="outlined" component="label" disabled={uploading}>
                      {uploading ? '上传中…' : '上传图片'}
                      <Box component="input" type="file" accept="image/png,image/jpeg,image/webp" sx={{ display: 'none' }} onChange={(event) => uploadFile(event.currentTarget.files?.[0])} />
                    </Button>
                    {uploadMessage && <Alert severity={uploadMessage.includes('失败') ? 'error' : 'info'}>{uploadMessage}</Alert>}
                    {uploadUrl && (
                      <Box component="img" src={uploadUrl} alt="上传预览" loading="lazy" decoding="async" sx={{ width: '100%', maxHeight: 220, objectFit: 'contain', imageRendering: 'pixelated', border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: 'background.paper', p: 1 }} />
                    )}
                    <TextField label="图片路径" value={inputImagePath} placeholder="上传后自动填充" onChange={(event) => setInputImagePath(event.target.value)} />
                  </Stack>
                </CardContent>
              </Card>
            )}

            <Stack spacing={2}>
              <PixelControls pixelLabel={isSprite ? '单帧尺寸' : '像素尺寸'} pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} />
              {isSprite && <TextField label="GIF 帧间隔(ms)" type="number" value={durationMs} onChange={(event) => setDurationMs(Number(event.target.value))} />}
            </Stack>
            <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
              <FormControlLabel control={<Checkbox checked={removeBg} disabled={isSprite} onChange={(event) => setRemoveBg(event.target.checked)} />} label="透明背景" />
              <FormControlLabel control={<Checkbox checked={skipVl} disabled={isSprite || isAsset} onChange={(event) => setSkipVl(event.target.checked)} />} label={isAsset ? '素材直出默认 VL 策略' : '跳过参考图理解'} />
            </Stack>
            {invalidSubAssetSize && <Alert severity="error">素材最低支持 16×16。</Alert>}
            {isAsset && <Alert severity="info">素材直出会按 CLI `pix asset` 策略使用白底单图模板、Pixel Grid 提取和透明 PNG 输出。</Alert>}
            <Button type="submit" variant="contained" disabled={loading || submitBlocked}>{loading ? '提交中…' : isSprite ? '生成动画精灵表' : isAsset ? '生成游戏素材' : '生成单张素材'}</Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}
