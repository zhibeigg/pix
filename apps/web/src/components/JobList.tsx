import type { GenerationJob } from '../types'

type JobListProps = {
  jobs: GenerationJob[]
  onRefresh: () => void
}

export function JobList({ jobs, onRefresh }: JobListProps) {
  return (
    <section className="panel job-list-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Queue</p>
          <h2>任务队列</h2>
        </div>
        <button className="ghost" onClick={onRefresh}>刷新</button>
      </div>
      <div className="jobs">
        {jobs.length === 0 ? (
          <div className="empty-state">还没有任务。创建一个任务后，启动 worker 即可处理。</div>
        ) : (
          jobs.map((job) => <JobCard job={job} key={job.id} />)
        )}
      </div>
    </section>
  )
}

function JobCard({ job }: { job: GenerationJob }) {
  const output = job.outputs[0]
  return (
    <article className="job-card">
      <div className="job-card-top">
        <div>
          <strong>#{job.id} · {job.job_type}</strong>
          <p>{job.prompt || job.input_image_path || '无输入摘要'}</p>
        </div>
        <span className={`status ${job.status}`}>{job.status}</span>
      </div>
      <div className="job-meta">
        <span>{job.price_credits} credits</span>
        <span>冻结 {job.reserved_credits}</span>
        <span>{new Date(job.created_at).toLocaleString()}</span>
      </div>
      {job.error_message && <pre className="error-box">{job.error_message.slice(0, 600)}</pre>}
      {output && (
        <div className="output-grid">
          <PathLine label="源图" value={output.source_path} />
          <PathLine label="像素图" value={output.pixelized_path} />
          {output.preview_path && <PathLine label="预览" value={output.preview_path} />}
          <PathLine label="meta" value={output.meta_json_path} />
        </div>
      )}
    </article>
  )
}

function PathLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="path-line">
      <span>{label}</span>
      <code title={value}>{value}</code>
    </div>
  )
}
