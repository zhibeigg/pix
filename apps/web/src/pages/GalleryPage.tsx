import * as React from 'react'
import { useI18n } from '../i18n'
import { GalleryGrid } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
import { TuningPanel } from '../components/TuningPanel'
import type { ContactSheetCandidate, GenerationJob, JobCreateRequest, PricingRule, SequenceAlignmentRequest } from '../types'

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
  onDeleteJob: (job: GenerationJob) => Promise<void>
  onSaveSequenceAlignment: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void>
}

export const GalleryPage = React.memo(function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, retryingJobId, onSelectJob, onCandidatePixelize, onCreateJob, onRetryJob, onDeleteJob, onSaveSequenceAlignment }: GalleryPageProps) {
  const { t } = useI18n()
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="grid min-w-0 gap-6">
        <PageHeader eyebrow={t('pages.gallery.eyebrow')} title={t('pages.gallery.title')} description={t('pages.gallery.description')} />
        <GalleryGrid jobs={jobs} subtitle={t('pages.gallery.allWorks')} selectedJobId={selectedJobId} retryingJobId={retryingJobId} onSelect={onSelectJob} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} onDeleteJob={onDeleteJob} onSaveSequenceAlignment={onSaveSequenceAlignment} />
      </div>
      <TuningPanel job={selectedJob} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
    </div>
  )
})
