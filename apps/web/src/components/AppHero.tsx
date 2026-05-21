import type { ReactNode } from 'react'
import type { CreditBalance, User } from '../types'
import { PixMetric } from './pix/PixMetric'
import { Button } from './ui/button'

const heroDots = [
  'left-[7%] top-[18%] bg-[hsl(var(--pix-peach))]',
  'left-[16%] top-[44%] bg-[hsl(var(--pix-rose))]',
  'left-[28%] bottom-[18%] bg-[hsl(var(--pix-lavender))]',
  'right-[24%] top-[16%] bg-[hsl(var(--pix-yellow))]',
  'right-[12%] top-[42%] bg-[hsl(var(--pix-mint))]',
  'right-[8%] bottom-[20%] bg-[hsl(var(--pix-sky))]',
]

const workflowColumns = [
  {
    title: 'Prompt queue',
    eyebrow: '01',
    tint: 'bg-[hsl(var(--pix-peach))]',
    items: ['暗月骑士', '星盐药瓶', '铜芽齿轮'],
  },
  {
    title: 'Pixel grid',
    eyebrow: '02',
    tint: 'bg-[hsl(var(--pix-sky))]',
    items: ['64×64', '16 colors', '透明 PNG'],
  },
  {
    title: 'Delivery pack',
    eyebrow: '03',
    tint: 'bg-[hsl(var(--pix-mint))]',
    items: ['ZIP 导出', '路径复制', '失败重试'],
  },
]

type AppHeroProps = {
  user: User | null
  balance: CreditBalance | null
  activeJobs: number
  completedJobs: number
  failedJobs: number
  batchCount: number
}

export function AppHero({ user, balance, activeJobs, completedJobs, failedJobs, batchCount }: AppHeroProps) {
  return (
    <section className="relative isolate overflow-hidden bg-background px-4 py-14 text-foreground md:px-8 md:py-20 lg:py-24 dark:bg-[hsl(var(--pix-navy))] dark:text-white lg:dark:py-[120px]">
      <HeroSurfaceDecor />
      <div className="relative z-10 mx-auto grid max-w-7xl gap-10">
        <div className="mx-auto max-w-5xl text-center">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-[hsl(var(--pix-steel))] shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:border-white/15 dark:bg-white/10 dark:text-white/75 dark:shadow-none">
            <span className="h-2 w-2 rounded-[3px] bg-primary dark:bg-[hsl(var(--pix-amber))]" />
            Pix Forge Workspace
          </div>
          <h2 className="mt-6 text-[40px] font-semibold leading-[1.05] tracking-[-1.4px] text-[hsl(var(--pix-ink))] md:text-[64px] md:tracking-[-2px] xl:text-[80px] dark:text-white">
            像素素材生产，<br className="hidden md:block" />一次整理到交付。
          </h2>
          <p className="mx-auto mt-5 max-w-3xl text-lg leading-[1.55] text-[hsl(var(--pix-slate))] dark:text-white/70">
            从 prompt、AI 原图、Pixel Grid、透明 PNG 到素材包和点数系统，用 Notion 式清晰界面把游戏素材生产线收进一个工作区。
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild><a href={user ? '#/workspace' : '#auth-panel'}>进入工作台</a></Button>
            <Button size="lg" variant="outline" className="border-[hsl(var(--pix-stone))]/45 bg-card text-[hsl(var(--pix-ink))] hover:bg-[hsl(var(--secondary))] dark:border-white/45 dark:bg-transparent dark:text-white dark:hover:bg-white/10" asChild><a href="#workflow">查看生产线</a></Button>
          </div>
          <div className="mt-6 flex flex-wrap justify-center gap-2 text-sm text-[hsl(var(--pix-steel))] dark:text-white/65">
            {['单图生成', '批量素材包', '序列帧预览', '透明 PNG 导出'].map((item) => <span key={item} className="rounded-full border border-border bg-card px-3 py-1 dark:border-white/15 dark:bg-white/7">{item}</span>)}
          </div>
        </div>

        <div className="mx-auto grid w-full max-w-6xl gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <WorkspaceMockup balance={balance} activeJobs={activeJobs} batchCount={batchCount} />
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            <PixMetric label="完成" value={completedJobs} tone="success" className="dark:border-white/15" />
            <PixMetric label="失败" value={failedJobs} tone={failedJobs ? 'danger' : 'default'} className="dark:border-white/15 dark:bg-white/7 dark:text-white" />
            <PixMetric label="活跃" value={activeJobs} tone="info" className="dark:border-white/15" />
          </div>
        </div>
      </div>
    </section>
  )
}

function HeroSurfaceDecor() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-72 bg-[linear-gradient(180deg,hsl(var(--secondary)),transparent)] dark:hidden" />
      <div className="absolute left-1/2 top-16 h-[520px] w-[920px] -translate-x-1/2 rounded-full bg-[hsl(var(--pix-cream))] opacity-70 blur-3xl dark:hidden" />
      <div className="absolute inset-0 hidden bg-[radial-gradient(circle_at_50%_-20%,hsl(var(--pix-navy-mid)/.72),transparent_48%)] dark:block" />
      <div className="absolute inset-x-0 bottom-0 hidden h-44 bg-[linear-gradient(0deg,hsl(var(--pix-navy-deep)/.58),transparent)] dark:block" />
      {heroDots.map((style) => <span key={style} className={`absolute h-5 w-5 rounded-[6px] border border-white/70 shadow-[0_10px_24px_rgba(15,15,15,0.10)] dark:border-white/12 dark:shadow-[0_10px_24px_rgba(0,0,0,0.18)] ${style}`} />)}
      <svg className="absolute -left-20 top-20 h-64 w-64 text-[hsl(var(--pix-navy))]/10 dark:text-white/12" viewBox="0 0 240 240" fill="none">
        <path d="M18 120C62 38 160 34 210 92C256 146 190 220 112 204C48 190-6 164 18 120Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M44 80C92 128 132 150 206 140M58 154C104 106 142 78 196 76M70 196C84 126 100 72 124 24" stroke="currentColor" strokeWidth="1" />
      </svg>
      <svg className="absolute -right-12 top-24 h-72 w-72 rotate-12 text-[hsl(var(--pix-navy))]/10 dark:text-white/10" viewBox="0 0 260 260" fill="none">
        <path d="M40 42L218 70L184 222L58 194L40 42Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M62 84L206 104M66 126L198 144M70 168L190 184M102 52L88 202M154 62L138 212" stroke="currentColor" strokeWidth="1" />
      </svg>
    </div>
  )
}

function WorkspaceMockup({ balance, activeJobs, batchCount }: { balance: CreditBalance | null; activeJobs: number; batchCount: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card text-left text-[hsl(var(--pix-ink))] shadow-[0_24px_48px_-8px_rgba(15,15,15,0.20)] dark:border-white/12 dark:bg-[hsl(var(--pix-paper))] dark:text-[hsl(var(--pix-paper-ink))] dark:shadow-[0_34px_90px_-26px_rgba(0,0,0,0.75)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 dark:border-[hsl(var(--pix-paper-border))]">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
          <span className="h-3 w-3 rounded-full bg-[#ffbd2e]" />
          <span className="h-3 w-3 rounded-full bg-[#28c840]" />
        </div>
        <p className="text-sm font-medium text-[hsl(var(--pix-steel))] dark:text-[hsl(var(--pix-paper-steel))]">Pix HQ / Asset pipeline</p>
      </div>
      <div className="grid md:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden border-r border-border bg-[hsl(var(--secondary))] p-4 md:block dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper-soft))]">
          <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-stone))] dark:text-[hsl(var(--pix-paper-steel))]">Workspace</p>
          <div className="mt-4 grid gap-2 text-sm">
            {['Production', 'Gallery', 'Packs', 'Billing'].map((item, index) => <div key={item} className={`rounded-md px-3 py-2 ${index === 0 ? 'bg-card font-medium shadow-[0_1px_2px_rgba(15,15,15,0.04)] dark:bg-[hsl(var(--pix-paper))]' : 'text-[hsl(var(--pix-steel))] dark:text-[hsl(var(--pix-paper-steel))]'}`}>{item}</div>)}
          </div>
          <div className="mt-6 rounded-lg border border-border bg-card p-3 dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper))]">
            <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-stone))] dark:text-[hsl(var(--pix-paper-steel))]">Credits</p>
            <p className="mt-2 text-2xl font-semibold">{balance?.available_credits ?? '—'}</p>
          </div>
        </aside>
        <div className="p-4 md:p-6">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[1px] text-primary">Live workspace mockup</p>
              <h3 className="mt-1 text-[28px] font-semibold leading-[1.25]">素材生产看板</h3>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <MiniStat label="队列" value={`${activeJobs}`} />
              <MiniStat label="点数" value={`${balance?.available_credits ?? '—'}`} />
              <MiniStat label="素材包" value={`${batchCount}`} />
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {workflowColumns.map((column) => <MockColumn key={column.title} {...column} />)}
          </div>
        </div>
      </div>
    </div>
  )
}

function MiniStat({ label, value }: { label: ReactNode; value: ReactNode }) {
  return <div className="rounded-md border border-border bg-[hsl(var(--secondary))] px-3 py-2 dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper-soft))]"><p className="text-[11px] text-[hsl(var(--pix-steel))] dark:text-[hsl(var(--pix-paper-steel))]">{label}</p><p className="text-lg font-semibold leading-tight">{value}</p></div>
}

function MockColumn({ title, eyebrow, tint, items }: { title: string; eyebrow: string; tint: string; items: string[] }) {
  return (
    <article className="rounded-lg border border-border bg-card p-3 dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper))]">
      <div className={`rounded-md px-3 py-2 ${tint}`}>
        <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-steel))]">{eyebrow}</p>
        <p className="mt-1 text-sm font-semibold">{title}</p>
      </div>
      <div className="mt-3 grid gap-2">
        {items.map((item) => <div key={item} className="rounded-md border border-border bg-[hsl(var(--secondary))] px-3 py-2 text-sm text-[hsl(var(--pix-slate))] dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper-soft))] dark:text-[hsl(var(--pix-paper-slate))]">{item}</div>)}
      </div>
    </article>
  )
}
