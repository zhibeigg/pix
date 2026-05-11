import { GalleryGrid } from '../components/GalleryGrid'
import { JobList } from '../components/JobList'
import { TuningPanel } from '../components/TuningPanel'
import type { GenerationJob, JobCreateRequest, PricingRule } from '../types'

interface GalleryPageProps {
  jobs: GenerationJob[]
  selectedJob: GenerationJob | null
  selectedJobId: number | null
  pricing: PricingRule[]
  loading: boolean
  onSelectJob: (job: GenerationJob) => void
  onCopyPath: (path: string) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onRefresh: () => void
}

export function GalleryPage({ jobs, selectedJob, selectedJobId, pricing, loading, onSelectJob, onCopyPath, onCreateJob, onRefresh }: GalleryPageProps) {
  return (
    <section className="page-grid page-grid-gallery">
      <div className="page-main">
        <header className="page-heading">
          <p className="eyebrow">Library</p>
          <h2>作品库</h2>
          <p>查看全部生成结果，选择作品后可以免费本地微调或发起 AI 微调。</p>
        </header>
        <GalleryGrid jobs={jobs} subtitle="全部作品" selectedJobId={selectedJobId} onSelect={onSelectJob} onCopyPath={onCopyPath} />
        <JobList jobs={jobs.filter((job) => job.status !== 'succeeded')} onRefresh={onRefresh} />
      </div>
      <aside className="page-aside">
        <TuningPanel job={selectedJob} pricing={pricing} loading={loading} onSubmit={onCreateJob} />
      </aside>
    </section>
  )
}
