import { Box, Stack } from '@mui/material'
import { GalleryGrid } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
import { TuningPanel } from '../components/TuningPanel'
import type { ContactSheetCandidate, GenerationJob, JobCreateRequest, PricingRule } from '../types'

interface GalleryPageProps {
  jobs: GenerationJob[]
  selectedJob: GenerationJob | null
  selectedJobId: number | null
  pricing: PricingRule[]
  loading: boolean
  onSelectJob: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
}

export function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, onSelectJob, onCopyPath, onCandidatePixelize, onCreateJob }: GalleryPageProps) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) minmax(320px, 420px)' }, gap: 3, alignItems: 'start' }}>
      <Stack spacing={3} sx={{ minWidth: 0 }}>
        <PageHeader eyebrow="作品" title="作品库" description="挑选、微调、复制路径。" tint="sky" />
        <GalleryGrid jobs={jobs} subtitle="全部作品" selectedJobId={selectedJobId} onSelect={onSelectJob} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} />
      </Stack>
      <Box sx={{ minWidth: 0 }}>
        <TuningPanel job={selectedJob} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
      </Box>
    </Box>
  )
}
