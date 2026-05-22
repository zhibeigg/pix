import { useI18n } from '../i18n'
import { BatchPanel } from '../components/BatchPanel'
import { GalleryGrid } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
import type { ContactSheetCandidate, GenerationBatch, GenerationJob } from '../types'

interface PacksPageProps {
  batches: GenerationBatch[]
  selectedBatch: GenerationBatch | null
  selectedBatchId: number | null
  selectedBatchJobs: GenerationJob[]
  selectedJobId: number | null
  retrying: boolean
  downloading: boolean
  onSelectBatch: (batch: GenerationBatch) => void
  onClearSelection: () => void
  onRetryFailed: (batch: GenerationBatch) => void
  onDownloadBatch: (batch: GenerationBatch) => void
  onRenameBatch: (batch: GenerationBatch) => void
  onToggleArchive: (batch: GenerationBatch) => void
  onDeleteBatch: (batch: GenerationBatch) => void
  onSelectJob: (job: GenerationJob) => void
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRefresh: () => void
}

export function PacksPage({ batches, selectedBatch, selectedBatchId, selectedBatchJobs, selectedJobId, retrying, downloading, onSelectBatch, onClearSelection, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch, onSelectJob, onCandidatePixelize, onRefresh }: PacksPageProps) {
  const { t } = useI18n()
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(300px,420px)_minmax(0,1fr)]">
      <BatchPanel batches={batches} selectedBatchId={selectedBatchId} onSelectBatch={onSelectBatch} onClearSelection={onClearSelection} onRetryFailed={onRetryFailed} onDownloadBatch={onDownloadBatch} onRenameBatch={onRenameBatch} onToggleArchive={onToggleArchive} onDeleteBatch={onDeleteBatch} retrying={retrying} downloading={downloading} onRefresh={onRefresh} />
      <div className="grid min-w-0 gap-6">
        <PageHeader eyebrow={t('pages.packs.eyebrow')} title={selectedBatch ? selectedBatch.name : t('pages.packs.title')} description={selectedBatch ? t('pages.packs.selectedDescription') : t('pages.packs.emptyDescription')} />
        <GalleryGrid jobs={selectedBatch ? selectedBatchJobs : []} subtitle={selectedBatch ? t('pages.packs.packSubtitle', { name: selectedBatch.name }) : t('pages.packs.selectPack')} selectedJobId={selectedJobId} onSelect={onSelectJob} onCandidatePixelize={onCandidatePixelize} />
      </div>
    </div>
  )
}
