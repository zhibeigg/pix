import { BatchPanel } from '../components/BatchPanel'
import { GalleryGrid } from '../components/GalleryGrid'
import type { GenerationBatch, GenerationJob } from '../types'

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
  onCopyPath: (path: string) => void
  onRefresh: () => void
}

export function PacksPage({ batches, selectedBatch, selectedBatchId, selectedBatchJobs, selectedJobId, retrying, downloading, onSelectBatch, onClearSelection, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch, onSelectJob, onCopyPath, onRefresh }: PacksPageProps) {
  return (
    <section className="page-grid page-grid-packs">
      <aside className="page-aside page-aside-wide">
        <BatchPanel
          batches={batches}
          selectedBatchId={selectedBatchId}
          onSelectBatch={onSelectBatch}
          onClearSelection={onClearSelection}
          onRetryFailed={onRetryFailed}
          onDownloadBatch={onDownloadBatch}
          onRenameBatch={onRenameBatch}
          onToggleArchive={onToggleArchive}
          onDeleteBatch={onDeleteBatch}
          retrying={retrying}
          downloading={downloading}
          onRefresh={onRefresh}
        />
      </aside>
      <div className="page-main">
        <header className="page-heading">
          <p className="eyebrow">Packs</p>
          <h2>{selectedBatch ? selectedBatch.name : '素材包'}</h2>
          <p>{selectedBatch ? '当前只显示这个素材包里的任务。' : '选择一个素材包，查看该批次的作品、失败项和下载入口。'}</p>
        </header>
        <GalleryGrid jobs={selectedBatch ? selectedBatchJobs : []} subtitle={selectedBatch ? `素材包：${selectedBatch.name}` : '请选择素材包'} selectedJobId={selectedJobId} onSelect={onSelectJob} onCopyPath={onCopyPath} />
      </div>
    </section>
  )
}
