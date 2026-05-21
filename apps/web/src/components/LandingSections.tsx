import type { ReactNode } from 'react'

export function LandingSections({ authSlot }: { authSlot: ReactNode }) {
  const features = [
    ['素材直出', '适合 RPG 背包图标的快速生成模板。'],
    ['网格候选', '自动分析候选区域，方便二次像素化。'],
    ['批量成包', '素材包、重试、下载和路径复制一体化。'],
    ['点数系统', '支付、流水、冻结和失败退回。'],
  ]
  return (
    <section id="features" className="mx-auto grid max-w-6xl gap-8 px-4 pb-16 md:grid-cols-[minmax(0,1fr)_400px] md:px-8">
      <div className="grid gap-4 sm:grid-cols-2">
        {features.map(([title, body]) => <article key={title} className="rounded-3xl border border-border bg-card p-6 shadow-sm"><h3 className="text-xl font-black">{title}</h3><p className="mt-3 text-sm leading-6 text-muted-foreground">{body}</p></article>)}
      </div>
      <div id="auth-panel" className="scroll-mt-28">{authSlot}</div>
    </section>
  )
}
