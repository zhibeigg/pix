import { useI18n } from '../i18n'
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
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRetryJob: (job: GenerationJob) => Promise<void>
}

export function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, retryingJobId, onSelectJob, onCandidatePixelize, onCreateJob, onRetryJob }: GalleryPageProps) {
  const { text } = useI18n()
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="grid min-w-0 gap-6">
        <PageHeader eyebrow={text('作品', 'Works')} title={text('作品库', 'Gallery')} description={text('挑选、微调、下载图片。', 'Select, tune, and download images.')} />
        <GalleryGrid jobs={jobs} subtitle={text('全部作品', 'All works')} selectedJobId={selectedJobId} retryingJobId={retryingJobId} onSelect={onSelectJob} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} />
      </div>
      <TuningPanel job={selectedJob} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
    </div>
  )
}
