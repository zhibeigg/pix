import { Box, Card, CardContent, Stack, Tab, Tabs, Typography } from '@mui/material'
import { BatchGeneratePanel } from '../components/BatchGeneratePanel'
import { JobList } from '../components/JobList'
import { PageHeader } from '../components/PageHeader'
import { SingleGeneratePanel } from '../components/SingleGeneratePanel'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'

export type WorkMode = 'single' | 'batch'

interface WorkspacePageProps {
  mode: WorkMode
  pricing: PricingRule[]
  jobs: GenerationJob[]
  loading: boolean
  token: string
  onModeChange: (mode: WorkMode) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>
  onRefresh: () => void
}

export function WorkspacePage({ mode, pricing, jobs, loading, token, onModeChange, onCreateJob, onCreateJobs, onRefresh }: WorkspacePageProps) {
  const activeJobs = jobs.filter((job) => ['pending', 'running'].includes(job.status))
  return (
    <Stack spacing={3}>
      <PageHeader eyebrow="Create" title="生产工作台" description="在这里创建单图任务或批量素材包。作品查看、微调和素材包管理分别放在独立页面。" />

      <Card variant="outlined">
        <CardContent>
          <Typography variant="overline" color="primary.main" sx={{ fontWeight: 900 }}>创建模式</Typography>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mt: 1 }}>
            <Tabs value={mode} aria-label="创建模式" onChange={(_, value: WorkMode) => onModeChange(value)}>
              <Tab value="single" label="单图生成" />
              <Tab value="batch" label="批量生产" />
            </Tabs>
          </Box>
        </CardContent>
      </Card>

      {mode === 'single' ? (
        <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} />
      ) : (
        <BatchGeneratePanel pricing={pricing} loading={loading} token={token} onSubmitMany={onCreateJobs} />
      )}

      <JobList jobs={activeJobs} onRefresh={onRefresh} />
    </Stack>
  )
}
