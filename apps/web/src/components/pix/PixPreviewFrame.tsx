import type { ReactNode } from 'react'
import { ImageOff } from 'lucide-react'
import { cn } from '../../lib/utils'

export function PixPreviewFrame({ url, alt, label, children, className, imageClassName, loading = false }: { url?: string | null; alt?: string; label?: ReactNode; children?: ReactNode; className?: string; imageClassName?: string; loading?: boolean }) {
  return (
    <div className={cn('pix-checkerboard relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]', className)}>
      {loading ? (
        <div className="motion-panel-enter flex flex-col items-center gap-3 p-6 text-center text-muted-foreground">
          <div className="pix-loader" aria-hidden="true">
            <span className="pix-loader-ring" />
            <span className="pix-loader-core" />
            <span className="pix-loader-spark pix-loader-spark-a" />
            <span className="pix-loader-spark pix-loader-spark-b" />
          </div>
          <p className="pix-loader-label text-sm font-bold">{label ?? '生成中…'}</p>
        </div>
      ) : url ? (
        <img src={url} alt={alt || '预览'} loading="lazy" decoding="async" className={cn('h-full max-h-[420px] w-full object-contain p-3 [image-rendering:pixelated]', imageClassName)} />
      ) : (
        <div className="motion-panel-enter flex flex-col items-center gap-2 p-6 text-center text-muted-foreground">
          <div className="motion-float-soft grid h-14 w-14 place-items-center rounded-lg border border-dashed border-border bg-card/80"><ImageOff className="h-6 w-6" /></div>
          <p className="text-sm font-bold">{label ?? '暂无预览'}</p>
        </div>
      )}
      {children}
    </div>
  )
}
