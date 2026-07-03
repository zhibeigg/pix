import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { Copy, Crosshair, Pause, Play, RotateCcw, Save, SkipBack, SkipForward, ZoomIn, ZoomOut } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { GenerationJob, JobOutput, SequenceAlignmentRequest, SpriteFrameOutput } from '../types'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Input } from './ui/input'
import { Slider } from './ui/slider'
import { Alert } from './ui/alert'

const DEFAULT_EDITOR_ZOOM = 4
const MIN_EDITOR_ZOOM = 1
const MAX_EDITOR_ZOOM = 12
const FRAME_SCALE_DEFAULT = 1
const FRAME_SCALE_MIN = 0.25
const FRAME_SCALE_MAX = 4
const FRAME_SCALE_STEP = 0.05
const COLOR_COUNT_MIN = 2
const COLOR_COUNT_MAX = 256
const COLOR_COUNT_DEFAULT = 16

type Offset = { x: number; y: number }
type VisibleBounds = { left: number; top: number; right: number; bottom: number }
type SnapEdge = 'left' | 'right' | 'top' | 'bottom'
type ImageMap = Map<number, HTMLImageElement>
type DragState = { startX: number; startY: number; startOffset: Offset }
type RgbColor = { r: number; g: number; b: number }
type WeightedColor = RgbColor & { count: number }
type PaletteBucket = {
  colors: WeightedColor[]
  weight: number
  rMin: number
  rMax: number
  gMin: number
  gMax: number
  bMin: number
  bMax: number
}

type Props = {
  job: GenerationJob
  output: JobOutput
  saving?: boolean
  onSave: (payload: SequenceAlignmentRequest) => Promise<void>
}

export function SpriteSequenceAlignmentEditor({ job, output, saving = false, onSave }: Props) {
  const { text } = useI18n()
  const frames = useMemo(() => [...(output.sprite_frames ?? [])].filter((frame) => frame.url && frame.sheet_rect).sort((a, b) => Number(a.index) - Number(b.index)), [output.sprite_frames])
  const frameSize = useMemo(() => {
    const rect = frames[0]?.sheet_rect
    return rect ? { width: Math.max(1, rect.w), height: Math.max(1, rect.h) } : { width: 64, height: 64 }
  }, [frames])
  const initialColorCount = useMemo(() => colorCountFromJob(job), [job])
  const frameIndexes = useMemo(() => frames.map((frame) => Number(frame.index)), [frames])
  const [selectedIndex, setSelectedIndex] = useState(() => frameIndexes[0] ?? 1)
  const [offsets, setOffsets] = useState<Record<number, Offset>>({})
  const [scales, setScales] = useState<Record<number, number>>({})
  const [images, setImages] = useState<ImageMap>(() => new Map())
  const [loadError, setLoadError] = useState('')
  const [onionOpacity, setOnionOpacity] = useState(35)
  const [playing, setPlaying] = useState(true)
  const [loopCheck, setLoopCheck] = useState(false)
  const [fps, setFps] = useState(spriteFpsFromJob(job))
  const [colorCount, setColorCount] = useState(initialColorCount)
  const [previewIndex, setPreviewIndex] = useState(0)
  const [editorZoom, setEditorZoom] = useState(DEFAULT_EDITOR_ZOOM)
  const editorCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const editorViewportRef = useRef<HTMLDivElement | null>(null)
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const dragRef = useRef<DragState | null>(null)

  const selectedFrame = frames.find((frame) => Number(frame.index) === selectedIndex) ?? frames[0]
  const selectedPosition = Math.max(1, frameIndexes.indexOf(selectedIndex) + 1)
  const selectedOffset = offsetFor(offsets, selectedIndex)

  const selectedScale = scaleFor(scales, selectedIndex)
  const selectedImage = images.get(selectedIndex)
  const selectedSourceSize = imageSourceSize(selectedImage, frameSize)
  const selectedVisibleBounds = useMemo(() => selectedFrame ? visibleBoundsForFrame(selectedFrame, selectedImage) : null, [selectedFrame, selectedImage])
  const projectedVisibleBounds = selectedVisibleBounds
    ? projectBoundsToCanvas(selectedVisibleBounds, selectedSourceSize, selectedScale, selectedOffset)
    : null
  const ghostIndex = useMemo(() => ghostFrameIndex(frameIndexes, selectedIndex), [frameIndexes, selectedIndex])
  const playableIndexes = useMemo(() => loopCheck && frameIndexes.length > 1 ? [frameIndexes[frameIndexes.length - 1], frameIndexes[0]] : frameIndexes, [frameIndexes, loopCheck])
  const sharedPalette = useMemo(() => buildSharedPalette(frames, images, offsets, scales, frameSize, colorCount), [colorCount, frameSize, frames, images, offsets, scales])

  useEffect(() => {
    if (frameIndexes.length > 0 && !frameIndexes.includes(selectedIndex)) setSelectedIndex(frameIndexes[0])
  }, [frameIndexes, selectedIndex])

  useEffect(() => {
    setColorCount(initialColorCount)
  }, [initialColorCount])

  useEffect(() => {
    let cancelled = false
    setLoadError('')
    setImages(new Map())
    const pending = frames.map((frame) => new Promise<[number, HTMLImageElement] | null>((resolve) => {
      const url = signedFileUrl(frame.url)
      if (!url) {
        resolve(null)
        return
      }
      const image = new Image()
      image.onload = () => resolve([Number(frame.index), image])
      image.onerror = () => resolve(null)
      image.src = url
    }))
    void Promise.all(pending).then((entries) => {
      if (cancelled) return
      const next = new Map<number, HTMLImageElement>()
      for (const entry of entries) {
        if (entry) next.set(entry[0], entry[1])
      }
      setImages(next)
      if (next.size !== frames.length) setLoadError(text('部分帧图片加载失败，无法完整预览。', 'Some frames failed to load; preview may be incomplete.'))
    })
    return () => { cancelled = true }
  }, [frames, text])

  const drawEditor = useCallback(() => {
    const canvas = editorCanvasRef.current
    if (!canvas) return
    prepareCanvas(canvas, frameSize)
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, frameSize.width, frameSize.height)
    const ghostImage = images.get(ghostIndex)
    if (ghostImage) {
      ctx.globalAlpha = onionOpacity / 100
      drawFrameImage(ctx, ghostImage, offsetFor(offsets, ghostIndex), scaleFor(scales, ghostIndex), sharedPalette)
      ctx.globalAlpha = 1
    }
    const current = images.get(selectedIndex)
    if (current) drawFrameImage(ctx, current, selectedOffset, selectedScale, sharedPalette)
    drawCanvasGuides(ctx, frameSize)
  }, [frameSize, ghostIndex, images, offsets, onionOpacity, scales, selectedIndex, selectedOffset, selectedScale, sharedPalette])

  const drawPreview = useCallback(() => {
    const canvas = previewCanvasRef.current
    if (!canvas || playableIndexes.length === 0) return
    prepareCanvas(canvas, frameSize)
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, frameSize.width, frameSize.height)
    const index = playableIndexes[previewIndex % playableIndexes.length]
    const image = images.get(index)
    if (image) drawFrameImage(ctx, image, offsetFor(offsets, index), scaleFor(scales, index), sharedPalette)
  }, [frameSize, images, offsets, playableIndexes, previewIndex, scales, sharedPalette])

  useEffect(() => { drawEditor() }, [drawEditor])
  useEffect(() => { drawPreview() }, [drawPreview])

  useEffect(() => {
    if (!playing || playableIndexes.length <= 1) return
    const timer = window.setInterval(() => setPreviewIndex((current) => (current + 1) % playableIndexes.length), Math.max(20, Math.round(1000 / Math.max(1, fps))))
    return () => window.clearInterval(timer)
  }, [fps, playableIndexes.length, playing])

  useEffect(() => { setPreviewIndex(0) }, [loopCheck, playableIndexes.length])

  function updateOffset(index: number, next: Offset) {
    setOffsets((current) => ({ ...current, [index]: { x: Math.round(next.x), y: Math.round(next.y) } }))
  }

  function updateEditorZoom(next: number) {
    setEditorZoom(Math.max(MIN_EDITOR_ZOOM, Math.min(MAX_EDITOR_ZOOM, Math.round(next))))
  }

  function updateColorCount(next: number) {
    setColorCount(clampColorCount(next))
  }

  function updateScale(index: number, next: number) {
    setScales((current) => ({ ...current, [index]: clampFrameScale(next) }))
  }

  function adjustSelectedScale(delta: number) {
    setScales((current) => {
      const base = scaleFor(current, selectedIndex)
      return { ...current, [selectedIndex]: clampFrameScale(base + delta) }
    })
  }

  // 滚轮缩放：仅作用于「当前选中帧的主体」（绕帧中心缩放），画布尺寸 / 影子 / 其它帧都不受影响。
  // React 合成事件的 onWheel 是 passive 的，无法 preventDefault；必须用原生监听器。
  useEffect(() => {
    const node = editorViewportRef.current
    if (!node) return
    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.metaKey) return // 让浏览器原生页面缩放保留行为
      event.preventDefault()
      if (event.deltaY === 0) return
      const direction = event.deltaY < 0 ? 1 : -1
      adjustSelectedScale(direction * FRAME_SCALE_STEP)
    }
    node.addEventListener('wheel', handleWheel, { passive: false })
    return () => node.removeEventListener('wheel', handleWheel)
    // adjustSelectedScale 依赖 selectedIndex，但我们用闭包捕获最新值的方式重新绑定监听器
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndex])

  function currentPoint(event: PointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget
    const rect = canvas.getBoundingClientRect()
    return {
      x: ((event.clientX - rect.left) / rect.width) * frameSize.width,
      y: ((event.clientY - rect.top) / rect.height) * frameSize.height,
    }
  }

  function pointerDown(event: PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = currentPoint(event)
    dragRef.current = { startX: point.x, startY: point.y, startOffset: selectedOffset }
  }

  function pointerMove(event: PointerEvent<HTMLCanvasElement>) {
    if (!dragRef.current) return
    const point = currentPoint(event)
    const dx = Math.round(point.x - dragRef.current.startX)
    const dy = Math.round(point.y - dragRef.current.startY)
    updateOffset(selectedIndex, { x: dragRef.current.startOffset.x + dx, y: dragRef.current.startOffset.y + dy })
  }

  function pointerUp(event: PointerEvent<HTMLCanvasElement>) {
    dragRef.current = null
    try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { undefined }
  }

  function moveSelected(dx: number, dy: number) {
    updateOffset(selectedIndex, { x: selectedOffset.x + dx, y: selectedOffset.y + dy })
  }

  function selectRelative(delta: number) {
    const current = Math.max(0, frameIndexes.indexOf(selectedIndex))
    const next = frameIndexes[(current + delta + frameIndexes.length) % frameIndexes.length]
    if (next) setSelectedIndex(next)
  }

  function resetCurrent() {
    updateOffset(selectedIndex, { x: 0, y: 0 })
    updateScale(selectedIndex, FRAME_SCALE_DEFAULT)
  }

  function resetAll() {
    setOffsets({})
    setScales({})
  }

  function copyGhostOffset() {
    updateOffset(selectedIndex, offsetFor(offsets, ghostIndex))
    updateScale(selectedIndex, scaleFor(scales, ghostIndex))
  }

  function alignTo(targetIndex: number) {
    if (!selectedFrame) return
    const target = frames.find((frame) => Number(frame.index) === targetIndex)
    if (!target) return
    const targetImage = images.get(targetIndex)
    const targetSourceSize = imageSourceSize(targetImage, frameSize)
    const targetAnchor = bottomCenter(target, offsetFor(offsets, targetIndex), frameSize, targetSourceSize, scaleFor(scales, targetIndex), targetImage)
    const currentAnchor = bottomCenter(selectedFrame, selectedOffset, frameSize, selectedSourceSize, selectedScale, selectedImage)
    updateOffset(selectedIndex, { x: selectedOffset.x + Math.round(targetAnchor.x - currentAnchor.x), y: selectedOffset.y + Math.round(targetAnchor.y - currentAnchor.y) })
  }

  function snapVisiblePixels(edge: SnapEdge) {
    if (!selectedVisibleBounds) return
    // 目标：让缩放后投影到画布的可见像素紧贴指定边。
    // 画布坐标公式（见 drawFrameImage / projectBoundsToCanvas）：
    //   canvasX = baseX + offsetX + bound * scale，  baseX = round(srcW/2 - newW/2)
    //   canvasY = baseY + offsetY + bound * scale，  baseY = round(srcH/2 - newH/2)
    // 推理：目标 canvasX/Y = 画布边界 → offsetX = 边界 - baseX - bound * scale
    const scale = Math.max(1e-3, selectedScale)
    const newW = Math.max(1, Math.round(selectedSourceSize.width * scale))
    const newH = Math.max(1, Math.round(selectedSourceSize.height * scale))
    const baseX = Math.round(selectedSourceSize.width / 2 - newW / 2)
    const baseY = Math.round(selectedSourceSize.height / 2 - newH / 2)
    const next = { ...selectedOffset }
    if (edge === 'left') {
      next.x = Math.round(0 - baseX - selectedVisibleBounds.left * scale)
    } else if (edge === 'right') {
      next.x = Math.round(frameSize.width - baseX - selectedVisibleBounds.right * scale)
    } else if (edge === 'top') {
      next.y = Math.round(0 - baseY - selectedVisibleBounds.top * scale)
    } else {
      next.y = Math.round(frameSize.height - baseY - selectedVisibleBounds.bottom * scale)
    }
    updateOffset(selectedIndex, next)
  }

  async function save() {
    await onSave({
      fps,
      colors: colorCount,
      gif_export: true,
      frames: frameIndexes.map((index) => {
        const offset = offsetFor(offsets, index)
        const scale = scaleFor(scales, index)
        return { index, offset_x: offset.x, offset_y: offset.y, scale }
      }),
    })
  }

  if (frames.length === 0) {
    return <Alert variant="destructive">{text('这个作品没有可调整的序列帧数据。', 'This work has no editable sequence-frame data.')}</Alert>
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,340px)]">
        <section className="flex min-h-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{selectedIndex === selectedPosition ? text(`第 ${selectedPosition} / ${frameIndexes.length} 帧`, `Frame ${selectedPosition} / ${frameIndexes.length}`) : text(`第 ${selectedPosition} / ${frameIndexes.length} 帧（全局 #${selectedIndex}）`, `Frame ${selectedPosition} / ${frameIndexes.length} (global #${selectedIndex})`)}</Badge>
            <Badge variant="outline">{frameSize.width}×{frameSize.height}</Badge>
            <Badge variant={Math.abs(selectedScale - 1) < 1e-3 ? 'muted' : 'info'}>{`${selectedScale.toFixed(2)}×`}</Badge>
            <Badge variant="outline">{text(`影子：第 ${ghostIndex} 帧`, `Ghost: frame ${ghostIndex}`)}</Badge>
            {projectedVisibleBounds ? <Badge variant="muted">{text(`可见像素：${projectedVisibleBounds.left},${projectedVisibleBounds.top} → ${projectedVisibleBounds.right},${projectedVisibleBounds.bottom}`, `Visible pixels: ${projectedVisibleBounds.left},${projectedVisibleBounds.top} → ${projectedVisibleBounds.right},${projectedVisibleBounds.bottom}`)}</Badge> : <Badge variant="warning">{text('未识别到可见像素', 'No visible pixels detected')}</Badge>}
            <div className="flex w-full min-w-0 flex-wrap items-center gap-2 rounded-lg border border-border bg-card/80 px-2 py-1.5 sm:ml-auto sm:w-auto sm:min-w-[260px] dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
              <Button type="button" size="sm" variant="ghost" disabled={editorZoom <= MIN_EDITOR_ZOOM} onClick={() => updateEditorZoom(editorZoom - 1)}><ZoomOut />{text('画布缩小', 'Canvas −')}</Button>
              <Slider className="min-w-24 flex-1" value={editorZoom} min={MIN_EDITOR_ZOOM} max={MAX_EDITOR_ZOOM} step={1} onValueChange={updateEditorZoom} aria-label={text('编辑画布显示倍数', 'Editor canvas display scale')} />
              <Button type="button" size="sm" variant="ghost" disabled={editorZoom >= MAX_EDITOR_ZOOM} onClick={() => updateEditorZoom(editorZoom + 1)}><ZoomIn />{text('画布放大', 'Canvas +')}</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => updateEditorZoom(DEFAULT_EDITOR_ZOOM)}>{editorZoom}×</Button>
            </div>
          </div>
          <div
            ref={editorViewportRef}
            className="pix-checkerboard grid min-h-[240px] flex-1 place-items-center overflow-auto rounded-xl border border-border bg-muted/40 p-4 dark:border-[hsl(var(--pix-dark-hairline))]"
            title={text('鼠标滚轮缩放当前帧主体（绕帧中心；Ctrl/Cmd + 滚轮 = 浏览器缩放）', 'Mouse wheel scales the current frame around its center (Ctrl/Cmd + wheel keeps browser zoom)')}
          >
            <canvas
              ref={editorCanvasRef}
              tabIndex={0}
              aria-label={text('拖动当前帧、滚轮缩放当前帧主体', 'Drag current frame, mouse wheel scales the current frame')}
              onPointerDown={pointerDown}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerCancel={pointerUp}
              onKeyDown={(event) => {
                const step = event.shiftKey ? 8 : 1
                if (event.key === 'ArrowLeft') { event.preventDefault(); moveSelected(-step, 0) }
                if (event.key === 'ArrowRight') { event.preventDefault(); moveSelected(step, 0) }
                if (event.key === 'ArrowUp') { event.preventDefault(); moveSelected(0, -step) }
                if (event.key === 'ArrowDown') { event.preventDefault(); moveSelected(0, step) }
              }}
              className="touch-none rounded-lg outline-none ring-1 ring-border [image-rendering:pixelated] focus-visible:ring-2 focus-visible:ring-ring dark:ring-[hsl(var(--pix-dark-hairline))]"
              style={{ width: frameSize.width * editorZoom, height: frameSize.height * editorZoom, maxWidth: 'none' }}
            />
          </div>
          {loadError && <Alert variant="warning">{loadError}</Alert>}
          <div className="grid max-h-32 shrink-0 grid-cols-4 gap-2 overflow-y-auto pr-1 sm:grid-cols-8 xl:max-h-28">
            {frames.map((frame) => {
              const index = Number(frame.index)
              const active = index === selectedIndex
              const offset = offsetFor(offsets, index)
              const scale = scaleFor(scales, index)
              const showScale = Math.abs(scale - 1) >= 1e-3
              return <button key={index} type="button" className={`rounded-lg border p-2 text-xs transition ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-muted/35 hover:bg-muted dark:border-[hsl(var(--pix-dark-hairline))]'}`} onClick={() => setSelectedIndex(index)}>{index}<span className="mt-1 block opacity-75">{offset.x},{offset.y}</span>{showScale && <span className="block opacity-75">{scale.toFixed(2)}×</span>}</button>
            })}
          </div>
        </section>

        <aside className="grid min-h-0 content-start gap-3 overflow-y-auto pr-1">
          <div className="pix-checkerboard flex h-44 items-center justify-center overflow-hidden rounded-xl border border-border bg-muted/40 p-3 dark:border-[hsl(var(--pix-dark-hairline))]">
            <canvas ref={previewCanvasRef} className="h-full w-full rounded-lg object-contain [image-rendering:pixelated]" />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => setPlaying((value) => !value)}>{playing ? <Pause /> : <Play />}{playing ? text('暂停', 'Pause') : text('播放', 'Play')}</Button>
            <Button type="button" variant={loopCheck ? 'default' : 'outline'} onClick={() => setLoopCheck((value) => !value)}><Crosshair />{text('首尾检查', 'Loop check')}</Button>
          </div>
          <label className="grid gap-2 text-sm font-medium">FPS<Input type="number" min={1} max={60} value={fps} onChange={(event) => setFps(Math.max(1, Math.min(60, Math.round(Number(event.target.value) || 8))))} /></label>
          <div className="grid gap-2 rounded-lg border border-border/70 bg-card/60 p-3 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
            <div className="flex items-center justify-between gap-3 text-sm font-medium"><span>{text('颜色数量', 'Color count')}</span><Badge variant="info">{text(`${colorCount} 色`, `${colorCount} colors`)}</Badge></div>
            <Slider value={colorCount} min={COLOR_COUNT_MIN} max={COLOR_COUNT_MAX} step={1} onValueChange={updateColorCount} aria-label={text('颜色数量实时预览', 'Live color count preview')} />
            <Input type="number" min={COLOR_COUNT_MIN} max={COLOR_COUNT_MAX} step={1} value={colorCount} onChange={(event) => updateColorCount(Number(event.target.value))} />
            <p className="text-xs leading-relaxed text-muted-foreground">{text('拖动后会立即用共享调色板重绘编辑画布和播放预览，保存时同步写入输出。', 'Updates the editor and playback preview immediately with a shared palette; saved output uses the same count.')}</p>
          </div>
          <label className="grid gap-2 text-sm font-medium">{text('影子透明度', 'Ghost opacity')}<Slider value={onionOpacity} min={0} max={80} step={5} onValueChange={setOnionOpacity} /></label>
        </aside>
      </div>

      <div className="grid max-h-[34dvh] shrink-0 gap-3 overflow-y-auto rounded-xl border border-border bg-muted/35 p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="grid gap-1 text-sm font-medium">X<Input type="number" value={selectedOffset.x} onChange={(event) => updateOffset(selectedIndex, { x: Number(event.target.value) || 0, y: selectedOffset.y })} /></label>
          <label className="grid gap-1 text-sm font-medium">Y<Input type="number" value={selectedOffset.y} onChange={(event) => updateOffset(selectedIndex, { x: selectedOffset.x, y: Number(event.target.value) || 0 })} /></label>
          <Button type="button" variant="outline" onClick={() => selectRelative(-1)}><SkipBack />{text('上一帧', 'Previous')}</Button>
          <Button type="button" variant="outline" onClick={() => selectRelative(1)}><SkipForward />{text('下一帧', 'Next')}</Button>
        </div>
        <div className="grid gap-2 rounded-lg border border-border/70 bg-card/60 p-3 sm:grid-cols-[minmax(0,1fr)_120px_auto] sm:items-center dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]">
          <label className="grid gap-2 text-sm font-medium">{text('当前帧主体缩放（绕中心；滚轮可调）', 'Current frame scale (around center; mouse wheel)')}<Slider value={Math.round(selectedScale * 100)} min={Math.round(FRAME_SCALE_MIN * 100)} max={Math.round(FRAME_SCALE_MAX * 100)} step={Math.round(FRAME_SCALE_STEP * 100)} onValueChange={(value) => updateScale(selectedIndex, value / 100)} /></label>
          <Input type="number" min={FRAME_SCALE_MIN} max={FRAME_SCALE_MAX} step={FRAME_SCALE_STEP} value={selectedScale.toFixed(2)} onChange={(event) => updateScale(selectedIndex, Number(event.target.value))} />
          <Button type="button" variant="ghost" size="sm" disabled={Math.abs(selectedScale - FRAME_SCALE_DEFAULT) < 1e-3} onClick={() => updateScale(selectedIndex, FRAME_SCALE_DEFAULT)}>{text('重置缩放', 'Reset scale')}</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={copyGhostOffset}><Copy />{text('复制影子偏移', 'Copy ghost offset')}</Button>
          <Button type="button" variant="outline" onClick={() => alignTo(ghostIndex)}><Crosshair />{text('底部对齐影子', 'Align to ghost')}</Button>
          <Button type="button" variant="outline" onClick={() => alignTo(frameIndexes[0])}><Crosshair />{text('对齐本组首帧', 'Align to group first frame')}</Button>
          <Button type="button" variant="outline" disabled={!selectedVisibleBounds} onClick={() => snapVisiblePixels('left')}>{text('吸附左边', 'Snap left')}</Button>
          <Button type="button" variant="outline" disabled={!selectedVisibleBounds} onClick={() => snapVisiblePixels('right')}>{text('吸附右边', 'Snap right')}</Button>
          <Button type="button" variant="outline" disabled={!selectedVisibleBounds} onClick={() => snapVisiblePixels('top')}>{text('吸附上边', 'Snap top')}</Button>
          <Button type="button" variant="outline" disabled={!selectedVisibleBounds} onClick={() => snapVisiblePixels('bottom')}>{text('吸附底边', 'Snap bottom')}</Button>
          <Button type="button" variant="ghost" onClick={resetCurrent}><RotateCcw />{text('重置当前', 'Reset current')}</Button>
          <Button type="button" variant="ghost" onClick={resetAll}><RotateCcw />{text('重置全部', 'Reset all')}</Button>
          <Button type="button" className="ml-auto" disabled={saving || images.size === 0} onClick={() => void save()}><Save />{saving ? text('保存中…', 'Saving…') : text('保存', 'Save')}</Button>
        </div>
      </div>
    </div>
  )
}

function prepareCanvas(canvas: HTMLCanvasElement, size: { width: number; height: number }) {
  if (canvas.width !== size.width) canvas.width = size.width
  if (canvas.height !== size.height) canvas.height = size.height
}

function drawFrameImage(ctx: CanvasRenderingContext2D, image: HTMLImageElement, offset: Offset, scale: number = 1, palette: RgbColor[] | null = null) {
  if (palette?.length) {
    const frame = renderFrameCanvas({ width: ctx.canvas.width, height: ctx.canvas.height }, image, offset, scale, palette)
    if (frame) ctx.drawImage(frame, 0, 0)
    return
  }
  drawFrameImageRaw(ctx, image, offset, scale)
}

function drawFrameImageRaw(ctx: CanvasRenderingContext2D, image: HTMLImageElement, offset: Offset, scale: number = 1) {
  const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1
  if (Math.abs(safeScale - 1) < 1e-3) {
    ctx.drawImage(image, Math.round(offset.x), Math.round(offset.y))
    return
  }
  const sourceWidth = image.naturalWidth || image.width
  const sourceHeight = image.naturalHeight || image.height
  if (!sourceWidth || !sourceHeight) return
  const newWidth = Math.max(1, Math.round(sourceWidth * safeScale))
  const newHeight = Math.max(1, Math.round(sourceHeight * safeScale))
  // 帧中心锚点：缩放后中心仍位于 (sourceWidth / 2, sourceHeight / 2)
  const baseX = Math.round(sourceWidth / 2 - newWidth / 2)
  const baseY = Math.round(sourceHeight / 2 - newHeight / 2)
  ctx.drawImage(image, baseX + Math.round(offset.x), baseY + Math.round(offset.y), newWidth, newHeight)
}

function drawCanvasGuides(ctx: CanvasRenderingContext2D, size: { width: number; height: number }) {
  ctx.save()
  ctx.strokeStyle = 'rgba(99,102,241,.75)'
  ctx.lineWidth = 1
  ctx.setLineDash([2, 3])
  ctx.strokeRect(0.5, 0.5, size.width - 1, size.height - 1)
  ctx.beginPath()
  ctx.moveTo(size.width / 2, 0)
  ctx.lineTo(size.width / 2, size.height)
  ctx.moveTo(0, size.height - 1)
  ctx.lineTo(size.width, size.height - 1)
  ctx.stroke()
  ctx.restore()
}

function renderFrameCanvas(size: { width: number; height: number }, image: HTMLImageElement, offset: Offset, scale: number, palette?: RgbColor[] | null): HTMLCanvasElement | null {
  if (typeof document === 'undefined') return null
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(size.width))
  canvas.height = Math.max(1, Math.round(size.height))
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null
  ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  drawFrameImageRaw(ctx, image, offset, scale)
  if (palette?.length) applyPaletteToCanvas(canvas, palette)
  return canvas
}

function buildSharedPalette(frames: SpriteFrameOutput[], images: ImageMap, offsets: Record<number, Offset>, scales: Record<number, number>, frameSize: { width: number; height: number }, colors: number): RgbColor[] | null {
  const limit = clampColorCount(colors)
  if (images.size === 0 || typeof document === 'undefined') return null
  const colorMap = new Map<number, WeightedColor>()
  for (const frame of frames) {
    const index = Number(frame.index)
    const image = images.get(index)
    if (!image) continue
    const canvas = renderFrameCanvas(frameSize, image, offsetFor(offsets, index), scaleFor(scales, index))
    const ctx = canvas?.getContext('2d', { willReadFrequently: true })
    if (!canvas || !ctx) continue
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] <= 8) continue
      const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
      const existing = colorMap.get(key)
      if (existing) {
        existing.count += 1
      } else {
        colorMap.set(key, { r: data[i], g: data[i + 1], b: data[i + 2], count: 1 })
      }
    }
  }
  const weighted = Array.from(colorMap.values())
  if (weighted.length === 0) return null
  return quantizeWeightedColors(weighted, limit)
}

function applyPaletteToCanvas(canvas: HTMLCanvasElement, palette: RgbColor[]) {
  if (palette.length === 0) return
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const data = imageData.data
  const nearestCache = new Map<number, RgbColor>()
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] <= 8) continue
    const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
    let nearest = nearestCache.get(key)
    if (!nearest) {
      nearest = nearestPaletteColor(data[i], data[i + 1], data[i + 2], palette)
      nearestCache.set(key, nearest)
    }
    data[i] = nearest.r
    data[i + 1] = nearest.g
    data[i + 2] = nearest.b
  }
  ctx.putImageData(imageData, 0, 0)
}

function quantizeWeightedColors(colors: WeightedColor[], limit: number): RgbColor[] {
  const safeLimit = clampColorCount(limit)
  if (colors.length <= safeLimit) return colors.map(({ r, g, b }) => ({ r, g, b }))
  const buckets = [makePaletteBucket(colors)]
  while (buckets.length < safeLimit) {
    let splitIndex = -1
    let splitScore = -1
    for (let i = 0; i < buckets.length; i += 1) {
      const bucket = buckets[i]
      if (bucket.colors.length <= 1) continue
      const score = bucketScore(bucket)
      if (score > splitScore) {
        splitScore = score
        splitIndex = i
      }
    }
    if (splitIndex < 0) break
    const [bucket] = buckets.splice(splitIndex, 1)
    const [left, right] = splitPaletteBucket(bucket)
    buckets.push(left, right)
  }
  return buckets.map(bucketAverageColor)
}

function makePaletteBucket(colors: WeightedColor[]): PaletteBucket {
  let rMin = 255
  let rMax = 0
  let gMin = 255
  let gMax = 0
  let bMin = 255
  let bMax = 0
  let weight = 0
  for (const color of colors) {
    rMin = Math.min(rMin, color.r)
    rMax = Math.max(rMax, color.r)
    gMin = Math.min(gMin, color.g)
    gMax = Math.max(gMax, color.g)
    bMin = Math.min(bMin, color.b)
    bMax = Math.max(bMax, color.b)
    weight += color.count
  }
  return { colors, weight, rMin, rMax, gMin, gMax, bMin, bMax }
}

function bucketScore(bucket: PaletteBucket): number {
  return Math.max(bucket.rMax - bucket.rMin, bucket.gMax - bucket.gMin, bucket.bMax - bucket.bMin) * Math.max(1, bucket.weight)
}

function splitPaletteBucket(bucket: PaletteBucket): [PaletteBucket, PaletteBucket] {
  const ranges = [bucket.rMax - bucket.rMin, bucket.gMax - bucket.gMin, bucket.bMax - bucket.bMin]
  const channel = ranges[0] >= ranges[1] && ranges[0] >= ranges[2] ? 'r' : ranges[1] >= ranges[2] ? 'g' : 'b'
  const sorted = [...bucket.colors].sort((a, b) => a[channel] - b[channel])
  const halfWeight = bucket.weight / 2
  let running = 0
  let splitAt = Math.max(1, Math.floor(sorted.length / 2))
  for (let i = 0; i < sorted.length - 1; i += 1) {
    running += sorted[i].count
    if (running >= halfWeight) {
      splitAt = i + 1
      break
    }
  }
  splitAt = Math.max(1, Math.min(sorted.length - 1, splitAt))
  return [makePaletteBucket(sorted.slice(0, splitAt)), makePaletteBucket(sorted.slice(splitAt))]
}

function bucketAverageColor(bucket: PaletteBucket): RgbColor {
  let r = 0
  let g = 0
  let b = 0
  const weight = Math.max(1, bucket.weight)
  for (const color of bucket.colors) {
    r += color.r * color.count
    g += color.g * color.count
    b += color.b * color.count
  }
  return { r: Math.round(r / weight), g: Math.round(g / weight), b: Math.round(b / weight) }
}

function nearestPaletteColor(r: number, g: number, b: number, palette: RgbColor[]): RgbColor {
  let best = palette[0]
  let bestDistance = Number.POSITIVE_INFINITY
  for (const color of palette) {
    const dr = r - color.r
    const dg = g - color.g
    const db = b - color.b
    const distance = dr * dr + dg * dg + db * db
    if (distance < bestDistance) {
      best = color
      bestDistance = distance
    }
  }
  return best
}

function offsetFor(offsets: Record<number, Offset>, index: number): Offset {
  return offsets[index] ?? { x: 0, y: 0 }
}

function scaleFor(scales: Record<number, number>, index: number): number {
  const value = scales[index]
  return Number.isFinite(value) && value > 0 ? value : FRAME_SCALE_DEFAULT
}

function clampFrameScale(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return FRAME_SCALE_DEFAULT
  return Math.max(FRAME_SCALE_MIN, Math.min(FRAME_SCALE_MAX, Math.round(value * 100) / 100))
}

function clampColorCount(value: number): number {
  if (!Number.isFinite(value)) return COLOR_COUNT_DEFAULT
  return Math.max(COLOR_COUNT_MIN, Math.min(COLOR_COUNT_MAX, Math.round(value)))
}

function ghostFrameIndex(indexes: number[], selectedIndex: number) {
  if (indexes.length <= 1) return selectedIndex
  const position = Math.max(0, indexes.indexOf(selectedIndex))
  return indexes[(position - 1 + indexes.length) % indexes.length]
}

function bottomCenter(frame: SpriteFrameOutput, offset: Offset, frameSize: { width: number; height: number }, sourceSize?: { width: number; height: number }, scale: number = 1, image?: HTMLImageElement) {
  const bounds = visibleBoundsForFrame(frame, image)
  if (!bounds) return { x: frameSize.width / 2 + offset.x, y: frameSize.height + offset.y }
  const safeSource = sourceSize ?? { width: bounds.right, height: bounds.bottom }
  const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1
  const newW = Math.max(1, Math.round(safeSource.width * safeScale))
  const newH = Math.max(1, Math.round(safeSource.height * safeScale))
  const baseX = Math.round(safeSource.width / 2 - newW / 2)
  const baseY = Math.round(safeSource.height / 2 - newH / 2)
  return {
    x: baseX + offset.x + ((bounds.left + bounds.right) / 2) * safeScale,
    y: baseY + offset.y + bounds.bottom * safeScale,
  }
}

function visibleBoundsForFrame(_frame: SpriteFrameOutput, image?: HTMLImageElement): VisibleBounds | null {
  // 始终扫描最终单帧 PNG 的 alpha：保证坐标系与画布绘制完全一致，
  // 避免使用后端 bbox（不同坐标系）引起吸附/对齐误差。
  return image ? scanAlphaBounds(image) : null
}

function scanAlphaBounds(image: HTMLImageElement): VisibleBounds | null {
  const width = image.naturalWidth || image.width
  const height = image.naturalHeight || image.height
  if (width <= 0 || height <= 0) return null
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(image, 0, 0)
  try {
    const data = ctx.getImageData(0, 0, width, height).data
    let left = width
    let top = height
    let right = -1
    let bottom = -1
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const alpha = data[(y * width + x) * 4 + 3]
        if (alpha <= 8) continue
        if (x < left) left = x
        if (x > right) right = x
        if (y < top) top = y
        if (y > bottom) bottom = y
      }
    }
    return right >= left && bottom >= top ? { left, top, right: right + 1, bottom: bottom + 1 } : null
  } catch {
    return null
  }
}

function imageSourceSize(image: HTMLImageElement | undefined, frameSize: { width: number; height: number }): { width: number; height: number } {
  if (image && (image.naturalWidth || image.width) && (image.naturalHeight || image.height)) {
    return { width: image.naturalWidth || image.width, height: image.naturalHeight || image.height }
  }
  return { width: Math.max(1, frameSize.width), height: Math.max(1, frameSize.height) }
}

function projectBoundsToCanvas(bounds: VisibleBounds, sourceSize: { width: number; height: number }, scale: number, offset: Offset): VisibleBounds {
  const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1
  const newW = Math.max(1, Math.round(sourceSize.width * safeScale))
  const newH = Math.max(1, Math.round(sourceSize.height * safeScale))
  const baseX = Math.round(sourceSize.width / 2 - newW / 2)
  const baseY = Math.round(sourceSize.height / 2 - newH / 2)
  return {
    left: Math.round(baseX + offset.x + bounds.left * safeScale),
    top: Math.round(baseY + offset.y + bounds.top * safeScale),
    right: Math.round(baseX + offset.x + bounds.right * safeScale),
    bottom: Math.round(baseY + offset.y + bounds.bottom * safeScale),
  }
}

function colorCountFromJob(job: GenerationJob) {
  const pixelize = typeof job.params_json?.pixelize === 'object' && job.params_json?.pixelize !== null ? job.params_json.pixelize as Record<string, unknown> : null
  const sprite = typeof job.params_json?.sprite === 'object' && job.params_json?.sprite !== null ? job.params_json.sprite as Record<string, unknown> : null
  const value = Number(pixelize?.colors ?? sprite?.colors)
  return Number.isFinite(value) && value > 0 ? clampColorCount(value) : COLOR_COUNT_DEFAULT
}

function spriteFpsFromJob(job: GenerationJob) {
  const sprite = typeof job.params_json?.sprite === 'object' && job.params_json?.sprite !== null ? job.params_json.sprite as Record<string, unknown> : null
  const fps = Number(sprite?.fps)
  return Number.isFinite(fps) && fps > 0 ? fps : 8
}
