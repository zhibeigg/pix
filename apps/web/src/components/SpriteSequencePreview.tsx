import { useEffect, useMemo, useRef, useState, type ReactNode, type SyntheticEvent } from 'react'
import type { SpriteFrameOutput } from '../types'
import { cn } from '../lib/utils'
import { PixPreviewFrame } from './pix/PixPreviewFrame'
import { ZoomButton } from './pix/ZoomButton'
import { ImageLightbox } from './ImageLightbox'

type SpriteSequencePreviewProps = {
  sheetUrl?: string | null
  frames?: SpriteFrameOutput[] | null
  frameCount?: number | null
  fps?: number | null
  fallbackUrl?: string | null
  alt?: string
  label?: ReactNode
  children?: ReactNode
  className?: string
  imageClassName?: string
  loading?: boolean
  trim?: boolean
  zoomable?: boolean
  zoomSrc?: string | null
  zoomRendering?: 'pixelated' | 'auto'
}

type SpritePlaybackState = {
  frameCount: number
  isVisible: boolean
  isDocumentVisible: boolean
  prefersReducedMotion: boolean
}

const MAX_INFERRED_SPRITE_FRAMES = 256

export function inferHorizontalSpriteFrames(
  frameCount: number | null | undefined,
  sheetWidth: number,
  sheetHeight: number,
): SpriteFrameOutput[] {
  const count = Math.floor(Number(frameCount))
  const width = Math.floor(Number(sheetWidth))
  const height = Math.floor(Number(sheetHeight))
  if (
    !Number.isFinite(count)
    || count <= 1
    || count > MAX_INFERRED_SPRITE_FRAMES
    || !Number.isFinite(width)
    || width <= 0
    || !Number.isFinite(height)
    || height <= 0
    || width % count !== 0
  ) return []

  const frameWidth = width / count
  return Array.from({ length: count }, (_, frameIndex) => ({
    index: frameIndex + 1,
    row: 0,
    col: frameIndex,
    path: '',
    url: null,
    sheet_rect: {
      x: frameIndex * frameWidth,
      y: 0,
      w: frameWidth,
      h: height,
    },
  }))
}

export function shouldAnimateSpriteSequence({ frameCount, isVisible, isDocumentVisible, prefersReducedMotion }: SpritePlaybackState) {
  return frameCount > 1 && isVisible && isDocumentVisible && !prefersReducedMotion
}

export function SpriteSequencePreview({ sheetUrl, frames, frameCount, fps, fallbackUrl, alt, label, children, className, imageClassName, loading = false, trim = false, zoomable = true, zoomSrc, zoomRendering = 'pixelated' }: SpriteSequencePreviewProps) {
  const suppliedFrames = useMemo(
    () => (frames || [])
      .filter((frame) => frame.sheet_rect && frame.sheet_rect.w > 0 && frame.sheet_rect.h > 0)
      .sort((a, b) => Number(a.index || 0) - Number(b.index || 0)),
    [frames],
  )
  const normalizedFrameCount = useMemo(() => {
    const count = Math.floor(Number(frameCount))
    return Number.isFinite(count) && count > 1 && count <= MAX_INFERRED_SPRITE_FRAMES ? count : 0
  }, [frameCount])
  const inferenceKey = `${sheetUrl || ''}:${normalizedFrameCount}`
  const [inferredState, setInferredState] = useState<{ key: string; frames: SpriteFrameOutput[] }>({ key: '', frames: [] })
  const inferredFrames = inferredState.key === inferenceKey ? inferredState.frames : []
  const playableFrames = suppliedFrames.length > 0 ? suppliedFrames : inferredFrames
  const canInferFrames = Boolean(sheetUrl && suppliedFrames.length === 0 && normalizedFrameCount > 1)
  const [frameIndex, setFrameIndex] = useState(0)
  const [isVisible, setIsVisible] = useState(false)
  const [isDocumentVisible, setIsDocumentVisible] = useState(() => typeof document === 'undefined' || document.visibilityState !== 'hidden')
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [containerSize, setContainerSize] = useState({ width: 1, height: 1 })

  useEffect(() => {
    setFrameIndex(0)
  }, [sheetUrl, playableFrames.length])

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    if (typeof IntersectionObserver === 'undefined') {
      setIsVisible(true)
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting && entry.intersectionRatio > 0),
      { threshold: 0.1 },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [sheetUrl, playableFrames.length, canInferFrames])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const syncVisibility = () => setIsDocumentVisible(document.visibilityState !== 'hidden')
    syncVisibility()
    document.addEventListener('visibilitychange', syncVisibility)
    return () => document.removeEventListener('visibilitychange', syncVisibility)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setPrefersReducedMotion(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const update = () => {
      setContainerSize({ width: Math.max(1, element.clientWidth), height: Math.max(1, element.clientHeight) })
    }
    update()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [sheetUrl, playableFrames.length, canInferFrames])

  useEffect(() => {
    if (prefersReducedMotion) setFrameIndex(0)
  }, [prefersReducedMotion])

  const delay = Math.max(16, Math.round(1000 / Math.max(1, Number(fps) || 8)))
  const shouldAnimate = Boolean(sheetUrl) && !loading && shouldAnimateSpriteSequence({
    frameCount: playableFrames.length,
    isVisible,
    isDocumentVisible,
    prefersReducedMotion,
  })

  useEffect(() => {
    if (!shouldAnimate) return
    const timer = window.setInterval(() => {
      setFrameIndex((current) => (current + 1) % playableFrames.length)
    }, delay)
    return () => window.clearInterval(timer)
  }, [delay, playableFrames.length, shouldAnimate])

  const activeFrame = playableFrames[frameIndex] || playableFrames[0]
  const rect = activeFrame?.sheet_rect
  const sheetSize = useMemo(() => {
    let width = 0
    let height = 0
    for (const frame of playableFrames) {
      const frameRect = frame.sheet_rect
      if (!frameRect) continue
      width = Math.max(width, frameRect.x + frameRect.w)
      height = Math.max(height, frameRect.y + frameRect.h)
    }
    return width > 0 && height > 0 ? { width, height } : null
  }, [playableFrames])

  const handleSheetLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    if (!canInferFrames) return
    const image = event.currentTarget
    setInferredState({
      key: inferenceKey,
      frames: inferHorizontalSpriteFrames(normalizedFrameCount, image.naturalWidth, image.naturalHeight),
    })
  }

  if (loading) {
    return <PixPreviewFrame url={fallbackUrl || sheetUrl} alt={alt} label={label} className={className} imageClassName={imageClassName} loading trim={trim} zoomable={zoomable} zoomSrc={zoomSrc} zoomRendering={zoomRendering}>{children}</PixPreviewFrame>
  }
  if (!sheetUrl) {
    return <PixPreviewFrame url={fallbackUrl} alt={alt} label={label} className={className} imageClassName={imageClassName} trim={trim} zoomable={zoomable} zoomSrc={zoomSrc} zoomRendering={zoomRendering}>{children}</PixPreviewFrame>
  }

  const frameStyle = rect && sheetSize
    ? fitSpriteFrame(Math.max(1, containerSize.width - 24), Math.max(1, containerSize.height - 24), rect)
    : null
  if (!frameStyle && !canInferFrames) {
    return <PixPreviewFrame url={fallbackUrl || sheetUrl} alt={alt} label={label} className={className} imageClassName={imageClassName} trim={trim} zoomable={zoomable} zoomSrc={zoomSrc} zoomRendering={zoomRendering}>{children}</PixPreviewFrame>
  }

  const resolvedZoomSrc = zoomSrc || fallbackUrl || sheetUrl
  const canZoom = zoomable && !!resolvedZoomSrc
  const sequenceState = frameStyle
    ? prefersReducedMotion
      ? 'reduced-motion'
      : shouldAnimate
        ? 'playing'
        : 'paused'
    : 'detecting'

  return (
    <div
      ref={containerRef}
      data-sequence-state={sequenceState}
      className={cn(
        'pix-checkerboard pix-preview-frame group relative grid min-h-40 place-items-center overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-muted p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]',
        className,
      )}
    >
      {frameStyle ? (
        <div
          role="img"
          aria-label={alt || '序列帧预览'}
          className="bg-no-repeat [image-rendering:pixelated]"
          style={{
            width: frameStyle.width,
            height: frameStyle.height,
            backgroundImage: `url("${sheetUrl.replace(/"/g, '\\"')}")`,
            backgroundSize: `${sheetSize!.width * frameStyle.scaleX}px ${sheetSize!.height * frameStyle.scaleY}px`,
            backgroundPosition: `${-rect!.x * frameStyle.scaleX}px ${-rect!.y * frameStyle.scaleY}px`,
          }}
          data-frame={frameIndex}
        />
      ) : (
        <img
          src={sheetUrl}
          alt={alt || '序列帧预览'}
          loading="lazy"
          decoding="async"
          onLoad={handleSheetLoad}
          className={cn('h-full max-h-[420px] w-full object-contain [image-rendering:pixelated]', imageClassName)}
        />
      )}
      {canZoom && <ZoomButton onClick={() => setLightboxOpen(true)} />}
      {children}
      {canZoom && resolvedZoomSrc && (
        <ImageLightbox
          src={resolvedZoomSrc}
          alt={typeof label === 'string' ? label : alt}
          open={lightboxOpen}
          onClose={() => setLightboxOpen(false)}
          rendering={zoomRendering}
        />
      )}
    </div>
  )
}

export function fitSpriteFrame(containerWidth: number, containerHeight: number, rect: { w: number; h: number }) {
  const scale = Math.min(containerWidth / Math.max(1, rect.w), containerHeight / Math.max(1, rect.h))
  const width = Math.max(1, Math.round(rect.w * scale))
  const height = Math.max(1, Math.round(rect.h * scale))
  return {
    width,
    height,
    scaleX: width / Math.max(1, rect.w),
    scaleY: height / Math.max(1, rect.h),
  }
}
