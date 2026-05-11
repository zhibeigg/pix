import { Box, Button, Card, CardContent, Chip, Divider, Stack, Typography } from '@mui/material'
import { jobStatusLabel, jobTypeLabel } from '../labels'
import { notionTokens } from '../theme'
import type { GenerationJob } from '../types'

type JobListProps = {
  jobs: GenerationJob[]
  onRefresh: () => void
}

const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'primary',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function JobList({ jobs, onRefresh }: JobListProps) {
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
              {jobs.map((job) => <JobCard job={job} key={job.id} />)}
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

function JobCard({ job }: { job: GenerationJob }) {
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
          {job.error_message && <Box component="pre" sx={{ whiteSpace: 'pre-wrap', maxHeight: 180, overflow: 'auto', color: 'error.main', bgcolor: notionTokens.errorPanel, border: 1, borderColor: 'error.main', borderRadius: 2, p: 1.25, m: 0 }}>{job.error_message.slice(0, 600)}</Box>}
          {output && (
            <Stack spacing={0.75} divider={<Divider flexItem />}>
              <PathLine label="源图" value={output.source_path} />
              <PathLine label="像素图" value={output.pixelized_path} />
              {output.preview_path && <PathLine label="预览" value={output.preview_path} />}
              <PathLine label="meta" value={output.meta_json_path} />
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
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
