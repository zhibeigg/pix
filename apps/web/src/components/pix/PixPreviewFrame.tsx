import type { ReactNode } from 'react'
import { ImageOff } from 'lucide-react'
import { cn } from '../../lib/utils'
import { PixMotionLoader } from './PixMotionLoader'

export function PixPreviewFrame({ url, alt, label, children, className, imageClassName, loading = false }: { url?: string | null; alt?: string; label?: ReactNode; children?: ReactNode; className?: string; imageClassName?: string; loading?: boolean }) {
  return (
    <div data-loading={loading ? 'true' : undefined} className={cn('pix-checkerboard pix-preview-frame relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]', loading && 'pix-preview-frame-loading', className)}>
      {loading ? (
        <PixMotionLoader label={label ?? '生成中'} />
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
