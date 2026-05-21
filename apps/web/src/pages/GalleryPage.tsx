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
  retryingJobId: number | null
  onSelectJob: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRetryJob: (job: GenerationJob) => Promise<void>
}

export function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, retryingJobId, onSelectJob, onCopyPath, onCandidatePixelize, onCreateJob, onRetryJob }: GalleryPageProps) {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="grid min-w-0 gap-6">
        <PageHeader eyebrow="作品" title="作品库" description="挑选、微调、复制路径。" />
        <GalleryGrid jobs={jobs} subtitle="全部作品" selectedJobId={selectedJobId} retryingJobId={retryingJobId} onSelect={onSelectJob} onCopyPath={onCopyPath} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} />
      </div>
      <TuningPanel job={selectedJob} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
    </div>
  )
}
