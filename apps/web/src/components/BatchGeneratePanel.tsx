import { FormEvent, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api'
import { notionTokens } from '../theme'
import type { JobCreateRequest, PricingRule, UploadResponse } from '../types'
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
    <Card variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ height: 8, bgcolor: notionTokens.tintMint }} />
      <CardContent>
        <Stack spacing={3}>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' }, gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>Batch</Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>批量生产</Typography>
            </Box>
            <Chip sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} label={`${taskCount} 个 · 预计 ${totalPrice} credits`} />
          </Stack>

          <Stack component="form" spacing={2.5} onSubmit={submit}>
            <TextField label="素材包名称" value={batchName} placeholder="例如：RPG 材料包" onChange={(event) => setBatchName(event.target.value)} />
            <TextField select label="批量类型" value={batchMode} onChange={(event) => setBatchMode(event.target.value as BatchMode)}>
              <MenuItem value="text_to_image">批量文生图</MenuItem>
              <MenuItem value="image_to_image">批量图生图</MenuItem>
              <MenuItem value="local_pixelize">批量本地像素化</MenuItem>
            </TextField>

            {batchMode === 'text_to_image' ? (
              <TextField label="批量 Prompt（每行一个素材）" value={prompts} multiline minRows={8} onChange={(event) => setPrompts(event.target.value)} />
            ) : (
              <Card variant="outlined" sx={{ bgcolor: notionTokens.tintSky }}>
                <CardContent>
                  <Stack spacing={2}>
                    {batchMode === 'image_to_image' && (
                      <TextField label="共用 AI 微调描述" value={sharedPrompt} multiline minRows={4} onChange={(event) => setSharedPrompt(event.target.value)} />
                    )}
                    <Button variant="outlined" component="label" disabled={uploading}>
                      {uploading ? '上传中…' : '批量上传图片'}
                      <Box component="input" type="file" multiple accept="image/png,image/jpeg,image/webp" sx={{ display: 'none' }} onChange={(event) => uploadFiles(event.currentTarget.files)} />
                    </Button>
                    <UploadList uploads={uploads} />
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
              <FormControlLabel control={<Checkbox checked={skipVl} disabled={batchMode === 'local_pixelize'} onChange={(event) => setSkipVl(event.target.checked)} />} label="跳过 VL 分析" />
            </Stack>
            <Button type="submit" variant="contained" color="primary" disabled={loading || uploading || taskCount === 0}>{loading ? '提交中…' : `批量入队 ${taskCount} 个任务`}</Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}

function UploadList({ uploads }: { uploads: BatchUpload[] }) {
  if (uploads.length === 0) return <Alert severity="info">选择多张图片后会先上传，再批量创建任务。</Alert>
  const ok = uploads.filter((item) => item.status === 'uploaded').length
  const failed = uploads.filter((item) => item.status === 'failed').length
  return (
    <Stack spacing={1.25}>
      <Alert severity={failed ? 'warning' : 'success'}>已上传 {ok} / {uploads.length}{failed ? `，失败 ${failed}` : ''}</Alert>
      {uploads.map((item) => (
        <Card variant="outlined" key={item.id} sx={{ bgcolor: 'background.paper' }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Stack direction="row" sx={{ gap: 1.5, alignItems: 'center' }}>
              {item.upload?.url ? (
                <Box component="img" src={item.upload.url} alt={item.name} loading="lazy" decoding="async" sx={{ width: 58, height: 58, objectFit: 'contain', imageRendering: 'pixelated', borderRadius: 1.5, bgcolor: 'background.default' }} />
              ) : (
                <Box sx={{ width: 58, height: 58, display: 'grid', placeItems: 'center', borderRadius: 1.5, bgcolor: 'background.default' }}>
                  <Typography variant="caption" color="text.secondary">{item.status}</Typography>
                </Box>
              )}
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600 }} noWrap>{item.name}</Typography>
                <Typography variant="body2" color="text.secondary" noWrap>{item.error || item.upload?.path || item.status}</Typography>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      ))}
    </Stack>
  )
}
