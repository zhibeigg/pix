import { useMemo, useState } from 'react'
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

export function GalleryGrid({ jobs, subtitle, selectedJobId, onSelect, onCopyPath }: GalleryGridProps) {
  const [page, setPage] = useState(1)
  const pageSize = 80
  const ordered = useMemo(() => [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at))), [jobs])
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const visible = ordered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <section className="panel gallery-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Library</p>
          <h2>作品网格</h2>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
        <span className="price-tag">{ordered.length} 件作品/任务</span>
      </div>
      {ordered.length === 0 ? (
        <div className="empty-gallery">
          <h3>你的像素工坊还是空的</h3>
          <p>先用单图生成试一个道具，或粘贴 5-20 行 prompt 开始批量生产。</p>
        </div>
      ) : (
        <div className="gallery-grid">
          {visible.map((job) => {
            const output = job.outputs[0]
            const mainPath = output?.pixelized_path || output?.source_path || job.input_image_path || ''
            const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''
            return (
              <article
                className={`gallery-card ${selectedJobId === job.id ? 'selected' : ''}`}
                key={job.id}
                aria-current={selectedJobId === job.id ? 'true' : undefined}
              >
                <div className="pixel-preview">
                  {previewUrl ? (
                    <img src={previewUrl} alt={summarizePrompt(job.prompt || job.input_image_path, '作品预览')} loading="lazy" decoding="async" />
                  ) : (
                    <span>{job.status === 'succeeded' ? 'PIX' : statusLabels[job.status] ?? job.status}</span>
                  )}
                </div>
                <div className="gallery-card-body">
                  <div className="job-card-top">
                    <strong>#{job.id} · {job.job_type}</strong>
                    <span className={`status ${job.status}`}>{statusLabels[job.status] ?? job.status}</span>
                  </div>
                  <p>{summarizePrompt(job.prompt || job.input_image_path)}</p>
                  <div className="job-meta">
                    <span>{job.price_credits} credits</span>
                    <span>{new Date(job.created_at).toLocaleString()}</span>
                  </div>
                  {job.batch_name && <p className="muted">素材包：{job.batch_name}</p>}
                  <div className="card-actions">
                    <button
                      className={selectedJobId === job.id ? 'compact' : 'ghost compact'}
                      type="button"
                      aria-pressed={selectedJobId === job.id}
                      onClick={() => onSelect(job)}
                    >
                      {selectedJobId === job.id ? '已选中' : '选择作品'}
                    </button>
                    {mainPath && (
                      <button
                        className="ghost compact"
                        type="button"
                        onClick={() => onCopyPath(mainPath)}
                      >
                        复制路径
                      </button>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
      {ordered.length > pageSize && (
        <div className="pager" aria-label="作品分页">
          <button className="ghost compact" type="button" disabled={safePage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</button>
          <span className="muted">第 {safePage} / {totalPages} 页</span>
          <button className="ghost compact" type="button" disabled={safePage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>下一页</button>
        </div>
      )}
    </section>
  )
}
