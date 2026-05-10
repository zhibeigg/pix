import type { GenerationBatch } from '../types'

type BatchPanelProps = {
  batches: GenerationBatch[]
  onRefresh: () => void
}

export function BatchPanel({ batches, onRefresh }: BatchPanelProps) {
  return (
    <section className="panel batch-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Packs</p>
          <h2>素材包</h2>
        </div>
        <button className="ghost compact" type="button" onClick={onRefresh}>刷新</button>
      </div>
      {batches.length === 0 ? (
        <p className="muted">批量生产后会在这里形成素材包，方便后续按批次管理。</p>
      ) : (
        <div className="batch-list">
          {batches.map((batch) => (
            <article className="batch-card" key={batch.id}>
              <div className="job-card-top">
                <strong>#{batch.id} · {batch.name}</strong>
                <span className="pill">{batch.mode}</span>
              </div>
              <div className="job-meta">
                <span>{batch.job_count} 个任务</span>
                <span>{batch.total_price_credits} credits</span>
              </div>
              <p className="muted">
                完成 {batch.succeeded_count} · 失败 {batch.failed_count} · 进行中 {batch.running_count} · 排队 {batch.pending_count}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
