import type { GenerationJob } from '../types'
import { summarizePrompt } from '../pixelize'

type GalleryGridProps = {
  jobs: GenerationJob[]
  selectedJobId: number | null
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

export function GalleryGrid({ jobs, selectedJobId, onSelect, onCopyPath }: GalleryGridProps) {
  const ordered = [...jobs].sort((a, b) => Number(new Date(b.created_at)) - Number(new Date(a.created_at)))

  return (
    <section className="panel gallery-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Library</p>
          <h2>作品网格</h2>
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
          {ordered.map((job) => {
            const output = job.outputs[0]
            const mainPath = output?.pixelized_path || output?.source_path || job.input_image_path || ''
            const previewUrl = output?.pixelized_url || output?.source_url || job.input_image_url || ''
            return (
              <article
                className={`gallery-card ${selectedJobId === job.id ? 'selected' : ''}`}
                key={job.id}
                onClick={() => onSelect(job)}
              >
                <div className="pixel-preview">
                  {previewUrl ? (
                    <img src={previewUrl} alt={summarizePrompt(job.prompt || job.input_image_path, '作品预览')} />
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
                  {mainPath && (
                    <button
                      className="ghost compact"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        onCopyPath(mainPath)
                      }}
                    >
                      复制输出路径
                    </button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
