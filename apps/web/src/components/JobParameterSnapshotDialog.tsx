import { useMemo, useState, type ReactNode } from 'react'
import { Clipboard, FileJson, Settings2 } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/utils'
import { jobTypeLabel } from '../labels'
import type { GenerationJob, JobOutput } from '../types'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog'

export function JobParameterSnapshotDialog({ job, output }: { job: GenerationJob; output?: JobOutput }) {
  const { language, text, t } = useI18n()
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const snapshot = useMemo(() => buildSnapshot(job, output), [job, output])
  const params = asRecord(job.params_json)
  const pixelize = asRecord(params?.pixelize)
  const sprite = asRecord(params?.sprite)
  const asset = asRecord(params?.asset)
  const billing = asRecord(params?.billing)
  const modelRows = compactRows([
    ['image_model', stringOrDash(params?.image_model)],
    ['image_size', stringOrDash(params?.image_size)],
    ['image_quality', stringOrDash(params?.image_quality)],
    ['vl_model', stringOrDash(params?.vl_model)],
    ['skip_vl', yesNo(params?.skip_vl, text)],
    ['source_only', yesNo(params?.source_only, text)],
  ])
  const pixelRows = compactRows([
    ['output_size', pairLabel(pixelize?.output_size)],
    ['colors', stringOrDash(pixelize?.colors)],
    ['dither', stringOrDash(pixelize?.dither)],
    ['remove_bg', yesNo(pixelize?.remove_bg, text)],
    ['preset', stringOrDash(pixelize?.preset)],
    ['edge_style', stringOrDash(pixelize?.edge_style)],
    ['edge_enhance', stringOrDash(pixelize?.edge_enhance)],
    ['bg_tolerance', stringOrDash(pixelize?.bg_tolerance)],
  ])
  const spriteRows = compactRows([
    ['frame_count', stringOrDash(sprite?.frame_count)],
    ['fps', stringOrDash(sprite?.fps)],
    ['gif_export', yesNo(sprite?.gif_export, text)],
    ['duration_ms', stringOrDash(sprite?.duration_ms)],
    ['loop', stringOrDash(sprite?.loop)],
    ['rows × cols', sprite ? `${stringOrDash(sprite.rows)} × ${stringOrDash(sprite.cols)}` : '—'],
  ])
  const assetRows = compactRows([
    ['name', stringOrDash(asset?.name)],
    ['asset_kind', stringOrDash(asset?.asset_kind)],
    ['subject_kind', stringOrDash(asset?.subject_kind)],
    ['no_preview', yesNo(asset?.no_preview, text)],
  ])
  const billingRows = compactRows([
    ['price_credits', String(job.price_credits)],
    ['reserved_credits', String(job.reserved_credits)],
    ['frame_base_price', stringOrDash(billing?.frame_base_price)],
    ['frame_count', stringOrDash(billing?.frame_count)],
    ['total_points', stringOrDash(billing?.total_points)],
    ['formula', stringOrDash(billing?.formula)],
  ])
  const outputRows = compactRows([
    ['source', stringOrDash(output?.source_path)],
    ['pixelized', stringOrDash(output?.pixelized_path)],
    ['preview', stringOrDash(output?.preview_path)],
    ['sprite_sheet', stringOrDash(output?.sprite_sheet_path)],
    ['sequence_json', stringOrDash(output?.sequence_json_path)],
    ['sprite_gif', stringOrDash(output?.sprite_gif_path)],
    ['meta_json', stringOrDash(output?.meta_json_path)],
  ])

  async function copySnapshot() {
    await navigator.clipboard.writeText(JSON.stringify(snapshot, null, 2))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); setOpen(true) }}><Settings2 />{text('参数', 'Params')}</Button>
      <DialogContent onClick={(event) => event.stopPropagation()} className="w-[min(96vw,920px)] max-h-[90vh] overflow-y-auto sm:max-w-none">
        <DialogHeader>
          <div className="flex flex-wrap items-start justify-between gap-3 pr-8">
            <div>
              <DialogTitle>{text('生成参数快照', 'Generation parameter snapshot')}</DialogTitle>
              <DialogDescription>{text('查看这个作品提交时使用的 prompt、模型、像素化、序列帧和计费参数。', 'Review the prompt, model, pixel, sprite, and billing parameters used for this work.')}</DialogDescription>
            </div>
            <Button type="button" variant="outline" onClick={() => void copySnapshot()}><Clipboard />{copied ? text('已复制', 'Copied') : text('复制 JSON', 'Copy JSON')}</Button>
          </div>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">#{job.id}</Badge>
            <Badge variant="secondary">{jobTypeLabel(job.job_type, language)}</Badge>
            <Badge variant="outline">{job.status}</Badge>
            <Badge variant="info">{t('common.points', { count: job.price_credits })}</Badge>
          </div>

          <SnapshotSection title={text('Prompt', 'Prompt')}>
            <PromptBlock label={text('用户 prompt', 'User prompt')} value={job.prompt || text('无 prompt', 'No prompt')} />
            {asset?.name ? <PromptBlock label={text('素材主体', 'Asset subject')} value={String(asset.name)} /> : null}
            {asset?.extra_prompt ? <PromptBlock label={text('额外描述', 'Extra prompt')} value={String(asset.extra_prompt)} /> : null}
            {job.input_image_path ? <KeyValueGrid rows={compactRows([
              [text('输入图片路径', 'Input image path'), job.input_image_path],
              [text('输入图片 URL', 'Input image URL'), signedFileUrl(job.input_image_url)],
            ])} /> : null}
          </SnapshotSection>

          <SnapshotSection title={text('基础信息', 'Basics')}>
            <KeyValueGrid rows={compactRows([
              [text('创建时间', 'Created at'), formatDateTime(job.created_at)],
              [text('开始时间', 'Started at'), job.started_at ? formatDateTime(job.started_at) : '—'],
              [text('完成时间', 'Finished at'), job.finished_at ? formatDateTime(job.finished_at) : '—'],
              [text('批次', 'Batch'), job.batch_name || '—'],
            ])} />
          </SnapshotSection>

          <div className="grid gap-4 lg:grid-cols-2">
            <SnapshotSection title={text('模型参数', 'Model')}><KeyValueGrid rows={modelRows} /></SnapshotSection>
            <SnapshotSection title={text('像素参数', 'Pixel')}><KeyValueGrid rows={pixelRows} /></SnapshotSection>
            {asset && <SnapshotSection title={text('素材直出参数', 'Asset params')}><KeyValueGrid rows={assetRows} /></SnapshotSection>}
            {sprite && <SnapshotSection title={text('序列帧参数', 'Sprite params')}><KeyValueGrid rows={spriteRows} /></SnapshotSection>}
            <SnapshotSection title={text('计费快照', 'Billing')}><KeyValueGrid rows={billingRows} /></SnapshotSection>
            <SnapshotSection title={text('输出文件', 'Outputs')}><KeyValueGrid rows={outputRows} /></SnapshotSection>
          </div>

          <SnapshotSection title={text('完整 JSON', 'Full JSON')} icon={<FileJson className="h-4 w-4" />}>
            <pre className="max-h-72 overflow-auto rounded-lg bg-muted/55 p-3 text-xs leading-5 text-muted-foreground dark:bg-[hsl(var(--pix-dark-band-soft))]">{JSON.stringify(snapshot, null, 2)}</pre>
          </SnapshotSection>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function SnapshotSection({ title, icon, children }: { title: string; icon?: ReactNode; children: ReactNode }) {
  return <section className="grid gap-3 rounded-xl border border-border bg-card p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-card))]"><h3 className="flex items-center gap-2 text-sm font-bold">{icon}{title}</h3>{children}</section>
}

function PromptBlock({ label, value }: { label: string; value: string }) {
  return <div className="grid gap-1"><div className="text-xs font-semibold text-muted-foreground">{label}</div><div className="whitespace-pre-wrap break-words rounded-lg bg-muted/45 p-3 text-sm leading-6 dark:bg-[hsl(var(--pix-dark-band-soft))]">{value}</div></div>
}

function KeyValueGrid({ rows }: { rows: Array<[string, string]> }) {
  return <dl className="grid gap-2 text-sm">{rows.map(([key, value]) => <div key={key} className="grid gap-1 rounded-lg bg-muted/32 p-2.5 sm:grid-cols-[150px_minmax(0,1fr)] dark:bg-[hsl(var(--pix-dark-band-soft))]"><dt className="text-xs font-semibold text-muted-foreground">{key}</dt><dd className="min-w-0 break-words font-medium">{value}</dd></div>)}</dl>
}

function buildSnapshot(job: GenerationJob, output?: JobOutput) {
  return {
    id: job.id,
    job_type: job.job_type,
    status: job.status,
    prompt: job.prompt,
    input_image_path: job.input_image_path,
    input_image_url: job.input_image_url,
    price_credits: job.price_credits,
    reserved_credits: job.reserved_credits,
    created_at: job.created_at,
    started_at: job.started_at,
    finished_at: job.finished_at,
    params_json: job.params_json,
    output,
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function stringOrDash(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function pairLabel(value: unknown): string {
  return Array.isArray(value) && value.length === 2 ? `${value[0]}×${value[1]}` : stringOrDash(value)
}

function yesNo(value: unknown, text: (zh: string, en: string) => string): string {
  if (value === null || value === undefined) return '—'
  return Boolean(value) ? text('是', 'Yes') : text('否', 'No')
}

function compactRows(rows: Array<[string, string]>): Array<[string, string]> {
  return rows.filter(([, value]) => value !== '—')
}
