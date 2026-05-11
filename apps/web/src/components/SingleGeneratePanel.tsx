import { FormEvent, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api'
import { notionTokens } from '../theme'
import type { JobCreateRequest, JobType, PricingRule } from '../types'
import { buildGridDesign, buildPixelize, hasInvalidSub16Size, isEightPixelSize, parsePixelSize } from '../pixelize'

type SingleGeneratePanelProps = {
  pricing: PricingRule[]
  loading: boolean
  token: string
  onSubmit: (payload: JobCreateRequest) => Promise<void>
}

export function SingleGeneratePanel({ pricing, loading, token, onSubmit }: SingleGeneratePanelProps) {
  const [jobType, setJobType] = useState<JobType>('text_to_image')
  const [prompt, setPrompt] = useState('一枚幻想 RPG 魔法药水图标，居中构图，轮廓清晰，透明背景')
  const [inputImagePath, setInputImagePath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [skipVl, setSkipVl] = useState(false)
  const [aiGrid, setAiGrid] = useState(false)

  const price = useMemo(() => pricing.find((item) => item.key === jobType)?.price_credits ?? 0, [pricing, jobType])
  const parsedPixelSize = parsePixelSize(pixelSize)
  const forceAiGrid = isEightPixelSize(parsedPixelSize)
  const invalidSub16Size = hasInvalidSub16Size(parsedPixelSize)
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
      pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }),
      grid: buildGridDesign(aiGrid, parsedPixelSize),
    })
  }

  return (
    <Card variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ height: 8, bgcolor: notionTokens.tintYellowBold }} />
      <CardContent>
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
              <MenuItem value="text_to_image">文生图</MenuItem>
              <MenuItem value="image_to_image">图生图 / AI 微调</MenuItem>
              <MenuItem value="local_pixelize">本地像素化</MenuItem>
            </TextField>

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

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
              <TextField label="像素尺寸" value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} />
              <TextField label="颜色数" type="number" value={colors} onChange={(event) => setColors(Number(event.target.value))} />
            </Box>
            <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
              <FormControlLabel control={<Checkbox checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />} label="透明背景" />
              <FormControlLabel control={<Checkbox checked={skipVl} onChange={(event) => setSkipVl(event.target.checked)} />} label="跳过参考图理解" />
              <FormControlLabel control={<Checkbox checked={forceAiGrid || aiGrid} disabled={forceAiGrid} onChange={(event) => setAiGrid(event.target.checked)} />} label="AI 低像素工程图" />
            </Stack>
            {invalidSub16Size && <Alert severity="error">16×16 以下仅支持 8×8；8×8 会自动使用 AI 低像素工程图。</Alert>}
            {forceAiGrid && <Alert severity="info">8×8 会强制使用 AI 低像素工程图，失败时不回退到 Python extract。</Alert>}
            {(forceAiGrid || aiGrid) && <Alert severity="warning">AI 低像素工程图会额外调用视觉模型生成并返修像素矩阵；默认点数价格不变，但会产生额外模型调用成本。</Alert>}
            <Button type="submit" variant="contained" disabled={loading || invalidSub16Size}>{loading ? '提交中…' : '生成单张素材'}</Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}
