import { useMemo, useState } from 'react'
import { Archive, RotateCw, Save, Sparkles, Trash2 } from 'lucide-react'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { CharacterItem, CharacterUpdatePayload } from '../types'
import { formatDateTime } from '../lib/utils'
import { Alert } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Textarea } from '../components/ui/textarea'
import { PageHeader } from '../components/PageHeader'
import { PixPanel } from '../components/pix/PixPanel'
import { PixPreviewFrame } from '../components/pix/PixPreviewFrame'

type CharactersPageProps = {
  characters: CharacterItem[]
  loading?: boolean
  onUpdate: (item: CharacterItem, payload: CharacterUpdatePayload) => Promise<CharacterItem | null>
  onDelete: (item: CharacterItem) => Promise<void>
  onGenerateCharacter: () => void
  onRefresh: () => void
}

type Draft = { name: string; description: string; tags: string }

function tagsFromText(value: string) {
  return Array.from(new Set(value.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean))).slice(0, 20)
}

function draftFromCharacter(item: CharacterItem): Draft {
  return { name: item.name, description: item.description || '', tags: (item.tags ?? []).join(', ') }
}

function CharactersPage({ characters, loading = false, onUpdate, onDelete, onGenerateCharacter, onRefresh }: CharactersPageProps) {
  const { text } = useI18n()
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState<Draft>({ name: '', description: '', tags: '' })
  const activeCount = useMemo(() => characters.filter((item) => item.status === 'active').length, [characters])

  function beginEdit(item: CharacterItem) {
    setEditingId(item.id)
    setEditDraft(draftFromCharacter(item))
  }

  async function saveEdit(item: CharacterItem) {
    setSaving(true)
    setMessage('')
    try {
      await onUpdate(item, { name: editDraft.name.trim(), description: editDraft.description.trim(), tags: tagsFromText(editDraft.tags) })
      setEditingId(null)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : text('更新角色失败', 'Failed to update character'))
    } finally {
      setSaving(false)
    }
  }

  async function toggleArchive(item: CharacterItem) {
    await onUpdate(item, { status: item.status === 'archived' ? 'active' : 'archived' })
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        eyebrow={text('角色库', 'Character library')}
        title={text('像素直出角色会自动进入角色库', 'Pixel-direct character jobs are saved automatically')}
        description={text('只有在生产工作台选择「素材直出 → 角色」生成成功的作品会成为角色；序列帧生成时可直接选择这些角色作为参考来源。', 'Only successful “asset → character” generation jobs become character-library items. Sprite generation can use these characters directly as references.')}
        action={<div className="flex flex-wrap gap-2"><Button onClick={onGenerateCharacter}><Sparkles />{text('生成角色', 'Generate character')}</Button><Button variant="outline" onClick={onRefresh} disabled={loading}><RotateCw />{text('刷新', 'Refresh')}</Button></div>}
      />

      {message && <Alert variant="destructive">{message}</Alert>}

      <PixPanel eyebrow={text('角色', 'Characters')} title={text('我的角色库', 'My character library')} action={<div className="flex flex-wrap gap-2"><Badge variant="success">{text(`活跃 ${activeCount}`, `${activeCount} active`)}</Badge><Badge variant="outline">{text(`共 ${characters.length}`, `${characters.length} total`)}</Badge></div>}>
        {characters.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/45 p-8 text-center text-sm text-muted-foreground">
            {text('还没有角色。请点击「生成角色」，在生产工作台使用「素材直出 → 角色」创建 64×64 角色素材。', 'No characters yet. Click “Generate character” and use “asset → character” in the workspace to create a 64×64 character asset.')}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {characters.map((item) => {
              const editing = editingId === item.id
              return (
                <article key={item.id} className="grid gap-3 rounded-lg border border-border bg-card p-3">
                  <PixPreviewFrame url={signedFileUrl(item.preview_url || item.image_url)} label={item.name} />
                  {editing ? (
                    <div className="grid gap-2">
                      <Input value={editDraft.name} maxLength={160} onChange={(event) => setEditDraft((draft) => ({ ...draft, name: event.target.value }))} />
                      <Textarea value={editDraft.description} rows={3} maxLength={1000} onChange={(event) => setEditDraft((draft) => ({ ...draft, description: event.target.value }))} />
                      <Input value={editDraft.tags} onChange={(event) => setEditDraft((draft) => ({ ...draft, tags: event.target.value }))} />
                    </div>
                  ) : (
                    <div className="grid gap-2">
                      <div className="flex flex-wrap items-center gap-1.5"><Badge variant={item.status === 'archived' ? 'outline' : 'success'}>{item.status === 'archived' ? text('已归档', 'Archived') : text('活跃', 'Active')}</Badge>{item.source_job_id && <Badge variant="outline">#{item.source_job_id}</Badge>}</div>
                      <h3 className="line-clamp-2 text-sm font-semibold">{item.name}</h3>
                      {item.description && <p className="line-clamp-3 text-xs leading-5 text-muted-foreground">{item.description}</p>}
                      <div className="flex flex-wrap gap-1">{(item.tags ?? []).slice(0, 5).map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}</div>
                      <p className="text-[11px] text-muted-foreground">{formatDateTime(item.updated_at)}</p>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {editing ? <><Button size="sm" onClick={() => void saveEdit(item)} disabled={saving}><Save />{text('保存', 'Save')}</Button><Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>{text('取消', 'Cancel')}</Button></> : <Button size="sm" variant="outline" onClick={() => beginEdit(item)}>{text('编辑', 'Edit')}</Button>}
                    <Button size="sm" variant="outline" onClick={() => void toggleArchive(item)}><Archive />{item.status === 'archived' ? text('恢复', 'Restore') : text('归档', 'Archive')}</Button>
                    <Button size="sm" variant="ghost" onClick={() => void onDelete(item)}><Trash2 />{text('删除', 'Delete')}</Button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </PixPanel>
    </div>
  )
}

export { CharactersPage }
export default CharactersPage
