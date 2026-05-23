import { useState, type DragEvent } from 'react'
import { PackagePlus } from 'lucide-react'
import { useI18n } from '../i18n'
import { AssetPackPanel } from '../components/AssetPackPanel'
import { GalleryGrid } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
import { Alert } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import type { AssetPack, ContactSheetCandidate, GenerationJob } from '../types'

interface PacksPageProps {
  packs: AssetPack[]
  selectedPack: AssetPack | null
  selectedPackId: number | null
  selectedPackJobs: GenerationJob[]
  jobs: GenerationJob[]
  selectedJobId: number | null
  downloading: boolean
  onSelectPack: (pack: AssetPack) => void
  onClearSelection: () => void
  onCreatePack: (name: string) => Promise<void>
  onRenamePack: (pack: AssetPack) => void
  onToggleArchive: (pack: AssetPack) => void
  onDeletePack: (pack: AssetPack) => void
  onExpandPack: (pack: AssetPack) => void
  onDownloadPack: (pack: AssetPack) => void
  onAddJobToPack: (pack: AssetPack, job: GenerationJob) => Promise<void>
  onRemoveJobFromPack: (pack: AssetPack, job: GenerationJob) => Promise<void>
  onSelectJob: (job: GenerationJob) => void
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRefresh: () => void
}

export function PacksPage({ packs, selectedPack, selectedPackId, selectedPackJobs, jobs, selectedJobId, downloading, onSelectPack, onClearSelection, onCreatePack, onRenamePack, onToggleArchive, onDeletePack, onExpandPack, onDownloadPack, onAddJobToPack, onRemoveJobFromPack, onSelectJob, onCandidatePixelize, onRefresh }: PacksPageProps) {
  const { t } = useI18n()
  const [dragOver, setDragOver] = useState(false)
  const successfulJobs = jobs.filter((job) => job.status === 'succeeded' && job.outputs.length > 0)

  function allowDrop(event: DragEvent<HTMLElement>) {
    if (!selectedPack || selectedPack.status !== 'active') return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    setDragOver(true)
  }

  function leaveDrop() {
    setDragOver(false)
  }

  async function dropJob(event: DragEvent<HTMLElement>) {
    if (!selectedPack || selectedPack.status !== 'active') return
    event.preventDefault()
    setDragOver(false)
    const raw = event.dataTransfer.getData('application/x-pix-job-id') || event.dataTransfer.getData('text/plain')
    const jobId = Number(raw)
    const job = successfulJobs.find((item) => item.id === jobId)
    if (job) await onAddJobToPack(selectedPack, job)
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(300px,420px)_minmax(0,1fr)]">
      <AssetPackPanel packs={packs} selectedPackId={selectedPackId} downloading={downloading} onSelectPack={onSelectPack} onClearSelection={onClearSelection} onCreatePack={onCreatePack} onRenamePack={onRenamePack} onToggleArchive={onToggleArchive} onDeletePack={onDeletePack} onExpandPack={onExpandPack} onDownloadPack={onDownloadPack} onRefresh={onRefresh} />
      <div className="grid min-w-0 gap-6">
        <PageHeader eyebrow={t('pages.packs.eyebrow')} title={selectedPack ? selectedPack.name : t('pages.packs.title')} description={selectedPack ? t('pages.packs.selectedDescription') : t('pages.packs.emptyDescription')} />
        <section onDragOver={allowDrop} onDragLeave={leaveDrop} onDrop={(event) => void dropJob(event)} className={`rounded-lg border border-dashed p-4 transition ${dragOver ? 'border-primary bg-primary/10' : 'border-border bg-muted/25'}`}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold"><PackagePlus className="h-4 w-4 text-primary" />{selectedPack ? t('packs.dropToSave') : t('packs.selectFirst')}</div>
            {selectedPack && <div className="flex flex-wrap gap-2"><Badge variant="outline">{t('packs.capacity', { used: selectedPack.item_count, capacity: selectedPack.capacity })}</Badge><Badge variant={selectedPack.remaining_capacity > 0 ? 'success' : 'warning'}>{t('packs.remaining', { count: selectedPack.remaining_capacity })}</Badge></div>}
          </div>
          {selectedPack ? <GalleryGrid jobs={selectedPackJobs} subtitle={t('pages.packs.packSubtitle', { name: selectedPack.name })} selectedJobId={selectedJobId} onSelect={onSelectJob} onCandidatePixelize={onCandidatePixelize} onRemoveFromPack={(job) => onRemoveJobFromPack(selectedPack, job)} /> : <Alert variant="info">{t('packs.selectHint')}</Alert>}
        </section>
        <GalleryGrid jobs={successfulJobs} subtitle={selectedPack ? t('packs.galleryHintSelected') : t('packs.galleryHint')} selectedJobId={selectedJobId} onSelect={onSelectJob} onCandidatePixelize={onCandidatePixelize} onSaveToPack={selectedPack ? (job) => onAddJobToPack(selectedPack, job) : undefined} draggableSucceeded={Boolean(selectedPack)} />
      </div>
    </div>
  )
}
