import type { ReactNode } from 'react'
import type { CreditBalance, User } from '../types'
import { PixMetric } from './pix/PixMetric'
import { Button } from './ui/button'

type AppHeroProps = { user: User | null; balance: CreditBalance | null; activeJobs: number; completedJobs: number; failedJobs: number; batchCount: number }

export function AppHero({ balance, activeJobs, completedJobs, failedJobs, batchCount }: AppHeroProps) {
  return (
    <section className="mx-auto grid max-w-6xl gap-8 px-4 py-14 md:grid-cols-[minmax(0,1.15fr)_minmax(320px,.85fr)] md:px-8 md:py-20">
      <div className="space-y-6">
        <div className="inline-flex rounded-full border border-border bg-card px-3 py-1 text-xs font-bold uppercase tracking-[.16em] text-primary">Pix Forge</div>
        <div>
          <h2 className="font-serif text-5xl font-black leading-[.95] tracking-tight md:text-7xl">像素素材的高级工坊</h2>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-muted-foreground">从 prompt 到 AI 原图、网格候选、像素化、素材包和点数系统，一条创作流水线。</p>
        </div>
        <div className="flex flex-wrap gap-3"><Button size="lg" asChild><a href="#auth-panel">进入工作台</a></Button><Button size="lg" variant="outline" asChild><a href="#features">查看能力</a></Button></div>
      </div>
      <div className="grid gap-3 rounded-[2rem] border border-border bg-card/86 p-4 shadow-2xl">
        <MockCard title="实时队列" value={`${activeJobs} 个`} />
        <MockCard title="可用点数" value={`${balance?.available_credits ?? '—'} 点`} />
        <div className="grid grid-cols-3 gap-3"><PixMetric label="完成" value={completedJobs} tone="success" /><PixMetric label="失败" value={failedJobs} tone={failedJobs ? 'danger' : 'default'} /><PixMetric label="素材包" value={batchCount} tone="info" /></div>
      </div>
    </section>
  )
}

function MockCard({ title, value }: { title: ReactNode; value: ReactNode }) {
  return <div className="rounded-3xl border border-border bg-muted/40 p-5"><p className="text-xs font-bold uppercase tracking-[.12em] text-muted-foreground">{title}</p><p className="mt-2 text-3xl font-black">{value}</p></div>
}
