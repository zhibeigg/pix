import { useMemo, useState } from 'react'
import { Box, Button, Card, CardActions, CardContent, CardMedia, Chip, Pagination, Stack, Typography } from '@mui/material'
import type { GenerationJob } from '../types'
import { summarizePrompt } from '../pixelize'

type GalleryGridProps = {
  jobs: GenerationJob[]
  selectedJobId: number | null
  subtitle?: string
  onSelect: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
}

const statusLabels: Record<string, string> = {
  pending: '排队中',
  running: '生产中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'primary',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function GalleryGrid({ jobs, subtitle, selectedJobId, onSelect, onCopyPath }: GalleryGridProps) {
  const [page, setPage] = useState(1)
  const pageSize = 80
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { xs: 'flex-start', sm: 'center' } }}>
          <Box>
            <Typography variant="overline" color="primary.main" sx={{ fontWeight: 900 }}>Library</Typography>
            <Typography variant="h4" sx={{ fontWeight: 950 }}>作品网格</Typography>
            {subtitle && <Typography color="text.secondary">{subtitle}</Typography>}
          </Box>
          <Chip label={`${ordered.length} 件作品/任务`} color="secondary" variant="outlined" />
        </Stack>

        {ordered.length === 0 ? (
          <Box sx={{ mt: 3, border: 1, borderStyle: 'dashed', borderColor: 'divider', borderRadius: 2.5, p: 4, bgcolor: 'background.default' }}>
            <Typography variant="h6" sx={{ fontWeight: 900 }}>你的像素工坊还是空的</Typography>
            <Typography color="text.secondary">先用单图生成试一个道具，或粘贴 5-20 行 prompt 开始批量生产。</Typography>
          </Box>
        ) : (
          <Box sx={{ mt: 3, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 1.75 }}>
            {visible.map((job) => {
              const output = job.outputs[0]
              const mainPath = output?.pixelized_path || output?.source_path || job.input_image_path || ''
              const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''
              const selected = selectedJobId === job.id
              return (
                <Card
                  key={job.id}
                  variant="outlined"
                  aria-current={selected ? 'true' : undefined}
                  sx={{
                    minWidth: 0,
                    overflow: 'hidden',
                    cursor: 'default',
                    borderColor: selected ? 'primary.main' : 'divider',
                    boxShadow: selected ? '0 0 0 2px rgba(103,199,255,.18)' : 'none',
                    transition: 'transform .18s ease, border-color .18s ease',
                    '&:hover': { transform: 'translateY(-2px)', borderColor: selected ? 'primary.main' : 'text.secondary' },
                  }}
                >
                  <CardMedia component="div" sx={{ height: 132, display: 'grid', placeItems: 'center', bgcolor: 'background.default', backgroundImage: 'linear-gradient(135deg, rgba(103,199,255,.08), rgba(244,167,220,.06))', imageRendering: 'pixelated' }}>
                    {previewUrl ? (
                      <Box component="img" src={previewUrl} alt={summarizePrompt(job.prompt || job.input_image_path, '作品预览')} loading="lazy" decoding="async" sx={{ width: '100%', height: '100%', objectFit: 'contain', imageRendering: 'pixelated', p: 1.5 }} />
                    ) : (
                      <Chip variant="outlined" color="primary" label={job.status === 'succeeded' ? 'PIX' : statusLabels[job.status] ?? job.status} />
                    )}
                  </CardMedia>
                  <CardContent sx={{ display: 'grid', gap: 1.1 }}>
                    <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1, alignItems: 'flex-start' }}>
                      <Typography sx={{ fontWeight: 900 }}>#{job.id} · {job.job_type}</Typography>
                      <Chip size="small" color={statusColors[job.status] ?? 'default'} label={statusLabels[job.status] ?? job.status} />
                    </Stack>
                    <Typography color="text.secondary" variant="body2">{summarizePrompt(job.prompt || job.input_image_path)}</Typography>
                    <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                      <Chip size="small" variant="outlined" label={`${job.price_credits} credits`} />
                      <Chip size="small" variant="outlined" label={new Date(job.created_at).toLocaleString()} />
                    </Stack>
                    {job.batch_name && <Typography color="text.secondary" variant="caption">素材包：{job.batch_name}</Typography>}
                  </CardContent>
                  <CardActions>
                    <Button size="small" variant={selected ? 'contained' : 'outlined'} aria-pressed={selected} onClick={() => onSelect(job)}>
                      {selected ? '已选中' : '选择作品'}
                    </Button>
                    {mainPath && <Button size="small" variant="text" onClick={() => onCopyPath(mainPath)}>复制路径</Button>}
                  </CardActions>
                </Card>
              )
            })}
          </Box>
        )}
        {ordered.length > pageSize && (
          <Stack sx={{ mt: 3, alignItems: 'center' }}>
            <Pagination count={totalPages} page={safePage} color="primary" onChange={(_, value) => setPage(value)} />
          </Stack>
        )}
      </CardContent>
    </Card>
  )
}
