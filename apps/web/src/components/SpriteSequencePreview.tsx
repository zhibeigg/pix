import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { SpriteFrameOutput } from '../types'
import { cn } from '../lib/utils'
import { PixPreviewFrame } from './pix/PixPreviewFrame'

type Props = {
  sheetUrl?: string | null
  frames?: SpriteFrameOutput[]
  fps?: number
  fallbackUrl?: string | null
  loading?: boolean
  label?: ReactNode
  className?: string
  imageClassName?: string
  children?: ReactNode
}

export function SpriteSequencePreview({ sheetUrl, frames = [], fps = 8, fallbackUrl, loading = false, label, className, imageClassName, children }: Props) {
  const playableFrames = useMemo(() => frames.filter((frame) => frame.sheet_rect && frame.sheet_rect.w > 0 && frame.sheet_rect.h > 0).sort((a, b) => Number(a.index) - Number(b.index)), [frames])
  const [frameIndex, setFrameIndex] = useState(0)
  const activeFrame = playableFrames.length > 0 ? playableFrames[frameIndex % playableFrames.length] : null
  const rect = activeFrame?.sheet_rect ?? null
  const sheetSize = useMemo(() => {
    if (!rect || playableFrames.length === 0) return null
    const width = Math.max(...playableFrames.map((frame) => (frame.sheet_rect?.x ?? 0) + (frame.sheet_rect?.w ?? 0)))
    const height = Math.max(...playableFrames.map((frame) => (frame.sheet_rect?.y ?? 0) + (frame.sheet_rect?.h ?? 0)))
    return width > 0 && height > 0 ? { width, height } : null
  }, [playableFrames, rect])

  useEffect(() => {
    if (!sheetUrl || playableFrames.length <= 1 || loading) return
    const interval = window.setInterval(() => {
      setFrameIndex((current) => (current + 1) % playableFrames.length)
    }, Math.max(20, Math.round(1000 / Math.max(1, fps || 8))))
    return () => window.clearInterval(interval)
  }, [sheetUrl, playableFrames.length, fps, loading])

  useEffect(() => {
    setFrameIndex(0)
  }, [sheetUrl, playableFrames.length])

  if (!sheetUrl || !rect || !sheetSize) {
    return <PixPreviewFrame url={fallbackUrl} loading={loading} label={label} className={className} imageClassName={imageClassName}>{children}</PixPreviewFrame>
  }

  const backgroundSize = `${(sheetSize.width / rect.w) * 100}% ${(sheetSize.height / rect.h) * 100}%`
  const backgroundPositionX = sheetSize.width === rect.w ? '0%' : `${(rect.x / Math.max(1, sheetSize.width - rect.w)) * 100}%`
  const backgroundPositionY = sheetSize.height === rect.h ? '0%' : `${(rect.y / Math.max(1, sheetSize.height - rect.h)) * 100}%`

  return (
    <div data-loading={loading ? 'true' : undefined} className={cn('pix-checkerboard pix-preview-frame relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]', loading && 'pix-preview-frame-loading', className)}>
      <div
        role="img"
        aria-label={typeof label === 'string' ? label : '序列帧预览'}
        className={cn('h-full max-h-[420px] w-full bg-no-repeat p-3 [image-rendering:pixelated]', imageClassName)}
        style={{
          aspectRatio: `${rect.w} / ${rect.h}`,
          backgroundImage: `url(${sheetUrl})`,
          backgroundSize,
          backgroundPosition: `${backgroundPositionX} ${backgroundPositionY}`,
        }}
      />
      {children}
    </div>
  )
}
