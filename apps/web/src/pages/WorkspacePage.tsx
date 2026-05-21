import { BatchGeneratePanel } from '../components/BatchGeneratePanel'
import { JobList } from '../components/JobList'
import { PageHeader } from '../components/PageHeader'
import { SingleGeneratePanel } from '../components/SingleGeneratePanel'
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs'
import type { ContactSheetCandidate, CreditBalance, GenerationJob, JobCreateRequest, PricingRule } from '../types'

export type WorkMode = 'single' | 'batch'

interface WorkspacePageProps {
  mode: WorkMode
  pricing: PricingRule[]
  balance: CreditBalance | null
  jobs: GenerationJob[]
  loading: boolean
  token: string
  onModeChange: (mode: WorkMode) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRefresh: () => void
}

export function WorkspacePage({ mode, pricing, balance, jobs, loading, token, onModeChange, onCreateJob, onCreateJobs, onCandidatePixelize, onRefresh }: WorkspacePageProps) {
  const activeJobs = jobs.filter((job) => ['pending', 'running'].includes(job.status))
  return (
    <div className="grid gap-6">
      <PageHeader eyebrow="生产" title="生产工作台" description="先试单张，再批量成包；所有任务都会进入作品库和队列记录。" action={(
        <Tabs value={mode} onValueChange={(v) => onModeChange(v as WorkMode)}>
          <TabsList><TabsTrigger value="single">单图试做</TabsTrigger><TabsTrigger value="batch">批量生产</TabsTrigger></TabsList>
        </Tabs>
      )} />
      {mode === 'single' ? <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} /> : <BatchGeneratePanel pricing={pricing} balance={balance} loading={loading} token={token} onSubmitMany={onCreateJobs} />}
      <JobList jobs={activeJobs} onRefresh={onRefresh} onCandidatePixelize={onCandidatePixelize} />
    </div>
  )
}
