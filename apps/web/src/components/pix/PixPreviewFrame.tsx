import type { ReactNode } from 'react'
import { ImageOff, LoaderCircle } from 'lucide-react'
import { cn } from '../../lib/utils'

export function PixPreviewFrame({ url, alt, label, children, className, imageClassName, loading = false }: { url?: string | null; alt?: string; label?: ReactNode; children?: ReactNode; className?: string; imageClassName?: string; loading?: boolean }) {
  return (
    <div className={cn('pix-checkerboard relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]', className)}>
      {loading ? (
        <div className="flex flex-col items-center gap-3 p-6 text-center text-muted-foreground">
          <div className="relative grid h-16 w-16 place-items-center rounded-full border border-primary/25 bg-card/85 shadow-[0_0_0_8px_hsl(var(--primary)/.06)] dark:bg-black/20">
            <div className="absolute inset-1 rounded-full border border-dashed border-primary/30 animate-spin" />
            <LoaderCircle className="h-7 w-7 animate-spin text-primary" />
          </div>
          <p className="text-sm font-bold">{label ?? '生成中…'}</p>
        </div>
      ) : url ? (
        <img src={url} alt={alt || '预览'} loading="lazy" decoding="async" className={cn('h-full max-h-[420px] w-full object-contain p-3 [image-rendering:pixelated]', imageClassName)} />
      ) : (
        <div className="flex flex-col items-center gap-2 p-6 text-center text-muted-foreground">
          <div className="grid h-14 w-14 place-items-center rounded-lg border border-dashed border-border bg-card/80"><ImageOff className="h-6 w-6" /></div>
          <p className="text-sm font-bold">{label ?? '暂无预览'}</p>
        </div>
      )}
      {children}
    </div>
  )
}
