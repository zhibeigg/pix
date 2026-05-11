import { Alert, Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import type { GenerationBatch } from '../types'

type BatchPanelProps = {
  batches: GenerationBatch[]
  selectedBatchId: number | null
  onSelectBatch: (batch: GenerationBatch) => void
  onClearSelection: () => void
  onRetryFailed: (batch: GenerationBatch) => void
  onDownloadBatch: (batch: GenerationBatch) => void
  onRenameBatch: (batch: GenerationBatch) => void
  onToggleArchive: (batch: GenerationBatch) => void
  onDeleteBatch: (batch: GenerationBatch) => void
  retrying: boolean
  downloading: boolean
  onRefresh: () => void
}

export function BatchPanel({ batches, selectedBatchId, onSelectBatch, onClearSelection, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch, retrying, downloading, onRefresh }: BatchPanelProps) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 900 }}>Packs</Typography>
              <Typography variant="h4" sx={{ fontWeight: 950 }}>素材包</Typography>
            </Box>
            <Button variant="outlined" size="small" onClick={onRefresh}>刷新</Button>
          </Stack>
          <Button variant={selectedBatchId === null ? 'contained' : 'outlined'} size="small" onClick={onClearSelection}>全部作品</Button>
          {batches.length === 0 ? (
            <Alert severity="info">批量生产后会在这里形成素材包，方便后续按批次管理。</Alert>
          ) : (
            <Stack spacing={1.5}>
              {batches.map((batch) => (
                <BatchCard
                  batch={batch}
                  selected={selectedBatchId === batch.id}
                  key={batch.id}
                  retrying={retrying}
                  downloading={downloading}
                  onSelectBatch={onSelectBatch}
                  onRetryFailed={onRetryFailed}
                  onDownloadBatch={onDownloadBatch}
                  onRenameBatch={onRenameBatch}
                  onToggleArchive={onToggleArchive}
                  onDeleteBatch={onDeleteBatch}
                />
              ))}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

function BatchCard({ batch, selected, retrying, downloading, onSelectBatch, onRetryFailed, onDownloadBatch, onRenameBatch, onToggleArchive, onDeleteBatch }: {
  batch: GenerationBatch
  selected: boolean
  retrying: boolean
  downloading: boolean
  onSelectBatch: (batch: GenerationBatch) => void
  onRetryFailed: (batch: GenerationBatch) => void
  onDownloadBatch: (batch: GenerationBatch) => void
  onRenameBatch: (batch: GenerationBatch) => void
  onToggleArchive: (batch: GenerationBatch) => void
  onDeleteBatch: (batch: GenerationBatch) => void
}) {
  return (
    <Card
      variant="outlined"
      aria-current={selected ? 'true' : undefined}
      sx={{
        bgcolor: 'background.default',
        opacity: batch.status === 'archived' ? 0.64 : 1,
        borderColor: selected ? 'primary.main' : 'divider',
        boxShadow: selected ? '0 0 0 2px rgba(103,199,255,.18)' : 'none',
      }}
    >
      <CardContent>
        <Stack spacing={1.25}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1.5, alignItems: 'flex-start' }}>
            <Typography sx={{ fontWeight: 900 }}>#{batch.id} · {batch.name}</Typography>
            <Chip size="small" variant="outlined" color={batch.status === 'archived' ? 'default' : 'secondary'} label={`${batch.mode} · ${batch.status === 'archived' ? '已归档' : '活跃'}`} />
          </Stack>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Chip size="small" variant="outlined" label={`${batch.job_count} 个任务`} />
            <Chip size="small" variant="outlined" label={`${batch.total_price_credits} credits`} />
          </Stack>
          <Typography color="text.secondary" variant="body2">
            完成 {batch.succeeded_count} · 失败 {batch.failed_count} · 进行中 {batch.running_count} · 排队 {batch.pending_count}
          </Typography>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Button size="small" variant={selected ? 'contained' : 'outlined'} aria-pressed={selected} onClick={() => onSelectBatch(batch)}>
              {selected ? '当前素材包' : '查看素材包'}
            </Button>
            <Button size="small" variant="outlined" onClick={() => onRenameBatch(batch)}>重命名</Button>
            <Button size="small" variant="outlined" onClick={() => onToggleArchive(batch)}>{batch.status === 'archived' ? '恢复' : '归档'}</Button>
            {batch.job_count === 0 && <Button size="small" color="error" variant="outlined" onClick={() => onDeleteBatch(batch)}>删除空包</Button>}
            {batch.succeeded_count > 0 && <Button size="small" variant="outlined" disabled={downloading} onClick={() => onDownloadBatch(batch)}>{downloading ? '下载中…' : '下载素材包'}</Button>}
            {batch.failed_count > 0 && <Button size="small" variant="outlined" disabled={retrying} onClick={() => onRetryFailed(batch)}>{retrying ? '重试中…' : `重试失败项 ${batch.failed_count}`}</Button>}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}
