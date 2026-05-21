import type { ReactNode } from 'react'
import type { CreditBalance, User } from '../types'
import { PixMetric } from './pix/PixMetric'
import { Button } from './ui/button'

type AppHeroProps = { user: User | null; balance: CreditBalance | null; activeJobs: number; completedJobs: number; failedJobs: number; batchCount: number }

const dotStyles = [
  'left-[8%] top-[18%] bg-[hsl(var(--pix-brand-orange))]',
  'left-[18%] top-[32%] bg-[hsl(var(--pix-brand-pink))]',
  'right-[18%] top-[18%] bg-[hsl(var(--pix-brand-yellow))]',
  'right-[8%] top-[38%] bg-[hsl(var(--pix-brand-teal))]',
  'left-[28%] bottom-[18%] bg-primary',
  'right-[30%] bottom-[20%] bg-[hsl(var(--pix-brand-green))]',
]

export function AppHero({ balance, activeJobs, completedJobs, failedJobs, batchCount }: AppHeroProps) {
  return (
    <section className="relative isolate overflow-hidden bg-[hsl(var(--pix-navy))] px-4 py-16 text-white md:px-8 md:py-24 lg:py-[120px]">
      <HeroDecor />
      <div className="relative z-10 mx-auto grid max-w-7xl gap-10 text-center">
        <div className="mx-auto max-w-4xl">
          <div className="mx-auto inline-flex rounded-full bg-white/10 px-3 py-1 text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-white/75 ring-1 ring-white/15">Pix Forge</div>
          <h2 className="mt-6 text-5xl font-semibold leading-[1.05] tracking-[-1.5px] md:text-7xl xl:text-[80px]">Meet the pixel shift.</h2>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-[1.5] text-white/70">从 prompt 到 AI 原图、网格候选、像素化、素材包和点数系统，把创意变成可交付的游戏素材工作区。</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild><a href="#auth-panel">进入工作台</a></Button>
            <Button size="lg" variant="outline" className="border-white/45 text-white hover:bg-white/10" asChild><a href="#workflow">查看能力</a></Button>
          </div>
        </div>

        <div className="mx-auto w-full max-w-6xl rounded-lg border border-border bg-white p-0 text-left text-[hsl(var(--pix-ink))] shadow-[0_24px_48px_-8px_rgba(15,15,15,0.20)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#ffbd2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            </div>
            <p className="text-sm font-medium text-[hsl(var(--pix-steel))]">Pix HQ / Asset pipeline</p>
          </div>
          <div className="grid gap-0 md:grid-cols-[220px_minmax(0,1fr)]">
            <aside className="hidden border-r border-border bg-[hsl(var(--secondary))] p-4 md:block">
              <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-stone))]">Workspace</p>
              <div className="mt-4 grid gap-2 text-sm">
                {['Production', 'Gallery', 'Packs', 'Billing'].map((item, index) => <div key={item} className={`rounded-md px-3 py-2 ${index === 0 ? 'bg-white font-medium shadow-[0_1px_2px_rgba(15,15,15,0.04)]' : 'text-[hsl(var(--pix-steel))]'}`}>{item}</div>)}
              </div>
            </aside>
            <div className="p-4 md:p-6">
              <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[1px] text-primary">Live workspace mockup</p>
                  <h3 className="mt-1 text-2xl font-semibold leading-[1.25]">素材生产看板</h3>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <MiniStat label="队列" value={`${activeJobs}`} />
                  <MiniStat label="点数" value={`${balance?.available_credits ?? '—'}`} />
                  <MiniStat label="素材包" value={`${batchCount}`} />
                </div>
              </div>
              <div className="grid gap-3 lg:grid-cols-3">
                <MockColumn title="Prompt" tint="bg-[hsl(var(--pix-peach))]" items={['暗月骑士', '星盐药瓶', '铜芽齿轮']} />
                <MockColumn title="Pixel Grid" tint="bg-[hsl(var(--pix-sky))]" items={['64×64', '16 colors', 'transparent PNG']} />
                <MockColumn title="Ready" tint="bg-[hsl(var(--pix-mint))]" items={['ZIP 导出', '路径复制', '失败重试']} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <PixMetric label="完成" value={completedJobs} tone="success" />
                <PixMetric label="失败" value={failedJobs} tone={failedJobs ? 'danger' : 'default'} />
                <PixMetric label="活跃" value={activeJobs} tone="info" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function HeroDecor() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
      {dotStyles.map((style) => <span key={style} className={`absolute h-4 w-4 rounded-[4px] opacity-90 shadow-[0_10px_24px_rgba(0,0,0,0.18)] ${style}`} />)}
      <svg className="absolute -left-16 top-16 h-56 w-56 text-white/12" viewBox="0 0 240 240" fill="none">
        <path d="M18 120C62 38 160 34 210 92C256 146 190 220 112 204C48 190-6 164 18 120Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M44 80C92 128 132 150 206 140M58 154C104 106 142 78 196 76M70 196C84 126 100 72 124 24" stroke="currentColor" strokeWidth="1" />
      </svg>
      <svg className="absolute -right-12 top-20 h-64 w-64 rotate-12 text-white/10" viewBox="0 0 260 260" fill="none">
        <path d="M40 42L218 70L184 222L58 194L40 42Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M62 84L206 104M66 126L198 144M70 168L190 184M102 52L88 202M154 62L138 212" stroke="currentColor" strokeWidth="1" />
      </svg>
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[hsl(var(--pix-navy-deep))]/55 to-transparent" />
    </div>
  )
}

function MiniStat({ label, value }: { label: ReactNode; value: ReactNode }) {
  return <div className="rounded-md border border-border bg-[hsl(var(--secondary))] px-3 py-2"><p className="text-[11px] text-[hsl(var(--pix-steel))]">{label}</p><p className="text-lg font-semibold leading-tight">{value}</p></div>
}

function MockColumn({ title, tint, items }: { title: string; tint: string; items: string[] }) {
  return (
    <article className="rounded-lg border border-border bg-white p-3">
      <div className={`rounded-md px-3 py-2 text-sm font-semibold ${tint}`}>{title}</div>
      <div className="mt-3 grid gap-2">
        {items.map((item) => <div key={item} className="rounded-md border border-border bg-[hsl(var(--secondary))] px-3 py-2 text-sm text-[hsl(var(--pix-slate))]">{item}</div>)}
      </div>
    </article>
  )
}
