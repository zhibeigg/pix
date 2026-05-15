import { Box, Stack, Tab, Tabs, Typography } from '@mui/material'
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

  return (
    <Stack spacing={2.8}>
      <PageHeader eyebrow="生产" title="生产工作台" description="先试单张，再批量成包；所有任务都会进入作品库和队列记录。" tint="yellow" />

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) auto' }, gap: 2, alignItems: 'center' }}>
        <Stack spacing={.5}>
          <Typography variant="overline" color="text.secondary">创建模式</Typography>
          <Typography color="text.secondary">单图验证轮廓，批量生成素材包。</Typography>
        </Stack>
        <Box sx={{ bgcolor: notionTokens.surface, border: `1px solid ${notionTokens.hairline}`, borderRadius: 1.5, p: .5, width: { xs: '100%', sm: 'fit-content' } }}>
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

      {mode === 'single' ? (
        <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} />
      ) : (
        <BatchGeneratePanel pricing={pricing} balance={balance} loading={loading} token={token} onSubmitMany={onCreateJobs} />
      )}

      <JobList jobs={activeJobs} onRefresh={onRefresh} onCandidatePixelize={onCandidatePixelize} />
    </Stack>
  )
}
