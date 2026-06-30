import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ImageOff } from 'lucide-react'
import { cn } from '../../lib/utils'
import { PixMotionLoader } from './PixMotionLoader'

export function PixPreviewFrame({ url, file, alt, label, children, className, imageClassName, loading = false, trim = false }: { url?: string | null; file?: File | null; alt?: string; label?: ReactNode; children?: ReactNode; className?: string; imageClassName?: string; loading?: boolean; trim?: boolean }) {
  const imgClass = cn('h-full max-h-[420px] w-full object-contain p-3 [image-rendering:pixelated]', imageClassName)
  return (
    <div data-loading={loading ? 'true' : undefined} className={cn('pix-checkerboard pix-preview-frame relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]', loading && 'pix-preview-frame-loading', className)}>
      {loading ? (
        <PixMotionLoader label={label ?? '生成中'} />
      ) : file ? (
        <LocalImageCanvas file={file} label={label} className={imgClass} />
      ) : url ? (
        trim
          ? <TrimmedImage url={url} alt={alt} className={imgClass} />
          : <img src={url} alt={alt || '预览'} loading="lazy" decoding="async" className={imgClass} />
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

function LocalImageCanvas({ file, label, className }: { file: File; label?: ReactNode; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setFailed(false)
    async function draw() {
      try {
        const canvas = canvasRef.current
        if (!canvas) return
        const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
        if (cancelled) { bitmap.close(); return }
        canvas.width = bitmap.width
        canvas.height = bitmap.height
        const ctx = canvas.getContext('2d')
        if (!ctx) { bitmap.close(); return }
        ctx.clearRect(0, 0, bitmap.width, bitmap.height)
        ctx.imageSmoothingEnabled = true
        ctx.drawImage(bitmap, 0, 0)
        bitmap.close()
      } catch {
        if (!cancelled) setFailed(true)
      }
    }
    void draw()
    return () => { cancelled = true }
  }, [file])

  if (failed) {
    return <div className="motion-panel-enter flex flex-col items-center gap-2 p-6 text-center text-muted-foreground"><ImageOff className="h-6 w-6" /><p className="text-sm font-bold">{label ?? '预览失败'}</p></div>
  }
  return <canvas ref={canvasRef} aria-label={typeof label === 'string' ? label : '预览'} className={className} />
}

/**
 * 透明边裁剪（仅用于缩略图展示，不改原文件）。
 * 很多生成 PNG 主体在画布里留白不一致（同一作品 96² 主体铺满、256² 只占 ~53%），
 * object-contain 会把整张画布含透明边一起缩放进框，导致同类作品忽大忽小。
 * 这里按 alpha 包围盒裁掉透明边后再展示，主体即可在各卡片中保持一致大小。
 * 跨域取不到像素 / 全透明 / 无明显留白时回退原图。
 */
function TrimmedImage({ url, alt, className }: { url: string; alt?: string; className?: string }) {
  const [src, setSrc] = useState(url)
  useEffect(() => {
    let cancelled = false
    setSrc(url)
    // 动图（GIF）不裁剪：画到 canvas 只会取到首帧，再转 data URL 会把动画变成静态图。
    if (/\.gif(\?|&|%|$)/i.test(url)) return
    const probe = new Image()
    probe.decoding = 'async'
    probe.onload = () => {
      if (cancelled) return
      const w = probe.naturalWidth
      const h = probe.naturalHeight
      if (!w || !h) return
      try {
        const canvas = document.createElement('canvas')
        canvas.width = w
        canvas.height = h
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        if (!ctx) return
        ctx.drawImage(probe, 0, 0)
        const data = ctx.getImageData(0, 0, w, h).data
        let minX = w
        let minY = h
        let maxX = -1
        let maxY = -1
        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            if (data[(y * w + x) * 4 + 3] > 8) {
              if (x < minX) minX = x
              if (x > maxX) maxX = x
              if (y < minY) minY = y
              if (y > maxY) maxY = y
            }
          }
        }
        if (maxX < minX || maxY < minY) return
        const bw = maxX - minX + 1
        const bh = maxY - minY + 1
        if (bw >= w * 0.96 && bh >= h * 0.96) return
        const crop = document.createElement('canvas')
        crop.width = bw
        crop.height = bh
        const cropCtx = crop.getContext('2d')
        if (!cropCtx) return
        cropCtx.imageSmoothingEnabled = false
        cropCtx.drawImage(probe, minX, minY, bw, bh, 0, 0, bw, bh)
        if (!cancelled) setSrc(crop.toDataURL('image/png'))
      } catch {
        /* 跨域污染等无法读像素时保留原图 */
      }
    }
    probe.src = url
    return () => { cancelled = true }
  }, [url])
  return <img src={src} alt={alt || '预览'} loading="lazy" decoding="async" className={className} />
}
