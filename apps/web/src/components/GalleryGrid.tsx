import { useMemo, useState } from 'react'
import { Box, Button, Card, CardActions, CardContent, CardMedia, Chip, Pagination, Stack, Typography } from '@mui/material'
import type { ContactSheetCandidate, GenerationJob, JobOutput } from '../types'
import { jobStatusLabel, jobTypeLabel } from '../labels'
import { summarizePrompt } from '../pixelize'
import { notionTokens } from '../theme'

type GalleryGridProps = {
  jobs: GenerationJob[]
  selectedJobId: number | null
  subtitle?: string
  onSelect: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
  onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
}

const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'primary',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function GalleryGrid({ jobs, subtitle, selectedJobId, onSelect, onCopyPath, onCandidatePixelize }: GalleryGridProps) {
  const [page, setPage] = useState(1)
  const pageSize = 80
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { xs: 'flex-start', sm: 'center' } }}>
          <Box>
            <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>作品库</Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>作品网格</Typography>
            {subtitle && <Typography color="text.secondary">{subtitle}</Typography>}
          </Box>
          <Chip label={`${ordered.length} 件作品/任务`} sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800 }} />
        </Stack>

        {ordered.length === 0 ? (
          <EmptyGalleryState />
        ) : (
          <Box sx={{ mt: 3, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 1.75 }}>
            {visible.map((job) => {
              const output = job.outputs[0]
              const mainPath = output?.pixelized_path || output?.source_path || job.input_image_path || ''
              const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''
              const selected = selectedJobId === job.id
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
                    boxShadow: selected ? notionTokens.focusRing : notionTokens.cardShadow,
                    transition: 'transform .18s ease, border-color .18s ease',
                    '&:hover': { transform: 'translateY(-2px)', borderColor: selected ? 'primary.main' : 'text.secondary' },
                  }}
                >
                  <CardMedia component="div" sx={{ height: 132, display: 'grid', placeItems: 'center', bgcolor: notionTokens.tintSky, imageRendering: 'pixelated' }}>
                    {previewUrl ? (
                      <Box component="img" src={previewUrl} alt={summarizePrompt(job.prompt || job.input_image_path, '作品预览')} loading="lazy" decoding="async" sx={{ width: '100%', height: '100%', objectFit: 'contain', imageRendering: 'pixelated', p: 1.5 }} />
                    ) : (
                      <Chip variant="outlined" color="primary" label={job.status === 'succeeded' ? 'PIX' : jobStatusLabel(job.status)} />
                    )}
                  </CardMedia>
                  <CardContent sx={{ display: 'grid', gap: 1.1 }}>
                    <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1, alignItems: 'flex-start' }}>
                      <Typography sx={{ fontWeight: 600 }}>#{job.id} · {jobTypeLabel(job.job_type)}</Typography>
                      <Chip size="small" color={statusColors[job.status] ?? 'default'} label={jobStatusLabel(job.status)} />
                    </Stack>
                    <Typography color="text.secondary" variant="body2">{summarizePrompt(job.prompt || job.input_image_path)}</Typography>
                    <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                      <Chip size="small" variant="outlined" label={`${job.price_credits} 点`} />
                      <Chip size="small" variant="outlined" label={new Date(job.created_at).toLocaleString()} />
                    </Stack>
                    {output && <GridQualityChips output={output} />}
                    {output && <CandidateMiniGrid job={job} output={output} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} />}
                    {job.batch_name && <Typography color="text.secondary" variant="caption">素材包：{job.batch_name}</Typography>}
                  </CardContent>
                  <CardActions>
                    <Button size="small" variant={selected ? 'contained' : 'outlined'} aria-pressed={selected} onClick={() => onSelect(job)}>
                      {selected ? '已选中' : '选择作品'}
                    </Button>
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
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 0.75 }}>
      {output.candidates.slice(0, 9).map((candidate) => (
        <Box key={candidate.path} sx={{ minWidth: 0 }}>
          <Box component="img" src={candidate.url ?? undefined} alt={`候选 ${candidate.index}`} loading="lazy" decoding="async" sx={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'contain', imageRendering: 'pixelated', bgcolor: 'background.default', border: 1, borderColor: 'divider', borderRadius: 1, p: 0.5 }} />
          <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }}>
            <Button size="small" variant="text" onClick={() => onCopyPath(candidate.path)}>路径</Button>
            {onCandidatePixelize && <Button size="small" variant="text" onClick={() => onCandidatePixelize(job, candidate)}>用它</Button>}
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
    <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
      {status?.mode && <Chip size="small" color={status.used_fallback || status.failed ? 'warning' : 'primary'} variant="outlined" label={status.mode === 'ai' ? 'AI Grid' : 'Grid'} />}
      {report && <Chip size="small" color={report.ok ? 'success' : 'warning'} variant="outlined" label={report.ok ? '可读性 OK' : '需返修'} />}
      {status?.repaired && <Chip size="small" color="success" variant="outlined" label="已返修" />}
    </Stack>
  )
}

function EmptyGalleryState() {
  return (
    <Box
      sx={{
        mt: 3,
        border: 1,
        borderStyle: 'dashed',
        borderColor: 'divider',
        borderRadius: 1.5,
        p: { xs: 3, md: 4 },
        bgcolor: notionTokens.tintYellowBold,
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', sm: '120px 1fr' },
        gap: 2.5,
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
        <Box sx={{ position: 'absolute', inset: '20px 10px 10px 18px', bgcolor: notionTokens.canvas, border: `2px solid ${notionTokens.inkDeep}`, borderRadius: .8 }} />
        <Box sx={{ position: 'absolute', left: 30, top: 8, width: 28, height: 18, bgcolor: notionTokens.tintSky, border: `2px solid ${notionTokens.inkDeep}` }} />
        <Box sx={{ position: 'absolute', right: 16, top: 18, width: 18, height: 18, bgcolor: notionTokens.tintRose, border: `2px solid ${notionTokens.inkDeep}` }} />
        <Box sx={{ position: 'absolute', left: 43, bottom: 24, width: 18, height: 18, bgcolor: notionTokens.primary }} />
        <Box sx={{ position: 'absolute', left: 8, top: 34, width: 8, height: 8, bgcolor: notionTokens.brandOrange }} />
        <Box sx={{ position: 'absolute', right: 4, bottom: 14, width: 8, height: 8, bgcolor: notionTokens.tintMint }} />
      </Box>
      <Box>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>工位台还空着</Typography>
        <Typography color="text.secondary" sx={{ mt: .5 }}>先生成单图，或直接批量生产一组素材。</Typography>
      </Box>
    </Box>
  )
}
