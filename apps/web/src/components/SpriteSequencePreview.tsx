import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  trim?: boolean
  children?: ReactNode
}

export function SpriteSequencePreview({ sheetUrl, frames = [], fps = 8, fallbackUrl, loading = false, label, className, imageClassName, trim = false, children }: Props) {
  const playableFrames = useMemo(() => frames.filter((frame) => frame.sheet_rect && frame.sheet_rect.w > 0 && frame.sheet_rect.h > 0).sort((a, b) => Number(a.index) - Number(b.index)), [frames])
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })
  const [frameIndex, setFrameIndex] = useState(0)
  const [isVisible, setIsVisible] = useState(true)
  const activeFrame = playableFrames.length > 0 ? playableFrames[frameIndex % playableFrames.length] : null
  const rect = activeFrame?.sheet_rect ?? null
  const sheetSize = useMemo(() => {
    if (!rect || playableFrames.length === 0) return null
    const width = Math.max(...playableFrames.map((frame) => (frame.sheet_rect?.x ?? 0) + (frame.sheet_rect?.w ?? 0)))
    const height = Math.max(...playableFrames.map((frame) => (frame.sheet_rect?.y ?? 0) + (frame.sheet_rect?.h ?? 0)))
    return width > 0 && height > 0 ? { width, height } : null
  }, [playableFrames, rect])

  useEffect(() => {
    const node = containerRef.current
    if (!node) return
    const update = () => setContainerSize({ width: node.clientWidth, height: node.clientHeight })
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const node = containerRef.current
    if (!node) return
    const observer = new IntersectionObserver(([entry]) => setIsVisible(entry.isIntersecting), { rootMargin: '150px' })
    observer.observe(node)
    return () => observer.disconnect()
  }, [sheetUrl, playableFrames.length])

  useEffect(() => {
    if (!sheetUrl || playableFrames.length <= 1 || loading || !isVisible) return
    const interval = window.setInterval(() => {
      setFrameIndex((current) => (current + 1) % playableFrames.length)
    }, Math.max(20, Math.round(1000 / Math.max(1, fps || 8))))
    return () => window.clearInterval(interval)
  }, [sheetUrl, playableFrames.length, fps, loading, isVisible])

  useEffect(() => {
    setFrameIndex(0)
  }, [sheetUrl, playableFrames.length])

  if (!sheetUrl || !rect || !sheetSize) {
    return <PixPreviewFrame url={fallbackUrl} loading={loading} label={label} className={className} imageClassName={imageClassName} trim={trim}>{children}</PixPreviewFrame>
  }

  const fit = fitRect(rect.w, rect.h, Math.max(1, containerSize.width - 24), Math.max(1, containerSize.height - 24))
  const scaleX = fit.width / rect.w
  const scaleY = fit.height / rect.h
  const backgroundSize = `${sheetSize.width * scaleX}px ${sheetSize.height * scaleY}px`
  const backgroundPosition = `${-rect.x * scaleX}px ${-rect.y * scaleY}px`

  return (
    <div ref={containerRef} data-loading={loading ? 'true' : undefined} className={cn('pix-checkerboard pix-preview-frame relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]', loading && 'pix-preview-frame-loading', className)}>
      <div
        role="img"
        aria-label={typeof label === 'string' ? label : '序列帧预览'}
        className="bg-no-repeat [image-rendering:pixelated]"
        style={{
          width: fit.width,
          height: fit.height,
          backgroundImage: `url(${sheetUrl})`,
          backgroundSize,
          backgroundPosition,
        }}
      />
      {children}
    </div>
  )
}

function fitRect(width: number, height: number, maxWidth: number, maxHeight: number) {
  const scale = Math.max(0.01, Math.min(maxWidth / width, maxHeight / height))
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}
