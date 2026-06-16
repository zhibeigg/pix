import { useMemo } from 'react'
import { useI18n } from '../i18n'
import { BatchGeneratePanel } from '../components/BatchGeneratePanel'
import { JobList } from '../components/JobList'
import { PageHeader } from '../components/PageHeader'
import { SingleGeneratePanel } from '../components/SingleGeneratePanel'
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs'
import type { ContactSheetCandidate, CreditBalance, GenerationJob, ImageModelsResponse, JobCreateRequest, PricingDiscount, PricingRule } from '../types'

export type WorkMode = 'single' | 'batch'
export type ReuseJobSeed = { revision: number; job: GenerationJob }

interface WorkspacePageProps {
  mode: WorkMode
  pricing: PricingRule[]
  discount?: PricingDiscount | null
  balance: CreditBalance | null
  jobs: GenerationJob[]
  loading: boolean
  token: string
  imageModels: ImageModelsResponse
  reuseJobSeed?: ReuseJobSeed | null
  onModeChange: (mode: WorkMode) => void
  onCreateJob: (payload: JobCreateRequest) => Promise<void>
  onCreateJobs: (payloads: JobCreateRequest[], batchName?: string, mode?: string) => Promise<void>
  onCandidatePixelize: (job: GenerationJob, candidate: ContactSheetCandidate) => Promise<void>
  onRefresh: () => void
}

export function WorkspacePage({ mode, pricing, discount, balance, jobs, loading, token, imageModels, reuseJobSeed, onModeChange, onCreateJob, onCreateJobs, onCandidatePixelize, onRefresh }: WorkspacePageProps) {
  const { t } = useI18n()
  const activeJobs = useMemo(() => jobs.filter((job) => ['pending', 'running'].includes(job.status)), [jobs])
  return (
    <div className="grid gap-6">
      <PageHeader eyebrow={t('pages.workspace.eyebrow')} title={t('pages.workspace.title')} description={t('pages.workspace.description')} action={(
        <Tabs value={mode} onValueChange={(v) => onModeChange(v as WorkMode)}>
          <TabsList><TabsTrigger value="single">{t('pages.workspace.single')}</TabsTrigger><TabsTrigger value="batch">{t('pages.workspace.batch')}</TabsTrigger></TabsList>
        </Tabs>
      )} />
      {mode === 'single' ? <SingleGeneratePanel pricing={pricing} discount={discount} loading={loading} token={token} imageModels={imageModels} reuseJobSeed={reuseJobSeed} onSubmit={onCreateJob} /> : <BatchGeneratePanel pricing={pricing} discount={discount} balance={balance} loading={loading} token={token} imageModels={imageModels} onSubmitMany={onCreateJobs} />}
      <JobList jobs={activeJobs} onRefresh={onRefresh} onCandidatePixelize={onCandidatePixelize} />
    </div>
  )
}
