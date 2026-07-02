import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, Eye, RefreshCw, RotateCcw, ShieldCheck, XCircle } from 'lucide-react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'
import { formatDateTime } from '../lib/utils'
import type { AdminSharedWork } from '../types'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Textarea } from './ui/textarea'
import { PixField } from './pix/PixField'

const STATUS_OPTIONS = [
  { value: 'pending', label: '待审核' },
  { value: 'active', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'hidden', label: '已下架/撤回' },
  { value: 'all', label: '全部非删除' },
]

type AdminSharesPanelProps = {
  token: string
  onRefresh?: () => void
}

export function AdminSharesPanel({ token, onRefresh }: AdminSharesPanelProps) {
  const [status, setStatus] = useState('pending')
  const [items, setItems] = useState<AdminSharedWork[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const result = await api.adminListShares(token, { status, limit: 120 })
      setItems(result.items)
      setTotal(result.total)
      setNotes((current) => {
        const next = { ...current }
        for (const item of result.items) {
          if (next[item.id] === undefined) next[item.id] = item.review_note || ''
        }
        return next
      })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [status, token])

  useEffect(() => { void load() }, [load])

  const summary = useMemo(() => ({
    pending: items.filter((item) => item.status === 'pending').length,
    active: items.filter((item) => item.status === 'active').length,
    rejected: items.filter((item) => item.status === 'rejected').length,
  }), [items])

  async function runAction(share: AdminSharedWork, action: 'approve' | 'reject' | 'unpublish') {
    setBusyId(share.id)
    setMessage('')
    setError('')
    try {
      if (action === 'approve') {
        await api.approveShare(token, share.id)
        setMessage(`已通过分享 #${share.id}；作品会展示在首页，奖励已按作者日限结算。`)
      } else if (action === 'reject') {
        await api.rejectShare(token, share.id, notes[share.id] ?? '')
        setMessage(`已驳回分享 #${share.id}。`)
      } else {
        await api.adminUnpublishShare(token, share.id)
        setMessage(`已下架分享 #${share.id}。`)
      }
      await load()
      onRefresh?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 rounded-xl border border-border bg-muted/35 p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">内容审核</h3>
            <p className="text-sm text-muted-foreground">用户提交分享后先进入待审核；通过后才展示在首页并发放奖励。审核预览图使用短时效文件票据访问。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info">当前 {items.length} / {total}</Badge>
            <Badge variant={summary.pending > 0 ? 'warning' : 'outline'}>待审 {summary.pending}</Badge>
            <Badge variant="success">通过 {summary.active}</Badge>
            <Badge variant={summary.rejected > 0 ? 'danger' : 'outline'}>驳回 {summary.rejected}</Badge>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-[220px_auto] sm:items-end">
          <PixField label="审核状态">
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{STATUS_OPTIONS.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
            </Select>
          </PixField>
          <Button type="button" variant="outline" onClick={() => { void load() }} disabled={loading}><RefreshCw />{loading ? '刷新中…' : '刷新列表'}</Button>
        </div>
      </div>

      {message && <Alert variant="success">{message}</Alert>}
      {error && <Alert variant="destructive">{error}</Alert>}
      {loading && items.length === 0 ? <Alert variant="info">正在加载审核列表…</Alert> : null}
      {!loading && items.length === 0 ? <Alert variant="info">当前筛选下没有分享作品。</Alert> : null}

      <div className="grid gap-4">
        {items.map((share) => (
          <ShareReviewCard
            key={share.id}
            share={share}
            busy={busyId === share.id}
            note={notes[share.id] ?? ''}
            onNoteChange={(value) => setNotes((current) => ({ ...current, [share.id]: value }))}
            onApprove={() => { void runAction(share, 'approve') }}
            onReject={() => { void runAction(share, 'reject') }}
            onUnpublish={() => { void runAction(share, 'unpublish') }}
          />
        ))}
      </div>
    </div>
  )
}

function ShareReviewCard({ share, busy, note, onNoteChange, onApprove, onReject, onUnpublish }: { share: AdminSharedWork; busy: boolean; note: string; onNoteChange: (value: string) => void; onApprove: () => void; onReject: () => void; onUnpublish: () => void }) {
  const previewUrl = signedFileUrl(share.preview_url)
  const chips = snapshotChips(share.parameter_snapshot)
  const canApprove = share.status !== 'active'
  const canReject = share.status !== 'rejected' && share.status !== 'hidden'
  const canUnpublish = share.status === 'active'
  return (
    <article className="grid overflow-hidden rounded-xl border border-border bg-card dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))] lg:grid-cols-[240px_minmax(0,1fr)]">
      <a href={previewUrl} target="_blank" rel="noreferrer" className="pix-checkerboard grid min-h-[220px] place-items-center border-b border-border bg-muted/35 p-4 dark:border-[hsl(var(--pix-dark-hairline))] lg:border-b-0 lg:border-r">
        {previewUrl ? <img src={previewUrl} alt={share.title} loading="lazy" decoding="async" className="max-h-[220px] w-full object-contain [image-rendering:pixelated]" /> : <span className="text-sm text-muted-foreground">无预览</span>}
      </a>
      <div className="grid gap-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">分享 #{share.id}</Badge>
              {share.job_id && <Badge variant="outline">任务 #{share.job_id}</Badge>}
              <StatusBadge status={share.status} />
              <Badge variant="secondary">{assetKindLabel(share.asset_kind)}</Badge>
            </div>
            <h4 className="mt-2 line-clamp-2 text-base font-semibold">{share.title || `作品 #${share.job_id ?? share.id}`}</h4>
            <p className="mt-1 text-sm text-muted-foreground">作者：{share.user_email || `用户 #${share.user_id}`} · 提交 {formatDateTime(share.created_at)}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canApprove && <Button size="sm" onClick={onApprove} disabled={busy}><Check />通过</Button>}
            {canUnpublish && <Button size="sm" variant="outline" onClick={onUnpublish} disabled={busy}><RotateCcw />下架</Button>}
          </div>
        </div>

        {chips.length > 0 && <div className="flex flex-wrap gap-1.5">{chips.map((chip) => <Badge key={chip} variant="outline">{chip}</Badge>)}</div>}
        {share.review_note && <Alert variant={share.status === 'rejected' ? 'destructive' : 'info'}>上次审核意见：{share.review_note}</Alert>}

        <details className="rounded-lg border border-border bg-muted/30 p-3 text-xs dark:border-[hsl(var(--pix-dark-hairline))]">
          <summary className="cursor-pointer font-semibold"><Eye className="mr-1 inline h-3.5 w-3.5" />参数快照</summary>
          <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-muted-foreground">{JSON.stringify(share.parameter_snapshot ?? {}, null, 2)}</pre>
        </details>

        <div className="grid gap-2 rounded-lg border border-border bg-muted/30 p-3 dark:border-[hsl(var(--pix-dark-hairline))]">
          <PixField label="驳回理由（作者会在作品库看到）">
            <Textarea value={note} onChange={(event) => onNoteChange(event.target.value)} maxLength={500} placeholder="例如：画面包含水印/不完整，请修改后重新提交。" />
          </PixField>
          <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
            <span>{note.length}/500</span>
            <Button type="button" size="sm" variant="destructive" onClick={onReject} disabled={busy || !canReject}><XCircle />驳回</Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span>点赞 {share.like_count}</span>
          <span>下载 {share.download_count}</span>
          <span>奖励 {share.reward_credits} 点</span>
          {share.reviewed_at && <span><ShieldCheck className="mr-1 inline h-3.5 w-3.5" />审核 {formatDateTime(share.reviewed_at)}</span>}
        </div>
      </div>
    </article>
  )
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'pending') return <Badge variant="warning">待审核</Badge>
  if (status === 'active') return <Badge variant="success">已通过</Badge>
  if (status === 'rejected') return <Badge variant="danger">已驳回</Badge>
  if (status === 'hidden') return <Badge variant="outline">已下架/撤回</Badge>
  return <Badge variant="muted">{status}</Badge>
}

function snapshotChips(snapshot: Record<string, unknown>) {
  const pixel = asRecord(snapshot.pixel)
  const raw = asRecord(snapshot.raw_image)
  const asset = asRecord(snapshot.asset)
  const sequence = asRecord(snapshot.sequence)
  const chips: string[] = []
  const outputSize = pixel.output_size
  if (Array.isArray(outputSize) && outputSize.length === 2) chips.push(`${outputSize[0]}×${outputSize[1]}`)
  if (pixel.colors) chips.push(`${pixel.colors} 色`)
  if (raw.model) chips.push(String(raw.model))
  if (asset.asset_kind) chips.push(assetKindLabel(String(asset.asset_kind)))
  if (sequence.frame_count) chips.push(`${sequence.frame_count} 帧`)
  if (sequence.fps) chips.push(`${sequence.fps} FPS`)
  return chips.slice(0, 6)
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function assetKindLabel(value: string) {
  if (value === 'item_icon') return '物品图标'
  if (value === 'ui_component') return 'UI 组件'
  if (value === 'tile_texture') return '平铺纹理'
  if (value === 'game_logo') return '游戏 Logo'
  if (value === 'dual_grid') return '双瓦片'
  if (value === 'sprite_sheet') return '序列帧'
  return value || '作品'
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
