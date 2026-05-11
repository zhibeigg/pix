import { BatchGeneratePanel } from '../components/BatchGeneratePanel'
import { JobList } from '../components/JobList'
import { SingleGeneratePanel } from '../components/SingleGeneratePanel'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'

export type WorkMode = 'single' | 'batch'

interface WorkspacePageProps {
  mode: WorkMode
  pricing: PricingRule[]
  jobs: GenerationJob[]
  loading: boolean
  token: string
  onModeChange: (mode: WorkMode) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>
  onRefresh: () => void
}

export function WorkspacePage({ mode, pricing, jobs, loading, token, onModeChange, onCreateJob, onCreateJobs, onRefresh }: WorkspacePageProps) {
  const activeJobs = jobs.filter((job) => ['pending', 'running'].includes(job.status))
  return (
    <section className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">Create</p>
        <h2>生产工作台</h2>
        <p>在这里创建单图任务或批量素材包。作品查看、微调和素材包管理分别放在独立页面。</p>
      </header>

      <section className="panel mode-panel">
        <p className="eyebrow">创建模式</p>
        <div className="mode-tabs" role="tablist" aria-label="创建模式">
          <button className={mode === 'single' ? '' : 'ghost'} type="button" role="tab" aria-selected={mode === 'single'} onClick={() => onModeChange('single')}>单图生成</button>
          <button className={mode === 'batch' ? '' : 'ghost'} type="button" role="tab" aria-selected={mode === 'batch'} onClick={() => onModeChange('batch')}>批量生产</button>
        </div>
      </section>

      {mode === 'single' ? (
        <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} />
      ) : (
        <BatchGeneratePanel pricing={pricing} loading={loading} token={token} onSubmitMany={onCreateJobs} />
      )}

      <JobList jobs={activeJobs} onRefresh={onRefresh} />
    </section>
  )
}
