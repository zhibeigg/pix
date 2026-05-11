import { Box, Card, CardContent, Stack, Tab, Tabs, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import { BatchGeneratePanel } from '../components/BatchGeneratePanel'
import { JobList } from '../components/JobList'
import { PageHeader } from '../components/PageHeader'
import { SingleGeneratePanel } from '../components/SingleGeneratePanel'
import type { CreditBalance, GenerationJob, JobCreateRequest, PricingRule } from '../types'

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
  onRefresh: () => void
}

export function WorkspacePage({ mode, pricing, balance, jobs, loading, token, onModeChange, onCreateJob, onCreateJobs, onRefresh }: WorkspacePageProps) {
  const activeJobs = jobs.filter((job) => ['pending', 'running'].includes(job.status))
  return (
    <Stack spacing={3}>
      <PageHeader eyebrow="生产" title="生产工作台" description="先试单张，再批量成包。" tint="yellow" />

      <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
        <CardContent>
          <Typography variant="overline" color="text.secondary">创建模式</Typography>
          <Box sx={{ mt: 1, bgcolor: notionTokens.surface, border: 1, borderColor: 'divider', borderRadius: 999, p: .5, width: 'fit-content' }}>
            <Tabs
              value={mode}
              aria-label="创建模式"
              onChange={(_, value: WorkMode) => onModeChange(value)}
              sx={{ minHeight: 0, '& .MuiTabs-indicator': { display: 'none' }, '& .MuiTabs-flexContainer': { gap: .5 }, '& .MuiTab-root': { minHeight: 36, borderRadius: 999, px: 2 }, '& .Mui-selected': { bgcolor: notionTokens.brandNavyDeep, color: `${notionTokens.onDark} !important` } }}
            >
              <Tab value="single" label="单图生成" />
              <Tab value="batch" label="批量生产" />
            </Tabs>
          </Box>
        </CardContent>
      </Card>

      {mode === 'single' ? (
        <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} />
      ) : (
        <BatchGeneratePanel pricing={pricing} balance={balance} loading={loading} token={token} onSubmitMany={onCreateJobs} />
      )}

      <JobList jobs={activeJobs} onRefresh={onRefresh} />
    </Stack>
  )
}
