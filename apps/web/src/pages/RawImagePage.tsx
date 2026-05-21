import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Chip, LinearProgress, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { defaultPixelize, summarizePrompt } from '../pixelize'
import { checkerboardSx, notionTokens } from '../theme'
import type { ContactSheetCandidate, CreditBalance, GenerationJob, JobCreateRequest, PricingRule } from '../types'

type RawImagePageProps = {
  pricing: PricingRule[]
  balance: CreditBalance | null
  jobs: GenerationJob[]
  loading: boolean
  selectedJobId: number | null
  onSelectJob: (jobId: number) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>
  onRefresh: () => void | Promise<void>
}

type PreviewOverride = {
  jobId: number
  url: string
  label: string
}

type Thumb = {
  key: string
  job: GenerationJob
  url: string
  label: string
  meta: string
  selected: boolean
  candidate?: ContactSheetCandidate
}

const imageSizes = ['1024x1024', '1536x1024', '1024x1536', '2048x1024', '1024x2048', 'auto']
const qualityOptions = [
  { value: 'auto', label: '自动' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
]
const sensitivityOptions = [
  { value: 'auto', label: '自动' },
  { value: 'standard', label: '标准' },
  { value: 'strict', label: '严格' },
]

export function RawImagePage({ pricing, balance, jobs, loading, selectedJobId, onSelectJob, onCreateJob, onCreateJobs, onRefresh }: RawImagePageProps) {
  const [provider] = useState('packyapi-image')
  const [model, setModel] = useState('gpt-image-2')
  const [imageSize, setImageSize] = useState('1024x1024')
  const [quality, setQuality] = useState('auto')
  const [sensitivity, setSensitivity] = useState('auto')
  const [generationCount, setGenerationCount] = useState(1)
  const [prompt, setPrompt] = useState('Create a polished 1024x1024 square app icon artwork for a fantasy RPG healing potion, deep emerald background, crisp silhouette, cinematic lighting.')
  const [previewOverride, setPreviewOverride] = useState<PreviewOverride | null>(null)

  const rawJobs = useMemo(() => jobs.filter(isRawImageJob).sort(sortNewestFirst), [jobs])
  const selectedJob = rawJobs.find((job) => job.id === selectedJobId) ?? rawJobs[0] ?? null
  const selectedOutput = firstOutput(selectedJob)
  const price = pricing.find((item) => item.key === 'text_to_image')?.price_credits ?? 0
  const safeCount = normalizeCount(generationCount)
  const estimatedCredits = price * safeCount
  const availableCredits = balance?.available_credits
  const insufficientCredits = typeof availableCredits === 'number' && availableCredits < estimatedCredits
  const hasPreviewOverride = previewOverride !== null && selectedJob !== null && previewOverride.jobId === selectedJob.id
  const mainImageUrl = hasPreviewOverride ? previewOverride.url : rawSourceUrl(selectedJob)
  const mainImageLabel = hasPreviewOverride ? previewOverride.label : '原始源图'

  const thumbs = useMemo(() => buildThumbs(rawJobs, selectedJob?.id ?? null, previewOverride), [previewOverride, rawJobs, selectedJob?.id])

  useEffect(() => {
    setPreviewOverride(null)
  }, [selectedJob?.id])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const basePrompt = prompt.trim()
    if (!basePrompt || insufficientCredits) return
    const payloads = Array.from({ length: safeCount }, (_, index) => buildRawPayload({
      prompt: variationPrompt(basePrompt, index, safeCount),
      imageSize,
      quality,
      model,
    }))
    if (payloads.length === 1) {
      await onCreateJob(payloads[0])
    } else {
      await onCreateJobs(payloads, `原始生图 ${new Date().toLocaleString()}`, 'raw_image')
    }
  }

  function selectThumb(thumb: Thumb) {
    onSelectJob(thumb.job.id)
    if (thumb.candidate) {
      setPreviewOverride({ jobId: thumb.job.id, url: thumb.url, label: thumb.label })
    } else {
      setPreviewOverride(null)
    }
  }

  return (
    <Stack component="form" spacing={2.2} onSubmit={submit}>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.4} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', md: 'flex-end' } }}>
        <Box>
          <Typography variant="overline" color="primary.main">Raw Forge</Typography>
          <Typography variant="h3" component="h2">原始生图</Typography>
          <Typography color="text.secondary" sx={{ maxWidth: '68ch', mt: .6 }}>
            只做文生原图：调基础参数、提交 prompt、在画布里看源图。像素化、批量包和图生图留在生产工作台处理。
          </Typography>
        </Box>
        <Stack direction="row" sx={{ gap: .8, flexWrap: 'wrap' }}>
          <Chip label={`余额 ${availableCredits ?? '—'} 点`} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} />
          <Chip label={`预计 ${estimatedCredits} 点`} sx={{ bgcolor: insufficientCredits ? notionTokens.tintRose : notionTokens.tintMint }} />
          <Button type="button" variant="outlined" onClick={() => onRefresh()}>刷新</Button>
        </Stack>
      </Stack>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '236px minmax(0, 1fr) 118px' },
          gap: 1.5,
          alignItems: 'stretch',
        }}
      >
        <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas, minWidth: 0 }}>
          <CardContent sx={{ p: { xs: 2, lg: 2.1 } }}>
            <Stack spacing={2.1}>
              <Box>
                <Typography variant="overline" color="text.secondary">参数</Typography>
                <Typography variant="h5">基础生图设置</Typography>
              </Box>
              <TextField select label="提供商" value={provider} disabled fullWidth>
                <MenuItem value="packyapi-image">packyapi-image</MenuItem>
              </TextField>
              <TextField select label="模型" value={model} onChange={(event) => setModel(event.target.value)} fullWidth>
                <MenuItem value="gpt-image-2">gpt-image-2</MenuItem>
              </TextField>
              <TextField select label="图片尺寸" value={imageSize} onChange={(event) => setImageSize(event.target.value)} fullWidth>
                {imageSizes.map((size) => <MenuItem value={size} key={size}>{size}</MenuItem>)}
              </TextField>
              <TextField select label="质量" value={quality} onChange={(event) => setQuality(event.target.value)} fullWidth>
                {qualityOptions.map((option) => <MenuItem value={option.value} key={option.value}>{option.label}</MenuItem>)}
              </TextField>
              <TextField
                select
                label="敏感度"
                value={sensitivity}
                onChange={(event) => setSensitivity(event.target.value)}
                helperText="当前沿用后端安全策略，此项仅用于前端记录意图。"
                fullWidth
              >
                {sensitivityOptions.map((option) => <MenuItem value={option.value} key={option.value}>{option.label}</MenuItem>)}
              </TextField>
              <TextField
                label="生成数量"
                type="number"
                value={generationCount}
                onChange={(event) => setGenerationCount(Number(event.target.value))}
                slotProps={{ htmlInput: { min: 1, max: 4, step: 1 } }}
                helperText="1-4 张；多张会作为轻量变体任务提交。"
                fullWidth
              />
            </Stack>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ bgcolor: notionTokens.brandNavyDeep, color: notionTokens.onDark, minWidth: 0, overflow: 'hidden' }}>
          {selectedJob && ['pending', 'running'].includes(selectedJob.status) && <LinearProgress color="primary" />}
          <CardContent sx={{ p: { xs: 1.4, md: 2 }, height: '100%' }}>
            <Box
              sx={{
                minHeight: { xs: 360, md: 500 },
                height: '100%',
                display: 'grid',
                gridTemplateRows: 'auto minmax(0, 1fr) auto',
                gap: 1.4,
              }}
            >
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ justifyContent: 'space-between', alignItems: { xs: 'flex-start', sm: 'center' } }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="overline" sx={{ color: notionTokens.onDarkMuted }}>Preview Deck</Typography>
                  <Typography variant="h5" sx={{ color: notionTokens.onDark }}>{selectedJob ? `#${selectedJob.id} · ${mainImageLabel}` : '等待第一张原图'}</Typography>
                </Box>
                {selectedJob && <JobStatusChips job={selectedJob} />}
              </Stack>

              <Box
                aria-live="polite"
                aria-busy={selectedJob ? ['pending', 'running'].includes(selectedJob.status) : false}
                sx={{
                  ...checkerboardSx,
                  borderRadius: 1.6,
                  border: `1px solid ${notionTokens.hairlineStrong}`,
                  minHeight: 0,
                  display: 'grid',
                  placeItems: 'center',
                  overflow: 'hidden',
                  bgcolor: notionTokens.surfaceSoft,
                  p: { xs: 1.2, md: 2 },
                }}
              >
                {mainImageUrl ? (
                  <Box
                    component="img"
                    src={mainImageUrl}
                    alt={selectedJob?.prompt ? summarizePrompt(selectedJob.prompt, '原始生图预览') : '原始生图预览'}
                    loading="lazy"
                    decoding="async"
                    sx={{ width: '100%', height: '100%', maxHeight: { xs: 460, md: 620 }, objectFit: 'contain', borderRadius: 1.1 }}
                  />
                ) : (
                  <RawCanvasState job={selectedJob} />
                )}
              </Box>

              <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <Typography variant="caption" sx={{ color: notionTokens.onDarkMuted }}>
                  {selectedJob ? summarizePrompt(selectedJob.prompt, '无 prompt') : '输入 prompt 后，生成结果会停留在本页。'}
                </Typography>
                {selectedOutput?.source_path && <Chip size="small" variant="outlined" label="source.png" sx={{ color: notionTokens.onDark, borderColor: notionTokens.onDarkMuted }} />}
              </Stack>
            </Box>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas, minWidth: 0 }}>
          <CardContent sx={{ p: 1.1 }}>
            <Stack spacing={1.1}>
              <Typography variant="overline" color="text.secondary" sx={{ px: .4 }}>最近</Typography>
              {thumbs.length === 0 ? (
                <Box sx={{ border: `1px dashed ${notionTokens.hairlineStrong}`, borderRadius: 1.2, p: 1.1, textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary">暂无缩略图</Typography>
                </Box>
              ) : (
                <Stack spacing={.9}>
                  {thumbs.slice(0, 8).map((thumb) => (
                    <Box
                      component="button"
                      type="button"
                      key={thumb.key}
                      title={`${thumb.label} · ${thumb.meta}`}
                      onClick={() => selectThumb(thumb)}
                      sx={{
                        border: 1,
                        borderColor: thumb.selected ? notionTokens.primary : notionTokens.hairline,
                        bgcolor: thumb.selected ? notionTokens.tintLavender : notionTokens.surface,
                        borderRadius: 1,
                        p: .45,
                        cursor: 'pointer',
                        width: '100%',
                        minHeight: 72,
                        display: 'grid',
                        placeItems: 'center',
                        transition: 'transform .16s ease, border-color .16s ease, background-color .16s ease',
                        '&:hover': { transform: 'translateY(-1px)', borderColor: notionTokens.primary },
                        '&:focus-visible': { outline: `2px solid ${notionTokens.primary}`, outlineOffset: 2 },
                        '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } },
                      }}
                    >
                      <Box component="img" src={thumb.url} alt={thumb.label} loading="lazy" decoding="async" sx={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', borderRadius: .7 }} />
                    </Box>
                  ))}
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
        <CardContent sx={{ p: { xs: 1.5, md: 1.8 }, '&:last-child': { pb: { xs: 1.5, md: 1.8 } } }}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.4} sx={{ alignItems: 'stretch' }}>
            <TextField
              label="Prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="描述你要生成的原始图片：主体、风格、构图、颜色、用途。"
              multiline
              minRows={2}
              maxRows={6}
              fullWidth
              required
            />
            <Stack spacing={1} sx={{ minWidth: { md: 188 }, justifyContent: 'space-between' }}>
              {insufficientCredits ? (
                <Alert severity="warning" sx={{ py: .45 }}>点数不足</Alert>
              ) : (
                <Chip label={`${imageSize} · ${qualityOptions.find((item) => item.value === quality)?.label ?? quality} · ${safeCount} 张`} sx={{ bgcolor: notionTokens.tintCream }} />
              )}
              <Button type="submit" variant="contained" size="large" disabled={loading || !prompt.trim() || insufficientCredits}>
                {loading ? '提交中…' : '生成原图'}
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  )
}

function buildRawPayload({ prompt, imageSize, quality, model }: { prompt: string; imageSize: string; quality: string; model: string }): JobCreateRequest {
  return {
    job_type: 'text_to_image',
    prompt,
    input_image_path: null,
    client_request_id: `raw-image-${crypto.randomUUID()}`,
    image_size: imageSize,
    image_quality: quality,
    image_model: model,
    skip_vl: true,
    pixelize: {
      ...defaultPixelize,
      output_size: [128, 128],
      preview_scale: 0,
      remove_bg: false,
      auto_crop: false,
    },
    grid: { mode: 'off' },
  }
}

function variationPrompt(basePrompt: string, index: number, count: number) {
  if (count <= 1) return basePrompt
  return `${basePrompt}\n\nVariation ${index + 1}/${count}: keep the requested subject and style, but use a distinct composition and detail arrangement.`
}

function normalizeCount(value: number) {
  if (!Number.isFinite(value)) return 1
  return Math.max(1, Math.min(4, Math.trunc(value)))
}

function isRawImageJob(job: GenerationJob) {
  const grid = job.params_json?.grid
  const gridMode = typeof grid === 'object' && grid !== null && 'mode' in grid ? (grid as { mode?: unknown }).mode : null
  return job.job_type === 'text_to_image' && job.params_json?.skip_vl === true && gridMode === 'off'
}

function sortNewestFirst(a: GenerationJob, b: GenerationJob) {
  return Number(new Date(b.created_at)) - Number(new Date(a.created_at))
}

function firstOutput(job: GenerationJob | null | undefined) {
  return Array.isArray(job?.outputs) ? job.outputs[0] : undefined
}

function rawSourceUrl(job: GenerationJob | null | undefined) {
  return firstOutput(job)?.source_url || null
}

function candidateRawUrl(candidate: ContactSheetCandidate) {
  return candidate.url || candidate.pixelized_url || candidate.preview_url || null
}

function buildThumbs(rawJobs: GenerationJob[], selectedJobId: number | null, previewOverride: PreviewOverride | null): Thumb[] {
  const thumbs: Thumb[] = []
  for (const job of rawJobs) {
    const output = firstOutput(job)
    const candidates = Array.isArray(output?.candidates) ? output.candidates : []
    if (job.id === selectedJobId && candidates.length) {
      for (const candidate of candidates) {
        const url = candidateRawUrl(candidate)
        if (!url) continue
        const label = candidate.rank ? `候选 #${candidate.rank}` : `候选 ${candidate.index}`
        thumbs.push({
          key: `candidate-${job.id}-${candidate.path}`,
          job,
          url,
          label,
          meta: candidate.score != null ? `${Math.round(candidate.score)} 分` : '原始候选',
          selected: previewOverride?.jobId === job.id && previewOverride.url === url,
          candidate,
        })
      }
    }
    const url = rawSourceUrl(job)
    if (!url) continue
    thumbs.push({
      key: `job-${job.id}`,
      job,
      url,
      label: `任务 #${job.id}`,
      meta: job.status,
      selected: previewOverride?.jobId !== job.id && job.id === selectedJobId,
    })
  }
  return thumbs
}

function JobStatusChips({ job }: { job: GenerationJob }) {
  return (
    <Stack direction="row" sx={{ gap: .65, flexWrap: 'wrap', justifyContent: { xs: 'flex-start', sm: 'flex-end' } }}>
      <Chip size="small" label={job.status} sx={{ bgcolor: statusTint(job.status), color: job.status === 'running' ? notionTokens.onSecondary : undefined }} />
      <Chip size="small" variant="outlined" label={`${job.price_credits} 点`} sx={{ color: notionTokens.onDark, borderColor: notionTokens.onDarkMuted }} />
    </Stack>
  )
}

function statusTint(status: string) {
  if (status === 'succeeded') return notionTokens.tintMint
  if (status === 'failed') return notionTokens.tintRose
  if (status === 'running') return notionTokens.tintSky
  return notionTokens.tintYellow
}

function safeErrorMessage(job: GenerationJob) {
  return typeof job.error_message === 'string' ? job.error_message : ''
}

function RawCanvasState({ job }: { job: GenerationJob | null }) {
  if (!job) {
    return (
      <Stack spacing={1.4} sx={{ alignItems: 'center', textAlign: 'center', maxWidth: 360 }}>
        <PixelGlyph />
        <Box>
          <Typography variant="h5">等待 prompt 点火</Typography>
          <Typography color="text.secondary">左侧保留基础参数，底部输入描述后生成第一张原始图。</Typography>
        </Box>
      </Stack>
    )
  }
  if (job.status === 'failed') {
    return (
      <Alert severity="error" sx={{ maxWidth: 620, width: '100%' }}>
        <Typography sx={{ fontWeight: 700 }}>生成失败</Typography>
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{safeErrorMessage(job).slice(0, 520) || '后端未返回错误详情。'}</Typography>
      </Alert>
    )
  }
  if (['pending', 'running'].includes(job.status)) {
    return (
      <Stack spacing={1.5} sx={{ alignItems: 'center', textAlign: 'center', maxWidth: 420 }}>
        <PixelGlyph active />
        <Box>
          <Typography variant="h5">炉膛正在出图</Typography>
          <Typography color="text.secondary">任务 #{job.id} 已进入队列，完成后这里会直接显示 source 原图。</Typography>
        </Box>
      </Stack>
    )
  }
  return (
    <Stack spacing={1.2} sx={{ alignItems: 'center', textAlign: 'center', maxWidth: 420 }}>
      <PixelGlyph />
      <Box>
        <Typography variant="h5">暂未拿到源图链接</Typography>
        <Typography color="text.secondary">任务已完成但文件 URL 还没有解析，点刷新再看一次。</Typography>
      </Box>
    </Stack>
  )
}

function PixelGlyph({ active = false }: { active?: boolean }) {
  return (
    <Box
      aria-hidden="true"
      sx={{
        width: 96,
        height: 96,
        position: 'relative',
        imageRendering: 'pixelated',
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: 14,
          bgcolor: active ? notionTokens.tintYellow : notionTokens.tintLavender,
          border: `2px solid ${notionTokens.inkDeep}`,
          borderRadius: 1,
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          width: 22,
          height: 22,
          right: 12,
          bottom: 18,
          bgcolor: active ? notionTokens.brandOrange : notionTokens.primary,
          boxShadow: `-34px -18px 0 ${notionTokens.tintMint}, -16px 24px 0 ${notionTokens.tintSky}`,
        },
      }}
    />
  )
}
