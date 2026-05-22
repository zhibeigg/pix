import { useI18n } from '../i18n'
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
  const { text } = useI18n()
  const activeJobs = jobs.filter((job) => ['pending', 'running'].includes(job.status))
  return (
    <div className="grid gap-6">
      <PageHeader eyebrow={text('生产', 'Production')} title={text('生产工作台', 'Production workspace')} description={text('先试单张，再批量成包；所有任务都会进入作品库和队列记录。', 'Try one asset first, then batch into packs; every job is recorded in the gallery and queue.')} action={(
        <Tabs value={mode} onValueChange={(v) => onModeChange(v as WorkMode)}>
          <TabsList><TabsTrigger value="single">{text('单图试做', 'Single test')}</TabsTrigger><TabsTrigger value="batch">{text('批量生产', 'Batch production')}</TabsTrigger></TabsList>
        </Tabs>
      )} />
      {mode === 'single' ? <SingleGeneratePanel pricing={pricing} loading={loading} token={token} onSubmit={onCreateJob} /> : <BatchGeneratePanel pricing={pricing} balance={balance} loading={loading} token={token} onSubmitMany={onCreateJobs} />}
      <JobList jobs={activeJobs} onRefresh={onRefresh} onCandidatePixelize={onCandidatePixelize} />
    </div>
  )
}
