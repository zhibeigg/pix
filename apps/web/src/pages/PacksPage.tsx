import { Box, Stack } from '@mui/material'
import { BatchPanel } from '../components/BatchPanel'
import { GalleryGrid } from '../components/GalleryGrid'
import { PageHeader } from '../components/PageHeader'
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
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(300px, 420px) minmax(0, 1fr)' }, gap: 3, alignItems: 'start' }}>
      <Box sx={{ minWidth: 0 }}>
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
      </Box>
      <Stack spacing={3} sx={{ minWidth: 0 }}>
        <PageHeader
          eyebrow="Packs"
          title={selectedBatch ? selectedBatch.name : '素材包'}
          description={selectedBatch ? '仅显示当前素材包。' : '选择素材包查看作品和失败项。'}
          tint="mint"
        />
        <GalleryGrid jobs={selectedBatch ? selectedBatchJobs : []} subtitle={selectedBatch ? `素材包：${selectedBatch.name}` : '请选择素材包'} selectedJobId={selectedJobId} onSelect={onSelectJob} onCopyPath={onCopyPath} />
      </Stack>
    </Box>
  )
}
