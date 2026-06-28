import * as React from 'react'
import { useI18n } from '../i18n'
import { GalleryGrid, type SpriteRowAction } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
import { TuningPanel } from '../components/TuningPanel'
import type { ContactSheetCandidate, GalleryQuota, GenerationJob, JobCreateRequest, PricingRule, SequenceAlignmentRequest } from '../types'

interface GalleryPageProps {
  jobs: GenerationJob[]
  selectedJob: GenerationJob | null
  selectedJobId: number | null
  pricing: PricingRule[]
  loading: boolean
  retryingJobId: number | null
  galleryQuota: GalleryQuota | null
  onExpandGalleryQuota: () => void
  onSelectJob: (job: GenerationJob) => void
  onReuseJob: (job: GenerationJob) => void
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRetryJob: (job: GenerationJob) => Promise<void>
  onDeleteJob: (job: GenerationJob) => Promise<void>
  onDeleteJobs: (jobs: GenerationJob[]) => Promise<void>
  onSaveSequenceAlignment: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void>
}

export const GalleryPage = React.memo(function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, retryingJobId, galleryQuota, onExpandGalleryQuota, onSelectJob, onReuseJob, onCandidatePixelize, onCreateJob, onRetryJob, onDeleteJob, onDeleteJobs, onSaveSequenceAlignment }: GalleryPageProps) {
  const { t } = useI18n()
  const [activeAction, setActiveAction] = React.useState<SpriteRowAction | null>(null)
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="grid min-w-0 gap-6">
        <PageHeader eyebrow={t('pages.gallery.eyebrow')} title={t('pages.gallery.title')} description={t('pages.gallery.description')} />
        <GalleryGrid jobs={jobs} subtitle={t('pages.gallery.allWorks')} selectedJobId={selectedJobId} retryingJobId={retryingJobId} galleryQuota={galleryQuota} onExpandGalleryQuota={onExpandGalleryQuota} onSelect={onSelectJob} onReuseJob={onReuseJob} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} onDeleteJob={onDeleteJob} onDeleteJobs={onDeleteJobs} onSaveSequenceAlignment={onSaveSequenceAlignment} onActiveActionChange={setActiveAction} />
      </div>
      <TuningPanel job={selectedJob} action={activeAction} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
    </div>
  )
})
