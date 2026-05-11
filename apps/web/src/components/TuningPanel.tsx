import { FormEvent, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, Stack, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'
import { buildPixelize, parsePixelSize, summarizePrompt } from '../pixelize'

type TuningPanelProps = {
  job: GenerationJob | null
  pricing: PricingRule[]
  loading: boolean
  onSubmit: (payload: JobCreateRequest) => Promise<void>
}

export function TuningPanel({ job, pricing, loading, onSubmit }: TuningPanelProps) {
  const [pixelSize, setPixelSize] = useState('128x128')
  const [colors, setColors] = useState(16)
  const [removeBg, setRemoveBg] = useState(true)
  const [aiPrompt, setAiPrompt] = useState('保留主体，优化材质和颜色')
  const aiPrice = useMemo(() => pricing.find((item) => item.key === 'image_to_image')?.price_credits ?? 0, [pricing])

  if (!job) {
    return (
      <Card variant="outlined" sx={{ bgcolor: notionTokens.tintLavender }}>
        <CardContent>
          <Stack spacing={1}>
            <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>微调工位</Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>选择作品进行微调</Typography>
            <Typography color="text.secondary">选择作品后可重新像素化或 AI 微调。</Typography>
          </Stack>
        </CardContent>
      </Card>
    )
  }

  const output = job.outputs[0]
  const sourcePath = output?.source_path || output?.pixelized_path || job.input_image_path || ''
  const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''

  async function submitLocal(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({
      job_type: 'repixelize',
      prompt: null,
      input_image_path: sourcePath,
      client_request_id: crypto.randomUUID(),
      skip_vl: true,
      pixelize: buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg }),
    })
  }

  async function submitAi(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({
      job_type: 'image_to_image',
      prompt: aiPrompt,
      input_image_path: sourcePath,
      client_request_id: crypto.randomUUID(),
      skip_vl: false,
      pixelize: buildPixelize({ output_size: parsePixelSize(pixelSize), colors, remove_bg: removeBg }),
    })
  }

  return (
    <Card variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ height: 8, bgcolor: notionTokens.tintLavender }} />
      <CardContent>
        <Stack spacing={2.5}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2, alignItems: 'flex-start' }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>微调工位</Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>微调 #{job.id}</Typography>
              <Typography color="text.secondary" variant="body2">{summarizePrompt(job.prompt || job.input_image_path)}</Typography>
            </Box>
            <Chip label={job.status} sx={{ bgcolor: job.status === 'succeeded' ? notionTokens.tintMint : job.status === 'failed' ? notionTokens.tintRose : notionTokens.tintSky }} />
          </Stack>
          {previewUrl && <Box component="img" src={previewUrl} alt="微调对象预览" loading="lazy" decoding="async" sx={{ width: '100%', maxHeight: 180, objectFit: 'contain', imageRendering: 'pixelated', border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: 'background.default', p: 1 }} />}

          <Card variant="outlined" sx={{ bgcolor: notionTokens.tintMint }}>
            <CardContent>
              <Stack component="form" spacing={2} onSubmit={submitLocal}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>免费本地微调</Typography>
                  <Typography color="text.secondary" variant="body2">不消耗点数。</Typography>
                </Box>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                  <TextField label="像素尺寸" value={pixelSize} onChange={(event) => setPixelSize(event.target.value)} />
                  <TextField label="颜色数" type="number" value={colors} onChange={(event) => setColors(Number(event.target.value))} />
                </Box>
                <FormControlLabel control={<Checkbox checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />} label="透明背景" />
                <Button type="submit" variant="contained" color="primary" disabled={loading || !sourcePath}>免费重新像素化</Button>
              </Stack>
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{ bgcolor: notionTokens.tintLavender }}>
            <CardContent>
              <Stack component="form" spacing={2} onSubmit={submitAi}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>AI 微调</Typography>
                  <Typography color="text.secondary" variant="body2">消耗 {aiPrice} 点。</Typography>
                </Box>
                {!sourcePath && <Alert severity="warning">当前作品没有可用源图路径，暂时无法微调。</Alert>}
                <TextField label="微调描述" value={aiPrompt} multiline minRows={4} onChange={(event) => setAiPrompt(event.target.value)} />
                <Button type="submit" variant="outlined" disabled={loading || !sourcePath}>AI 微调并入队</Button>
              </Stack>
            </CardContent>
          </Card>
        </Stack>
      </CardContent>
    </Card>
  )
}
