import { Box, Button, Card, CardContent, Chip, Divider, Stack, Typography } from '@mui/material'
import { jobStatusLabel, jobTypeLabel } from '../labels'
import { notionTokens } from '../theme'
import type { ContactSheetCandidate, GenerationJob, JobOutput } from '../types'

type JobListProps = {
  jobs: GenerationJob[]
  onRefresh: () => void
  onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
}

const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'primary',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function JobList({ jobs, onRefresh, onCandidatePixelize }: JobListProps) {
  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>生产队列</Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>正在生产</Typography>
            </Box>
            <Button variant="outlined" onClick={onRefresh}>刷新</Button>
          </Stack>
          {jobs.length === 0 ? (
            <EmptyQueueState />
          ) : (
            <Stack spacing={1.5}>
              {jobs.map((job) => <JobCard job={job} key={job.id} onCandidatePixelize={onCandidatePixelize} />)}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

function EmptyQueueState() {
  return (
    <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1.5, bgcolor: notionTokens.surfaceSoft, p: 2.25 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
        <Box
          aria-hidden="true"
          sx={{
            width: 38,
            height: 38,
            borderRadius: 1,
            bgcolor: notionTokens.tintMint,
            border: `1px solid ${notionTokens.hairlineStrong}`,
            position: 'relative',
            flex: '0 0 auto',
            '&::before': { content: '""', position: 'absolute', left: 10, top: 10, width: 7, height: 7, bgcolor: notionTokens.primary },
            '&::after': { content: '""', position: 'absolute', right: 9, bottom: 9, width: 10, height: 10, bgcolor: notionTokens.brandOrange },
          }}
        />
        <Box>
          <Typography sx={{ fontWeight: 700 }}>炉火正安静</Typography>
          <Typography variant="body2" color="text.secondary">暂无生产中任务，可以开一组新素材。</Typography>
        </Box>
      </Stack>
    </Box>
  )
}

function JobCard({ job, onCandidatePixelize }: { job: GenerationJob; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  const output = job.outputs[0]
  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.surfaceSoft }}>
      <CardContent>
        <Stack spacing={1.5}>
          <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', gap: 1.5 }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 600 }}>#{job.id} · {jobTypeLabel(job.job_type)}</Typography>
              <Typography color="text.secondary" variant="body2">{job.prompt || job.input_image_path || '无输入摘要'}</Typography>
            </Box>
            <Chip size="small" color={statusColors[job.status] ?? 'default'} label={jobStatusLabel(job.status)} sx={{ alignSelf: { xs: 'flex-start', sm: 'center' }, bgcolor: job.status === 'succeeded' ? notionTokens.tintMint : job.status === 'failed' ? notionTokens.tintRose : job.status === 'running' ? notionTokens.tintSky : notionTokens.tintYellow }} />
          </Stack>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Chip size="small" variant="outlined" label={`${job.price_credits} 点`} />
            <Chip size="small" variant="outlined" label={`冻结 ${job.reserved_credits}`} />
            <Chip size="small" variant="outlined" label={new Date(job.created_at).toLocaleString()} />
          </Stack>
          {output && <GridQualitySummary output={output} />}
          {output && <CandidateStrip job={job} output={output} onCandidatePixelize={onCandidatePixelize} />}
          {job.error_message && <Box component="pre" sx={{ whiteSpace: 'pre-wrap', maxHeight: 180, overflow: 'auto', color: 'error.main', bgcolor: notionTokens.errorPanel, border: 1, borderColor: 'error.main', borderRadius: 2, p: 1.25, m: 0 }}>{job.error_message.slice(0, 600)}</Box>}
          {output && (
            <Stack spacing={0.75} divider={<Divider flexItem />}>
              <PathLine label="源图" value={output.source_path} />
              <PathLine label="像素图" value={output.pixelized_path} />
              {output.preview_path && <PathLine label="预览" value={output.preview_path} />}
              {output.grid_json_path && <PathLine label="Grid" value={output.grid_json_path} />}
              <PathLine label="meta" value={output.meta_json_path} />
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

function CandidateStrip({ job, output, onCandidatePixelize }: { job: GenerationJob; output: JobOutput; onCandidatePixelize?: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void> }) {
  if (!output.candidates?.length) return null
  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.tintMint }}>
      <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
        <Typography variant="caption" color="text.secondary">九宫格候选</Typography>
        <Box sx={{ mt: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(76px, 1fr))', gap: 1 }}>
          {output.candidates.map((candidate) => (
            <Stack key={candidate.path} spacing={0.5} sx={{ alignItems: 'center' }} title={candidate.reason ?? undefined}>
              <Box component="img" src={candidate.preview_url ?? candidate.pixelized_url ?? candidate.url ?? undefined} alt={`候选 ${candidate.index}`} loading="lazy" decoding="async" sx={{ width: 64, height: 64, objectFit: 'contain', imageRendering: 'pixelated', bgcolor: 'background.paper', border: 1, borderColor: candidate.selected ? 'success.main' : 'divider', borderRadius: 1, p: 0.5 }} />
              <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', justifyContent: 'center' }}>
                <Chip size="small" color={candidate.selected ? 'success' : 'default'} variant="outlined" label={candidate.rank ? `#${candidate.rank}` : `候选${candidate.index}`} />
                {candidate.score != null && <Chip size="small" variant="outlined" label={`${Math.round(candidate.score)}分`} />}
              </Stack>
              {onCandidatePixelize && <Button size="small" variant="outlined" onClick={() => onCandidatePixelize(job, candidate)}>重调</Button>}
            </Stack>
          ))}
        </Box>
      </CardContent>
    </Card>
  )
}

function GridQualitySummary({ output }: { output: JobOutput }) {
  const status = output.grid_status
  const report = output.grid_readability
  if (!status && !report) return null
  const mode = status?.mode === 'extract' ? 'Grid 提取' : status?.mode
  const blocking = report?.issues?.filter((issue) => issue.level === 'blocking').length ?? 0
  return (
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
      {mode && <Chip size="small" color="primary" variant="outlined" label={mode} />}
      {report && <Chip size="small" color={report.ok ? 'success' : 'warning'} variant="outlined" label={report.ok ? '可读性通过' : `阻塞 ${blocking}`} />}
      {report && <Chip size="small" variant="outlined" label={`${report.color_count} 色 · 主体 ${Math.round(report.bbox_coverage * 100)}%`} />}
    </Stack>
  )
}

function PathLine({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '70px minmax(0, 1fr)', gap: 1, alignItems: 'center' }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Box component="code" title={value} sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'info.light' }}>{value}</Box>
    </Box>
  )
}
