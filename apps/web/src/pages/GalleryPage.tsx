import * as React from 'react'
import { useI18n } from '../i18n'
import { GalleryGrid } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
import type { ContactSheetCandidate, GalleryQuota, GenerationJob, SequenceAlignmentRequest } from '../types'

interface GalleryPageProps {
  jobs: GenerationJob[]
  selectedJobId: number | null
  loading: boolean
  retryingJobId: number | null
  regeneratingJobId: number | null
  downloadingJobs: boolean
  galleryQuota: GalleryQuota | null
  onExpandGalleryQuota: () => void
  onSelectJob: (job: GenerationJob) => void
  onReuseJob: (job: GenerationJob) => void
  onTuneJob: (job: GenerationJob) => void
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRetryJob: (job: GenerationJob) => Promise<void>
  onRegenerateJob: (job: GenerationJob) => Promise<void>
  onDeleteJob: (job: GenerationJob) => Promise<void>
  onDeleteJobs: (jobs: GenerationJob[]) => Promise<void>
  onDownloadJobs: (jobs: GenerationJob[]) => Promise<void>
  onSaveSequenceAlignment: (job: GenerationJob, payload: SequenceAlignmentRequest) => Promise<void>
  onPublishShare: (job: GenerationJob) => Promise<void>
  onUnpublishShare: (job: GenerationJob) => Promise<void>
}

export const GalleryPage = React.memo(function GalleryPage({ jobs, selectedJobId, retryingJobId, regeneratingJobId, downloadingJobs, galleryQuota, onExpandGalleryQuota, onSelectJob, onReuseJob, onTuneJob, onCandidatePixelize, onRetryJob, onRegenerateJob, onDeleteJob, onDeleteJobs, onDownloadJobs, onSaveSequenceAlignment, onPublishShare, onUnpublishShare }: GalleryPageProps) {
  const { t } = useI18n()
  return (
    <div className="grid min-w-0 gap-6">
      <PageHeader eyebrow={t('pages.gallery.eyebrow')} title={t('pages.gallery.title')} description={t('pages.gallery.description')} />
      <GalleryGrid jobs={jobs} subtitle={t('pages.gallery.allWorks')} selectedJobId={selectedJobId} retryingJobId={retryingJobId} regeneratingJobId={regeneratingJobId} downloadingJobs={downloadingJobs} galleryQuota={galleryQuota} onExpandGalleryQuota={onExpandGalleryQuota} onSelect={onSelectJob} onReuseJob={onReuseJob} onTuneJob={onTuneJob} onCandidatePixelize={onCandidatePixelize} onRetryJob={onRetryJob} onRegenerateJob={onRegenerateJob} onDeleteJob={onDeleteJob} onDeleteJobs={onDeleteJobs} onDownloadJobs={onDownloadJobs} onSaveSequenceAlignment={onSaveSequenceAlignment} onPublishShare={onPublishShare} onUnpublishShare={onUnpublishShare} />
    </div>
  )
})
