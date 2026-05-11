import type { KeyboardEvent } from 'react'
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
  function activateBatch(event: KeyboardEvent<HTMLElement>, batch: GenerationBatch) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelectBatch(batch)
    }
  }

  return (
    <section className="panel batch-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Packs</p>
          <h2>素材包</h2>
        </div>
        <button className="ghost compact" type="button" onClick={onRefresh}>刷新</button>
      </div>
      <button className={selectedBatchId === null ? 'compact' : 'ghost compact'} type="button" onClick={onClearSelection}>全部作品</button>
      {batches.length === 0 ? (
        <p className="muted">批量生产后会在这里形成素材包，方便后续按批次管理。</p>
      ) : (
        <div className="batch-list">
          {batches.map((batch) => (
            <article
              className={`batch-card ${selectedBatchId === batch.id ? 'selected' : ''} ${batch.status === 'archived' ? 'archived' : ''}`}
              key={batch.id}
              role="button"
              tabIndex={0}
              aria-selected={selectedBatchId === batch.id}
              onClick={() => onSelectBatch(batch)}
              onKeyDown={(event) => activateBatch(event, batch)}
            >
              <div className="job-card-top">
                <strong>#{batch.id} · {batch.name}</strong>
                <span className="pill">{batch.mode} · {batch.status === 'archived' ? '已归档' : '活跃'}</span>
              </div>
              <div className="job-meta">
                <span>{batch.job_count} 个任务</span>
                <span>{batch.total_price_credits} credits</span>
              </div>
              <p className="muted">
                完成 {batch.succeeded_count} · 失败 {batch.failed_count} · 进行中 {batch.running_count} · 排队 {batch.pending_count}
              </p>
              <div className="batch-actions">
                <button
                  className="ghost compact"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onRenameBatch(batch)
                  }}
                >
                  重命名
                </button>
                <button
                  className="ghost compact"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onToggleArchive(batch)
                  }}
                >
                  {batch.status === 'archived' ? '恢复' : '归档'}
                </button>
                {batch.job_count === 0 && (
                  <button
                    className="ghost compact danger"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onDeleteBatch(batch)
                    }}
                  >
                    删除空包
                  </button>
                )}
                {batch.succeeded_count > 0 && (
                  <button
                    className="ghost compact"
                    type="button"
                    disabled={downloading}
                    onClick={(event) => {
                      event.stopPropagation()
                      onDownloadBatch(batch)
                    }}
                  >
                    {downloading ? '下载中…' : '下载素材包'}
                  </button>
                )}
              {batch.failed_count > 0 && (
                <button
                  className="ghost compact"
                  type="button"
                  disabled={retrying}
                  onClick={(event) => {
                    event.stopPropagation()
                    onRetryFailed(batch)
                  }}
                >
                  {retrying ? '重试中…' : `重试失败项 ${batch.failed_count}`}
                </button>
              )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
