import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Chip, LinearProgress, Menu, MenuItem, Stack, Typography } from '@mui/material'
import { notionTokens } from '../theme'
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
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent sx={{ p: { xs: 2, md: 2.4 } }}>
        <Stack spacing={2}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="text.secondary">素材包</Typography>
              <Typography variant="h4">批量素材包</Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              <Button variant={selectedBatchId === null ? 'contained' : 'outlined'} size="small" onClick={onClearSelection}>全部作品</Button>
              <Button variant="outlined" size="small" onClick={onRefresh}>刷新</Button>
            </Stack>
          </Stack>
          {batches.length === 0 ? (
            <Alert severity="info">批量生产后会出现在这里；素材包可下载、归档或只重试失败项。</Alert>
          ) : (
            <Stack spacing={1.25}>
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
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)
  const progress = batch.job_count > 0 ? Math.round((batch.succeeded_count / batch.job_count) * 100) : 0
  const archived = batch.status === 'archived'

  function close() {
    setAnchorEl(null)
  }

  function run(action: () => void) {
    close()
    action()
  }

  return (
    <Card
      variant="outlined"
      aria-current={selected ? 'true' : undefined}
      sx={{
        position: 'relative',
        overflow: 'hidden',
        bgcolor: selected ? notionTokens.surface : notionTokens.canvas,
        opacity: archived ? 0.68 : 1,
        borderColor: selected ? notionTokens.primary : notionTokens.hairline,
        borderWidth: selected ? 2 : 1,
        boxShadow: selected ? notionTokens.focusRing : 'none',
        transition: 'transform .18s ease, box-shadow .18s ease, border-color .18s ease',
        '&:hover': { transform: 'translateY(-2px)', borderColor: notionTokens.hairlineStrong, boxShadow: selected ? notionTokens.focusRing : notionTokens.liftShadow },
        '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } },
        '&::before': selected ? {
          content: '""',
          position: 'absolute',
          left: 0,
          top: '12%',
          bottom: '12%',
          width: 3,
          borderRadius: 999,
          bgcolor: notionTokens.primary,
        } : undefined,
      }}
    >
      <CardContent sx={{ p: 1.6, '&:last-child': { pb: 1.6 } }}>
        <Stack spacing={1.35}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1.5, alignItems: 'flex-start' }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 600 }} noWrap>#{batch.id} · {batch.name}</Typography>
              <Typography color="text.secondary" variant="body2">{modeLabel(batch.mode)} · {batch.total_price_credits} 点 · {archived ? '已归档' : '活跃'}</Typography>
            </Box>
            <Chip size="small" sx={{ bgcolor: progress === 100 ? notionTokens.tintMint : notionTokens.surface }} label={`${progress}%`} />
          </Stack>

          <Box>
            <LinearProgress variant="determinate" value={progress} sx={{ height: 7, borderRadius: 999, bgcolor: notionTokens.surface, '& .MuiLinearProgress-bar': { bgcolor: batch.failed_count ? notionTokens.warning : notionTokens.success } }} />
          </Box>

          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: .75 }}>
            <Chip size="small" variant="outlined" label={`${batch.job_count} 个素材`} />
            <Chip size="small" variant="outlined" label={`完成 ${batch.succeeded_count}`} />
            {batch.failed_count > 0 && <Chip size="small" sx={{ bgcolor: notionTokens.tintRose }} label={`失败 ${batch.failed_count}`} />}
            {(batch.running_count > 0 || batch.pending_count > 0) && <Chip size="small" sx={{ bgcolor: notionTokens.tintSky }} label={`生产中 ${batch.running_count + batch.pending_count}`} />}
          </Stack>

          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: .75 }}>
            <Button size="small" variant={selected ? 'contained' : 'outlined'} aria-pressed={selected} onClick={() => onSelectBatch(batch)}>
              {selected ? '当前素材包' : '打开素材包'}
            </Button>
            {batch.succeeded_count > 0 && <Button size="small" variant="outlined" disabled={downloading} onClick={() => onDownloadBatch(batch)}>{downloading ? '下载中…' : '下载 ZIP'}</Button>}
            {batch.failed_count > 0 && <Button size="small" variant="outlined" disabled={retrying} onClick={() => onRetryFailed(batch)}>{retrying ? '重试中…' : `重试失败项 ${batch.failed_count}`}</Button>}
            <Button size="small" variant="text" onClick={(event) => setAnchorEl(event.currentTarget)} aria-controls={open ? `batch-menu-${batch.id}` : undefined} aria-haspopup="true" aria-expanded={open ? 'true' : undefined}>更多</Button>
          </Stack>

          <Menu id={`batch-menu-${batch.id}`} anchorEl={anchorEl} open={open} onClose={close}>
            <MenuItem onClick={() => run(() => onRenameBatch(batch))}>重命名素材包</MenuItem>
            <MenuItem onClick={() => run(() => onToggleArchive(batch))}>{archived ? '恢复到活跃' : '归档素材包'}</MenuItem>
            {batch.job_count === 0 && <MenuItem onClick={() => run(() => onDeleteBatch(batch))}>删除空素材包</MenuItem>}
          </Menu>
        </Stack>
      </CardContent>
    </Card>
  )
}

function modeLabel(mode: string) {
  const labels: Record<string, string> = {
    asset: '素材直出',
    text_to_image: '文字生成',
    image_to_image: '参考图微调',
    local_pixelize: '本地像素化',
    mixed: '混合批次',
  }
  return labels[mode] ?? mode
}
