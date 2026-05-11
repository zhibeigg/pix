import { Box, Stack } from '@mui/material'
import { GalleryGrid } from '../components/GalleryGrid'
import { JobList } from '../components/JobList'
import { PageHeader } from '../components/PageHeader'
import { TuningPanel } from '../components/TuningPanel'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'

interface GalleryPageProps {
  jobs: GenerationJob[]
  selectedJob: GenerationJob | null
  selectedJobId: number | null
  pricing: PricingRule[]
  loading: boolean
  onSelectJob: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRefresh: () => void
}

export function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, onSelectJob, onCopyPath, onCreateJob, onRefresh }: GalleryPageProps) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) minmax(320px, 420px)' }, gap: 3, alignItems: 'start' }}>
      <Stack spacing={3} sx={{ minWidth: 0 }}>
        <PageHeader eyebrow="Library" title="作品库" description="查看全部生成结果，选择作品后可以免费本地微调或发起 AI 微调。" />
        <GalleryGrid jobs={jobs} subtitle="全部作品" selectedJobId={selectedJobId} onSelect={onSelectJob} onCopyPath={onCopyPath} />
        <JobList jobs={jobs.filter((job) => job.status !== 'succeeded')} onRefresh={onRefresh} />
      </Stack>
      <Box sx={{ minWidth: 0 }}>
        <TuningPanel job={selectedJob} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
      </Box>
    </Box>
  )
}
