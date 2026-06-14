import { ArrowLeft, Home, Sparkles } from 'lucide-react'
import type { User } from '../types'
import { useI18n } from '../i18n'
import { Button } from './ui/button'

const swatches = [
  'bg-[hsl(var(--pix-mint))]',
  'bg-[hsl(var(--pix-sky))]',
  'bg-[hsl(var(--pix-rose))]',
  'bg-[hsl(var(--pix-yellow))]',
  'bg-[hsl(var(--pix-lavender))]',
  'bg-[hsl(var(--pix-peach))]',
]

export function NotFoundPage({ user }: { user: User | null }) {
  const { text } = useI18n()
  return (
    <section className="relative isolate min-h-[calc(100vh-65px)] overflow-hidden bg-[hsl(var(--pix-cream)/.42)] px-4 py-14 text-foreground md:px-8 md:py-20 dark:bg-[hsl(var(--pix-navy))] dark:text-white">
      <NotFoundDecor />
      <div className="relative z-10 mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,1fr)_440px] lg:items-center">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-[11px] font-semibold uppercase leading-[1.4] tracking-[1px] text-[hsl(var(--pix-steel))] pix-shadow-hairline dark:border-white/15 dark:bg-white/10 dark:text-white/72">
            <span className="h-2 w-2 rounded-[3px] bg-primary dark:bg-[hsl(var(--pix-amber))]" />
            {text('素材坐标丢失', 'Asset coordinates lost')}
          </div>
          <h1 className="mt-6 text-[clamp(3.5rem,12vw,8.5rem)] font-semibold leading-[.88] tracking-[-0.08em] text-[hsl(var(--pix-ink))] dark:text-white">404</h1>
          <p className="mt-5 max-w-2xl text-[28px] font-semibold leading-tight tracking-[-0.04em] text-[hsl(var(--pix-ink))] md:text-[42px] dark:text-white">
            {text('这张像素素材还没有被铸造出来。', 'This pixel asset has not been forged yet.')}
          </p>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[hsl(var(--pix-slate))] dark:text-white/68">
            {text('你访问的链接不存在，或者这个任务、素材包、页面入口已经被移动。回到首页重新选择一个素材类型，或直接进入工作台继续生成。', 'The link does not exist, or this task, pack, or page entry has moved. Return home to choose an asset type, or jump back into the workspace.')}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button size="lg" asChild><a href="#/home"><Home />{text('回到首页', 'Back home')}</a></Button>
            <Button size="lg" variant="outline" className="border-[hsl(var(--pix-stone))]/45 bg-card text-[hsl(var(--pix-ink))] hover:bg-[hsl(var(--secondary))] dark:border-white/35 dark:bg-transparent dark:text-white dark:hover:bg-white/10" asChild>
              <a href={user ? '#/workspace' : '#auth-panel'}><Sparkles />{user ? text('进入工作台', 'Open workspace') : text('登录并开始', 'Sign in to start')}</a>
            </Button>
          </div>
        </div>

        <div className="motion-panel-enter overflow-hidden rounded-lg border border-border bg-card text-[hsl(var(--pix-ink))] shadow-[0_24px_54px_-18px_rgba(15,15,15,0.24)] dark:border-white/12 dark:bg-[hsl(var(--pix-paper))] dark:text-[hsl(var(--pix-paper-ink))] dark:shadow-[0_34px_90px_-26px_rgba(0,0,0,0.75)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3 dark:border-[hsl(var(--pix-paper-border))]">
            <div className="flex items-center gap-2" aria-hidden="true">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#ffbd2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-[hsl(var(--pix-steel))] dark:text-[hsl(var(--pix-paper-steel))]">missing://sprite</p>
          </div>
          <div className="grid gap-5 p-5">
            <div className="pix-checkerboard rounded-lg border border-border bg-muted/40 p-4 dark:border-[hsl(var(--pix-paper-border))]">
              <div className="mx-auto grid w-fit grid-cols-7 gap-1" aria-hidden="true">
                {Array.from({ length: 49 }).map((_, index) => {
                  const ghost = [3, 9, 10, 11, 17, 24, 31, 37, 38, 39, 45].includes(index)
                  const color = swatches[index % swatches.length]
                  return <span key={index} className={`h-7 w-7 rounded-[6px] border border-black/5 ${ghost ? color : 'bg-white/78 dark:bg-[hsl(var(--pix-paper-soft))]'} ${[16, 18, 30, 32].includes(index) ? 'opacity-25' : ''}`} />
                })}
              </div>
            </div>
            <div className="grid gap-2 rounded-lg border border-border bg-[hsl(var(--pix-paper-soft))] p-4 text-sm dark:border-[hsl(var(--pix-paper-border))]">
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold">{text('可能的下一步', 'Possible next steps')}</span>
                <ArrowLeft className="h-4 w-4 text-primary" />
              </div>
              <ul className="grid gap-2 text-[hsl(var(--pix-slate))] dark:text-[hsl(var(--pix-paper-slate))]">
                <li>{text('检查分享链接是否完整。', 'Check whether the shared link is complete.')}</li>
                <li>{text('从首页范例图鉴重新进入。', 'Re-enter from the home sample atlas.')}</li>
                <li>{text('登录后查看作品库和素材包。', 'Sign in to review your gallery and packs.')}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function NotFoundDecor() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-72 bg-[linear-gradient(180deg,hsl(var(--secondary)),transparent)] dark:hidden" />
      <div className="absolute left-1/2 top-16 h-[520px] w-[920px] -translate-x-1/2 rounded-full bg-[hsl(var(--pix-cream))] opacity-70 blur-3xl dark:hidden" />
      <div className="absolute inset-0 hidden bg-[radial-gradient(circle_at_50%_-20%,hsl(var(--pix-navy-mid)/.72),transparent_48%)] dark:block" />
      <div className="absolute left-[8%] top-[18%] h-5 w-5 rounded-[6px] border border-white/70 bg-[hsl(var(--pix-peach))] shadow-[0_10px_24px_rgba(15,15,15,0.10)] dark:border-white/12" />
      <div className="absolute right-[18%] top-[20%] h-4 w-4 rounded-[5px] border border-white/70 bg-[hsl(var(--pix-mint))] shadow-[0_10px_24px_rgba(15,15,15,0.10)] dark:border-white/12" />
      <div className="absolute bottom-[18%] left-[22%] h-6 w-6 rounded-[7px] border border-white/70 bg-[hsl(var(--pix-lavender))] shadow-[0_10px_24px_rgba(15,15,15,0.10)] dark:border-white/12" />
    </div>
  )
}
