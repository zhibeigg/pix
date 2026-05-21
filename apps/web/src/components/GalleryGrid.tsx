import { useMemo, useState } from 'react'
import { Box, Button, Card, CardActions, CardContent, CardMedia, Chip, Pagination, Stack, Typography } from '@mui/material'
import type { ContactSheetCandidate, GenerationJob, JobOutput } from '../types'
import { jobStatusLabel, jobTypeLabel, statusColors } from '../labels'
import { jobInputSummary } from '../pixelize'
import { checkerboardSx, notionTokens } from '../theme'

type GalleryGridProps = {
  jobs: GenerationJob[]
  selectedJobId: number | null
  subtitle?: string
  retryingJobId?: number | null
  onSelect: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
  onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRetryJob?: (job: GenerationJob) => Promise<void>
}

export function GalleryGrid({ jobs, subtitle, selectedJobId, retryingJobId = null, onSelect, onCopyPath, onCandidatePixelize, onRetryJob }: GalleryGridProps) {
  const [page, setPage] = useState(1)
  const pageSize = 72
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { xs: 'flex-start', sm: 'center' } }}>
          <Box>
            <Typography variant="overline" color="text.secondary">作品库</Typography>
            <Typography variant="h4">作品网格</Typography>
            {subtitle && <Typography color="text.secondary">{subtitle}</Typography>}
          </Box>
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            <Chip label={`${ordered.length} 件作品/任务`} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} />
            <Chip label={`第 ${safePage}/${totalPages} 页`} sx={{ bgcolor: notionTokens.surface }} />
          </Stack>
        </Stack>

        {ordered.length === 0 ? (
          <EmptyGalleryState />
        ) : (
          <Box sx={{ mt: 2.5, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 1.35 }}>
            {visible.map((job) => {
              const output = job.outputs[0]
              const mainPath = output?.sprite_sheet_path || output?.pixelized_path || output?.source_path || job.input_image_path || ''
              const previewUrl = output?.sprite_gif_url || output?.preview_url || output?.pixelized_url || output?.source_url || job.input_image_url || ''
              const selected = selectedJobId === job.id
              const retrying = retryingJobId === job.id
              return (
                <Card
                  key={job.id}
                  variant="outlined"
                  aria-current={selected ? 'true' : undefined}
                  sx={{
                    minWidth: 0,
                    overflow: 'hidden',
                    cursor: 'default',
                    borderColor: selected ? notionTokens.primary : notionTokens.hairline,
                    borderWidth: selected ? 2 : 1,
                    boxShadow: selected ? notionTokens.focusRing : notionTokens.cardShadow,
                    transition: 'transform .18s cubic-bezier(.22,1,.36,1), border-color .18s ease, box-shadow .18s ease',
                    '&:hover': { transform: 'translateY(-3px) scale(1.01)', borderColor: selected ? notionTokens.primary : notionTokens.hairlineStrong, boxShadow: notionTokens.liftShadow },
                    '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } },
                  }}
                >
                  <CardMedia component="div" sx={{ ...checkerboardSx, height: 140, display: 'grid', placeItems: 'center', imageRendering: 'pixelated', borderBottom: `1px solid ${notionTokens.hairline}` }}>
                    {previewUrl ? (
                      <Box component="img" src={previewUrl} alt={jobInputSummary(job, '作品预览')} loading="lazy" decoding="async" sx={{ width: '100%', height: '100%', objectFit: 'contain', imageRendering: 'pixelated', p: 1.4 }} />
                    ) : (
                      <Chip variant="outlined" color="primary" label={job.status === 'succeeded' ? 'PIX' : jobStatusLabel(job.status)} />
                    )}
                  </CardMedia>
                  <CardContent sx={{ display: 'grid', gap: .95, p: 1.6, '&:last-child': { pb: 1.6 } }}>
                    <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1, alignItems: 'flex-start' }}>
                      <Typography sx={{ fontWeight: 600 }} noWrap>#{job.id} · {jobTypeLabel(job.job_type)}</Typography>
                      <Chip size="small" color={statusColors[job.status] ?? 'default'} label={jobStatusLabel(job.status)} />
                    </Stack>
                    <Typography color="text.secondary" variant="body2" sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{jobInputSummary(job)}</Typography>
                    {selected && (
                      <Stack spacing={.9}>
                        <Stack direction="row" spacing={.7} sx={{ flexWrap: 'wrap' }}>
                          <Chip size="small" variant="outlined" label={`${job.price_credits} 点`} />
                          <Chip size="small" variant="outlined" label={new Date(job.created_at).toLocaleString()} />
                        </Stack>
                        {output && <GridQualityChips output={output} />}
                        {output?.sprite_gif_path && <Chip size="small" color="primary" variant="outlined" label="GIF 动画" />}
                        {output && <CandidateMiniGrid job={job} output={output} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} />}
                        {job.batch_name && <Typography color="text.secondary" variant="caption">素材包：{job.batch_name}</Typography>}
                      </Stack>
                    )}
                  </CardContent>
                  <CardActions sx={{ px: 1.6, pb: 1.4, pt: 0 }}>
                    <Button size="small" variant={selected ? 'contained' : 'outlined'} aria-pressed={selected} onClick={() => onSelect(job)}>
                      {selected ? '已展开' : '查看详情'}
                    </Button>
                    {job.status === 'failed' && onRetryJob && (
                      <Button size="small" color="error" variant="contained" disabled={retrying} onClick={() => onRetryJob(job)}>
                        {retrying ? '重试中…' : '重试'}
                      </Button>
                    )}
                    {mainPath && <Button size="small" variant="text" onClick={() => onCopyPath(mainPath)}>复制路径</Button>}
                  </CardActions>
                </Card>
              )
            })}
          </Box>
        )}
        {ordered.length > pageSize && (
          <Stack sx={{ mt: 3, alignItems: 'center' }}>
            <Pagination count={totalPages} page={safePage} color="primary" onChange={(_, value) => setPage(value)} />
          </Stack>
        )}
      </CardContent>
    </Card>
  )
}

function CandidateMiniGrid({ job, output, onCopyPath, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCopyPath: (path: string) => void; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  if (!output.candidates?.length) return null
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 0.65 }}>
      {output.candidates.slice(0, 9).map((candidate) => (
        <Box key={candidate.path} sx={{ minWidth: 0 }} title={candidate.reason ?? undefined}>
          <Box component="img" src={candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined} alt={`候选 ${candidate.index}`} loading="lazy" decoding="async" sx={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'contain', imageRendering: 'pixelated', bgcolor: notionTokens.surface, border: 1, borderColor: candidate.selected ? 'success.main' : 'divider', borderRadius: .75, p: 0.45 }} />
          <Stack direction="row" spacing={0.45} sx={{ mt: 0.45, flexWrap: 'wrap' }}>
            <Chip size="small" color={candidate.selected ? 'success' : 'default'} variant="outlined" label={candidate.rank ? `#${candidate.rank}` : `候选${candidate.index}`} />
            {candidate.score != null && <Chip size="small" variant="outlined" label={`${Math.round(candidate.score)}分`} />}
          </Stack>
          <Stack direction="row" spacing={0.45} sx={{ mt: 0.45 }}>
            <Button size="small" variant="text" onClick={() => onCopyPath(candidate.pixelized_path ?? candidate.path)}>像素图</Button>
            {onCandidatePixelize && <Button size="small" variant="text" onClick={() => onCandidatePixelize(job, candidate)}>重调</Button>}
          </Stack>
        </Box>
      ))}
    </Box>
  )
}

function GridQualityChips({ output }: { output: JobOutput }) {
  const status = output.grid_status
  const report = output.grid_readability
  if (!status && !report) return null
  return (
    <Stack direction="row" spacing={.7} sx={{ flexWrap: 'wrap' }}>
      {status?.mode && <Chip size="small" color="primary" variant="outlined" label="Grid" />}
      {report && <Chip size="small" color={report.ok ? 'success' : 'warning'} variant="outlined" label={report.ok ? '可读性 OK' : '需返修'} />}
    </Stack>
  )
}

function EmptyGalleryState() {
  return (
    <Box
      sx={{
        mt: 2.5,
        border: `1px dashed ${notionTokens.hairlineStrong}`,
        borderRadius: 1.5,
        p: { xs: 2.5, md: 3.5 },
        bgcolor: notionTokens.surface,
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', sm: '124px 1fr auto' },
        gap: 2.2,
        alignItems: 'center',
        overflow: 'hidden',
      }}
    >
      <Box
        aria-hidden="true"
        sx={{
          width: 104,
          height: 88,
          position: 'relative',
          justifySelf: { xs: 'start', sm: 'center' },
          imageRendering: 'pixelated',
        }}
      >
        <Box sx={{ position: 'absolute', inset: '20px 10px 10px 18px', bgcolor: notionTokens.canvas, border: `2px solid ${notionTokens.inkDeep}`, borderRadius: .75 }} />
        <Box sx={{ position: 'absolute', left: 30, top: 8, width: 28, height: 18, bgcolor: notionTokens.tintSky, border: `2px solid ${notionTokens.inkDeep}` }} />
        <Box sx={{ position: 'absolute', right: 16, top: 18, width: 18, height: 18, bgcolor: notionTokens.tintRose, border: `2px solid ${notionTokens.inkDeep}` }} />
        <Box sx={{ position: 'absolute', left: 43, bottom: 24, width: 18, height: 18, bgcolor: notionTokens.primary }} />
        <Box sx={{ position: 'absolute', left: 8, top: 34, width: 8, height: 8, bgcolor: notionTokens.brandOrange }} />
        <Box sx={{ position: 'absolute', right: 4, bottom: 14, width: 8, height: 8, bgcolor: notionTokens.tintMint }} />
      </Box>
      <Box>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>作品库还空着</Typography>
        <Typography color="text.secondary" sx={{ mt: .5 }}>先从生产工作台生成单图，或直接批量生产一组素材。完成后可在这里挑选、复制路径和进入微调。</Typography>
      </Box>
      <Button href="#/workspace" variant="contained" sx={{ justifySelf: { xs: 'start', sm: 'end' } }}>去生产</Button>
    </Box>
  )
}
