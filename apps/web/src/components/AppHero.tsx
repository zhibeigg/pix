import type { ReactNode } from 'react'
import { useI18n } from '../i18n'
import type { CreditBalance, User } from '../types'
import { PixMetric } from './pix/PixMetric'
import { Button } from './ui/button'

type AppHeroProps = {
  user: User | null
  balance: CreditBalance | null
  activeJobs: number
  completedJobs: number
  failedJobs: number
  batchCount: number
}

export function AppHero({ user, balance, activeJobs, completedJobs, failedJobs, batchCount }: AppHeroProps) {
  const { text } = useI18n()
  const chips = [text('批量生成透明 PNG', 'Batch transparent PNGs'), text('统一尺寸和色板', 'Consistent sizes and palettes'), text('省 1–3 天打样时间', 'Save 1–3 days per prototype'), text('少花数百到数千元外包成本', 'Cut hundreds to thousands in outsourcing costs')]
  return (
    <section className="relative isolate overflow-hidden bg-background px-4 py-14 text-foreground md:px-8 md:py-20 lg:py-24 dark:bg-[hsl(var(--pix-navy))] dark:text-white lg:dark:py-[120px]">
      <HeroSurfaceDecor />
      <div className="relative z-10 mx-auto grid max-w-7xl gap-10">
        <div className="mx-auto max-w-5xl text-center">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-[hsl(var(--pix-steel))] pix-shadow-hairline dark:border-white/15 dark:bg-white/10 dark:text-white/75 dark:shadow-none">
            <span className="h-2 w-2 rounded-full bg-[hsl(var(--tone-success-line))] shadow-[0_0_8px_hsl(var(--tone-success-line))]" />
            {text('给游戏开发者的 AI 像素素材工具', 'AI pixel asset tool for game developers')}
          </div>
          <h1 className="mt-6 text-3xl font-semibold leading-[1.08] tracking-[-1px] text-[hsl(var(--pix-ink))] xs:text-[40px] xs:leading-[1.05] xs:tracking-[-1.4px] md:text-[64px] md:tracking-[-2px] xl:text-[80px] dark:text-white">
            {text('10–30 分钟，', '10–30 minutes to')}<br className="hidden md:block" />{text('做出可进游戏的像素素材', 'game-ready pixel assets')}
          </h1>
          <p className="mx-auto mt-5 max-w-3xl text-lg leading-[1.55] text-[hsl(var(--pix-slate))] dark:text-white/70">
            {text('输入一句描述，批量产出统一尺寸、透明背景、可直接导出的像素 PNG 与精灵帧。把 1–3 天的美术打样，压缩成一次生成。', 'Describe it once — batch-generate consistent, transparent, export-ready pixel PNGs and sprite frames. Compress 1–3 days of art mockups into a single run.')}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild><a href={user ? '#/workspace' : '#auth-panel'}>{text('开始生成素材', 'Start generating assets')}</a></Button>
            <Button size="lg" variant="outline" className="border-[hsl(var(--pix-stone))]/45 bg-card text-[hsl(var(--pix-ink))] hover:bg-[hsl(var(--secondary))] dark:border-white/45 dark:bg-transparent dark:text-white dark:hover:bg-white/10" asChild><a href="#examples">{text('查看范例', 'View examples')}</a></Button>
          </div>
          <div className="mt-6 flex flex-wrap justify-center gap-2 text-sm text-[hsl(var(--pix-steel))] dark:text-white/65">
            {chips.map((item) => <span key={item} className="rounded-full border border-border bg-card px-3 py-1 dark:border-white/15 dark:bg-white/7">{item}</span>)}
          </div>
        </div>

        <div className="mx-auto grid w-full max-w-6xl gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <WorkspaceMockup balance={balance} activeJobs={activeJobs} batchCount={batchCount} />
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            <PixMetric label={text('完成', 'Completed')} value={completedJobs} tone="success" className="dark:border-white/15" />
            <PixMetric label={text('失败', 'Failed')} value={failedJobs} tone={failedJobs ? 'danger' : 'default'} className="dark:border-white/15 dark:bg-white/7 dark:text-white" />
            <PixMetric label={text('活跃', 'Active')} value={activeJobs} tone="info" className="dark:border-white/15" />
          </div>
        </div>
      </div>
    </section>
  )
}

function HeroSurfaceDecor() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
      {/* Iris 辉光 */}
      <div className="absolute left-1/2 top-[-14%] h-[560px] w-[1120px] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,hsl(var(--primary)/.16),transparent)] blur-2xl dark:bg-[radial-gradient(closest-side,hsl(var(--primary)/.34),transparent)]" />
      {/* 细网格纹理（顶部渐隐遮罩） */}
      <div className="absolute inset-0 bg-[linear-gradient(hsl(var(--foreground)/.05)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--foreground)/.05)_1px,transparent_1px)] bg-[size:42px_42px] [mask-image:radial-gradient(720px_400px_at_50%_-4%,#000,transparent_72%)] dark:bg-[linear-gradient(rgba(255,255,255,.055)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.055)_1px,transparent_1px)]" />
    </div>
  )
}

function WorkspaceMockup({ balance, activeJobs, batchCount }: { balance: CreditBalance | null; activeJobs: number; batchCount: number }) {
  const { text } = useI18n()
  const navItems = [text('生产', 'Production'), text('作品库', 'Gallery'), text('素材包', 'Packs'), text('点数', 'Billing')]
  const columns = [
    { title: text('提示词队列', 'Prompt queue'), eyebrow: '01', tint: 'bg-[hsl(var(--pix-peach))]', items: [text('暗月骑士', 'Darkmoon knight'), text('星盐药瓶', 'Starsalt potion'), text('铜芽齿轮', 'Copper sprout gear')] },
    { title: text('像素网格', 'Pixel grid'), eyebrow: '02', tint: 'bg-[hsl(var(--pix-sky))]', items: ['64×64', text('16 色', '16 colors'), text('透明 PNG', 'Transparent PNG')] },
    { title: text('交付素材包', 'Delivery pack'), eyebrow: '03', tint: 'bg-[hsl(var(--pix-mint))]', items: [text('ZIP 导出', 'ZIP export'), text('保存到包', 'Save to pack'), text('失败重试', 'Retry failed')] },
  ]
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card text-left text-[hsl(var(--pix-ink))] shadow-[0_24px_48px_-8px_rgba(15,15,15,0.20)] dark:border-white/12 dark:bg-[hsl(var(--pix-paper))] dark:text-[hsl(var(--pix-paper-ink))] dark:shadow-[0_34px_90px_-26px_rgba(0,0,0,0.75)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 dark:border-[hsl(var(--pix-paper-border))]">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
          <span className="h-3 w-3 rounded-full bg-[#ffbd2e]" />
          <span className="h-3 w-3 rounded-full bg-[#28c840]" />
        </div>
        <p className="text-sm font-medium text-[hsl(var(--pix-steel))] dark:text-[hsl(var(--pix-paper-steel))]">{text('Pix 总部 / 素材流水线', 'Pix HQ / Asset pipeline')}</p>
      </div>
      <div className="grid md:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden border-r border-border bg-[hsl(var(--secondary))] p-4 md:block dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper-soft))]">
          <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-text-subtle))] dark:text-[hsl(var(--pix-paper-steel))]">{text('工作区', 'Workspace')}</p>
          <div className="mt-4 grid gap-2 text-sm">
            {navItems.map((item, index) => <div key={item} className={`rounded-md px-3 py-2 ${index === 0 ? 'bg-card font-medium pix-shadow-hairline dark:bg-[hsl(var(--pix-paper))]' : 'text-[hsl(var(--pix-steel))] dark:text-[hsl(var(--pix-paper-steel))]'}`}>{item}</div>)}
          </div>
          <div className="mt-6 rounded-lg border border-border bg-card p-3 dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper))]">
            <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-text-subtle))] dark:text-[hsl(var(--pix-paper-steel))]">{text('点数', 'Credits')}</p>
            <p className="mt-2 text-2xl font-semibold">{balance?.available_credits ?? '—'}</p>
          </div>
        </aside>
        <div className="p-4 md:p-6">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[1px] text-primary">{text('实时工作区预览', 'Live workspace mockup')}</p>
              <h3 className="mt-1 text-[28px] font-semibold leading-[1.25]">{text('素材生产看板', 'Asset production board')}</h3>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <MiniStat label={text('队列', 'Queue')} value={`${activeJobs}`} />
              <MiniStat label={text('点数', 'Credits')} value={`${balance?.available_credits ?? '—'}`} />
              <MiniStat label={text('素材包', 'Packs')} value={`${batchCount}`} />
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {columns.map((column) => <MockColumn key={column.title} {...column} />)}
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
      <div className={`rounded-md px-3 py-2 text-[hsl(var(--pix-charcoal))] ${tint}`}>
        <p className="text-[11px] font-semibold uppercase tracking-[1px] text-[hsl(var(--pix-steel))]">{eyebrow}</p>
        <p className="mt-1 text-sm font-semibold">{title}</p>
      </div>
      <div className="mt-3 grid gap-2">
        {items.map((item) => <div key={item} className="rounded-md border border-border bg-[hsl(var(--secondary))] px-3 py-2 text-sm text-[hsl(var(--pix-slate))] dark:border-[hsl(var(--pix-paper-border))] dark:bg-[hsl(var(--pix-paper-soft))] dark:text-[hsl(var(--pix-paper-slate))]">{item}</div>)}
      </div>
    </article>
  )
}
