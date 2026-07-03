import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ZoomIn, ZoomOut, RotateCcw, X } from 'lucide-react'
import { cn } from '../lib/utils'
import { useI18n } from '../i18n'

type Props = {
  src: string
  alt?: string
  open: boolean
  onClose: () => void
  /** 图片渲染模式：像素图用 pixelated 保锐利，原始图用 auto 平滑。默认 pixelated。 */
  rendering?: 'pixelated' | 'auto'
}

const MIN_SCALE = 1
const MAX_SCALE = 16
const ZOOM_STEP = 1.3

type Point = { x: number; y: number }

/**
 * 全屏图片查看器：支持滚轮缩放、拖拽平移、双击缩放、双指捏合缩放、ESC 关闭。
 * 通过 portal 挂到 body，避免受父容器 overflow/transform 影响。
 */
export function ImageLightbox({ src, alt, open, onClose, rendering = 'pixelated' }: Props) {
  const { t } = useI18n()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 })

  const dragState = useRef<{ active: boolean; startX: number; startY: number; originX: number; originY: number }>({
    active: false,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
  })
  const pinchState = useRef<{ active: boolean; startDist: number; startScale: number }>({
    active: false,
    startDist: 0,
    startScale: 1,
  })
  const pointers = useRef<Map<number, Point>>(new Map())

  const reset = useCallback(() => {
    setScale(1)
    setOffset({ x: 0, y: 0 })
  }, [])

  // 打开时重置视图，并锁定 body 滚动
  useEffect(() => {
    if (!open) return
    reset()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [open, src, reset])

  // ESC 关闭
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, onClose])

  const clampScale = (value: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))

  // 以某个屏幕锚点为中心缩放，保持锚点在图片上的相对位置不变
  const zoomAt = useCallback((nextScaleRaw: number, anchor: Point) => {
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    const cx = rect.width / 2
    const cy = rect.height / 2
    setScale((prevScale) => {
      const nextScale = clampScale(nextScaleRaw)
      if (nextScale === prevScale) return prevScale
      setOffset((prevOffset) => {
        if (nextScale <= MIN_SCALE) return { x: 0, y: 0 }
        // 锚点相对容器中心的坐标
        const ax = anchor.x - rect.left - cx
        const ay = anchor.y - rect.top - cy
        const ratio = nextScale / prevScale
        return {
          x: ax - (ax - prevOffset.x) * ratio,
          y: ay - (ay - prevOffset.y) * ratio,
        }
      })
      return nextScale
    })
  }, [])

  const handleWheel = useCallback((event: React.WheelEvent) => {
    event.preventDefault()
    const factor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
    setScale((prev) => {
      const next = clampScale(prev * factor)
      if (next === prev) return prev
      const container = containerRef.current
      if (container) {
        const rect = container.getBoundingClientRect()
        const cx = rect.width / 2
        const cy = rect.height / 2
        const ax = event.clientX - rect.left - cx
        const ay = event.clientY - rect.top - cy
        const ratio = next / prev
        setOffset((prevOffset) => (next <= MIN_SCALE ? { x: 0, y: 0 } : {
          x: ax - (ax - prevOffset.x) * ratio,
          y: ay - (ay - prevOffset.y) * ratio,
        }))
      }
      return next
    })
  }, [])

  const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y)
  const midpoint = (a: Point, b: Point): Point => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 })

  const handlePointerDown = useCallback((event: React.PointerEvent) => {
    ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })

    if (pointers.current.size === 2) {
      const [p1, p2] = Array.from(pointers.current.values())
      pinchState.current = { active: true, startDist: distance(p1, p2), startScale: scale }
      dragState.current.active = false
      return
    }

    dragState.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      originX: offset.x,
      originY: offset.y,
    }
  }, [offset.x, offset.y, scale])

  const handlePointerMove = useCallback((event: React.PointerEvent) => {
    if (pointers.current.has(event.pointerId)) {
      pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    }

    if (pinchState.current.active && pointers.current.size >= 2) {
      const [p1, p2] = Array.from(pointers.current.values())
      const dist = distance(p1, p2)
      if (pinchState.current.startDist > 0) {
        const nextScale = pinchState.current.startScale * (dist / pinchState.current.startDist)
        zoomAt(nextScale, midpoint(p1, p2))
      }
      return
    }

    if (!dragState.current.active || scale <= MIN_SCALE) return
    const dx = event.clientX - dragState.current.startX
    const dy = event.clientY - dragState.current.startY
    setOffset({ x: dragState.current.originX + dx, y: dragState.current.originY + dy })
  }, [scale, zoomAt])

  const endPointer = useCallback((event: React.PointerEvent) => {
    pointers.current.delete(event.pointerId)
    if (pointers.current.size < 2) {
      pinchState.current.active = false
    }
    if (pointers.current.size === 0) {
      dragState.current.active = false
    }
  }, [])

  const handleDoubleClick = useCallback((event: React.MouseEvent) => {
    const anchor = { x: event.clientX, y: event.clientY }
    if (scale > MIN_SCALE) {
      reset()
    } else {
      zoomAt(2.5, anchor)
    }
  }, [scale, reset, zoomAt])

  if (!open) return null

  const canZoomOut = scale > MIN_SCALE
  const canZoomIn = scale < MAX_SCALE

  const centerZoom = (factor: number) => {
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    zoomAt(scale * factor, { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
  }

  const content = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={alt || t('lightbox.title')}
      onClick={onClose}
    >
      {/* 工具栏 */}
      <div className="absolute right-3 top-3 z-10 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
        <LightboxButton title={t('lightbox.zoomOut')} disabled={!canZoomOut} onClick={() => centerZoom(1 / ZOOM_STEP)}>
          <ZoomOut className="h-5 w-5" />
        </LightboxButton>
        <span className="min-w-14 text-center text-sm font-semibold tabular-nums text-white/90">{Math.round(scale * 100)}%</span>
        <LightboxButton title={t('lightbox.zoomIn')} disabled={!canZoomIn} onClick={() => centerZoom(ZOOM_STEP)}>
          <ZoomIn className="h-5 w-5" />
        </LightboxButton>
        <LightboxButton title={t('lightbox.reset')} disabled={!canZoomOut} onClick={reset}>
          <RotateCcw className="h-5 w-5" />
        </LightboxButton>
        <LightboxButton title={t('lightbox.close')} onClick={onClose}>
          <X className="h-5 w-5" />
        </LightboxButton>
      </div>

      {/* 画布 */}
      <div
        ref={containerRef}
        className={cn('relative flex h-full w-full touch-none select-none items-center justify-center overflow-hidden', canZoomOut ? 'cursor-grab active:cursor-grabbing' : 'cursor-zoom-in')}
        onClick={(e) => e.stopPropagation()}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endPointer}
        onPointerCancel={endPointer}
        onDoubleClick={handleDoubleClick}
      >
        <img
          src={src}
          alt={alt || t('lightbox.title')}
          draggable={false}
          className={cn('max-h-[92vh] max-w-[92vw] object-contain', rendering === 'pixelated' ? '[image-rendering:pixelated]' : '[image-rendering:auto]')}
          style={{
            transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${scale})`,
            transition: dragState.current.active || pinchState.current.active ? 'none' : 'transform 120ms ease-out',
            willChange: 'transform',
          }}
        />
      </div>

      {/* 底部提示 */}
      <p className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 text-xs text-white/60">{t('lightbox.hint')}</p>
    </div>
  )

  return createPortal(content, document.body)
}

function LightboxButton({ title, disabled, onClick, children }: { title: string; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className="grid h-9 w-9 place-items-center rounded-md bg-white/10 text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  )
}
