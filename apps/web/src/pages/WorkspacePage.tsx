import { Box, Card, CardContent, Stack, Tab, Tabs, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import { BatchGeneratePanel } from '../components/BatchGeneratePanel'
import { JobList } from '../components/JobList'
import { PageHeader } from '../components/PageHeader'
import { SingleGeneratePanel } from '../components/SingleGeneratePanel'
import type { ContactSheetCandidate, CreditBalance, GenerationJob, JobCreateRequest, PricingRule } from '../types'

export type WorkMode = 'single' | 'batch'

interface WorkspacePageProps {
  mode: WorkMode
  pricing: PricingRule[]
  balance: CreditBalance | null
  jobs: GenerationJob[]
  loading: boolean
  token: string
  onModeChange: (mode: WorkMode) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRefresh: () => void
}

export function WorkspacePage({ mode, pricing, balance, jobs, loading, token, onModeChange, onCreateJob, onCreateJobs, onCandidatePixelize, onRefresh }: WorkspacePageProps) {
  const activeJobs = jobs.filter((job) => ['pending', 'running'].includes(job.status))
  const succeeded = jobs.filter((job) => job.status === 'succeeded').length
  const failed = jobs.filter((job) => job.status === 'failed').length

  return (
    <Stack spacing={2.8}>
      <PageHeader eyebrow="生产" title="生产工作台" description="先试单张，再批量成包；所有任务都会进入作品库和队列记录。" tint="yellow" />

      <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
        <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) auto' }, gap: 2, alignItems: 'center' }}>
            <Stack spacing={.7}>
              <Typography variant="overline" color="text.secondary">创建模式</Typography>
              <Typography variant="h5">选择本次生产节奏</Typography>
              <Typography color="text.secondary">单图适合验证材质和轮廓；批量适合素材包、图标套装和原型补齐。</Typography>
            </Stack>
            <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: .5, width: { xs: '100%', sm: 'fit-content' } }}>
              <Tabs
                value={mode}
                aria-label="创建模式"
                onChange={(_, value: WorkMode) => onModeChange(value)}
                variant="scrollable"
                scrollButtons="auto"
                sx={{ minHeight: 0, '& .MuiTabs-indicator': { display: 'none' }, '& .MuiTabs-flexContainer': { gap: .5 }, '& .MuiTab-root': { minHeight: 38, borderRadius: '8px', px: 2.2 }, '& .Mui-selected': { bgcolor: notionTokens.brandNavyDeep, color: `${notionTokens.onDark} !important` } }}
              >
                <Tab value="single" label="单图试做" />
                <Tab value="batch" label="批量生产" />
              </Tabs>
            </Box>
          </Box>
          <Box sx={{ mt: 2, display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1 }}>
            <WorkbenchMetric label="队列中" value={activeJobs.length} tone={notionTokens.tintSky} />
            <WorkbenchMetric label="已完成" value={succeeded} tone={notionTokens.tintMint} />
            <WorkbenchMetric label="失败" value={failed} tone={failed ? notionTokens.tintRose : notionTokens.tintGray} />
            <WorkbenchMetric label="可用点数" value={balance?.available_credits ?? '—'} tone={notionTokens.tintLavender} />
          </Box>
        </CardContent>
      </Card>

      {mode === 'single' ? (
        <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} />
      ) : (
        <BatchGeneratePanel pricing={pricing} balance={balance} loading={loading} token={token} onSubmitMany={onCreateJobs} />
      )}

      <JobList jobs={activeJobs} onRefresh={onRefresh} onCandidatePixelize={onCandidatePixelize} />
    </Stack>
  )
}

function WorkbenchMetric({ label, value, tone }: { label: string; value: string | number; tone: string }) {
  return (
    <Box sx={{ bgcolor: tone, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1, p: 1.2, minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h5" sx={{ fontVariantNumeric: 'tabular-nums' }}>{value}</Typography>
    </Box>
  )
}
