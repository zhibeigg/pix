import { FormEvent, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, Stack, TextField, Typography } from '@mui/material'
import { jobStatusLabel } from '../labels'
import { notionTokens } from '../theme'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'
import { buildGridDesign, buildPixelize, hasInvalidSubAssetSize, parsePixelSize, summarizePrompt } from '../pixelize'
import { PixelControls } from './PixelControls'

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

  const output = Array.isArray(job.outputs) ? job.outputs[0] : undefined
  const sourcePath = output?.source_path || output?.pixelized_path || job.input_image_path || ''
  const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''
  const parsedPixelSize = parsePixelSize(pixelSize)
  const invalidSubAssetSize = hasInvalidSubAssetSize(parsedPixelSize)

  async function submitLocal(event: FormEvent) {
    event.preventDefault()
    if (!sourcePath) return
    await onSubmit({
      job_type: 'repixelize',
      prompt: null,
      input_image_path: sourcePath,
      client_request_id: crypto.randomUUID(),
      skip_vl: true,
      pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }),
      grid: buildGridDesign(),
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
      pixelize: buildPixelize({ output_size: parsedPixelSize, colors, remove_bg: removeBg }),
      grid: buildGridDesign(),
    })
  }

  return (
    <Card variant="outlined" sx={{ overflow: 'hidden', position: 'sticky', top: 96 }}>
      <Box sx={{ height: 6, background: `linear-gradient(90deg, ${notionTokens.tintLavender}, ${statusTint(job.status)})` }} />
      <CardContent sx={{ p: { xs: 2, md: 2.25 } }}>
        <Stack spacing={2.1}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1.5, alignItems: 'flex-start' }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>微调工位</Typography>
              <Typography variant="h4" sx={{ fontWeight: 600, lineHeight: 1.1 }}>#{job.id}</Typography>
              <Typography color="text.secondary" variant="body2" noWrap title={job.prompt || job.input_image_path || undefined}>{summarizePrompt(job.prompt || job.input_image_path)}</Typography>
            </Box>
            <Chip size="small" label={jobStatusLabel(job.status)} sx={{ bgcolor: statusTint(job.status), fontWeight: 700 }} />
          </Stack>

          <PreviewBox previewUrl={previewUrl} label={summarizePrompt(job.prompt || job.input_image_path, '微调对象预览')} />

          {invalidSubAssetSize && <Alert severity="error">素材最低支持 16×16。</Alert>}

          <Card variant="outlined" sx={{ bgcolor: notionTokens.tintMint, boxShadow: 'none' }}>
            <CardContent sx={{ p: 1.7, '&:last-child': { pb: 1.7 } }}>
              <Stack component="form" spacing={1.6} onSubmit={submitLocal}>
                <Stack direction="row" sx={{ alignItems: 'baseline', justifyContent: 'space-between', gap: 1 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>本地像素化</Typography>
                    <Typography color="text.secondary" variant="caption">免费 · 不消耗点数</Typography>
                  </Box>
                  <Chip size="small" label="FREE" sx={{ bgcolor: notionTokens.canvas }} />
                </Stack>
                <PixelControls compact pixelSize={pixelSize} onPixelSizeChange={setPixelSize} colors={colors} onColorsChange={setColors} />
                <FormControlLabel control={<Checkbox checked={removeBg} onChange={(event) => setRemoveBg(event.target.checked)} />} label="透明背景" />
                <Button type="submit" variant="contained" color="primary" disabled={loading || !sourcePath || invalidSubAssetSize}>重新像素化</Button>
              </Stack>
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{ bgcolor: notionTokens.tintLavender, boxShadow: 'none' }}>
            <CardContent sx={{ p: 1.7, '&:last-child': { pb: 1.7 } }}>
              <Stack component="form" spacing={1.5} onSubmit={submitAi}>
                <Stack direction="row" sx={{ alignItems: 'baseline', justifyContent: 'space-between', gap: 1 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>AI 微调</Typography>
                    <Typography color="text.secondary" variant="caption">消耗 {aiPrice} 点</Typography>
                  </Box>
                  <Chip size="small" label={`${aiPrice} 点`} sx={{ bgcolor: notionTokens.canvas }} />
                </Stack>
                {!sourcePath && <Alert severity="warning">当前作品没有可用源图路径，暂时无法微调。</Alert>}
                <TextField label="微调描述" value={aiPrompt} multiline minRows={3} onChange={(event) => setAiPrompt(event.target.value)} />
                <Button type="submit" variant="outlined" disabled={loading || !sourcePath || invalidSubAssetSize}>AI 微调并入队</Button>
              </Stack>
            </CardContent>
          </Card>
        </Stack>
      </CardContent>
    </Card>
  )
}

function PreviewBox({ previewUrl, label }: { previewUrl: string; label: string }) {
  return (
    <Box
      sx={{
        minHeight: 168,
        border: `1px solid ${notionTokens.hairline}`,
        borderRadius: 1.4,
        bgcolor: notionTokens.surface,
        display: 'grid',
        placeItems: 'center',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {previewUrl ? (
        <Box component="img" src={previewUrl} alt={label} loading="lazy" decoding="async" sx={{ width: '100%', maxHeight: 210, objectFit: 'contain', imageRendering: 'pixelated', p: 1 }} />
      ) : (
        <Stack spacing={.7} sx={{ alignItems: 'center', color: notionTokens.steel, textAlign: 'center', p: 2 }}>
          <Box aria-hidden="true" sx={{ width: 42, height: 42, borderRadius: 1.1, bgcolor: notionTokens.tintGray, border: `1px dashed ${notionTokens.hairlineStrong}` }} />
          <Typography variant="body2" sx={{ fontWeight: 700 }}>暂无可预览源图</Typography>
          <Typography variant="caption" color="text.secondary">任务完成后会在这里显示缩略图</Typography>
        </Stack>
      )}
    </Box>
  )
}

function statusTint(status: string) {
  if (status === 'succeeded') return notionTokens.tintMint
  if (status === 'failed') return notionTokens.tintRose
  if (status === 'running') return notionTokens.tintSky
  return notionTokens.tintYellow
}
