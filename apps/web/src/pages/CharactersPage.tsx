import { FormEvent, useMemo, useState } from 'react'
import { Archive, RotateCw, Save, Sparkles, Trash2, Upload } from 'lucide-react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'
import { useI18n } from '../i18n'
import type { CharacterCreatePayload, CharacterItem, CharacterUpdatePayload } from '../types'
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
  token: string
  characters: CharacterItem[]
  loading?: boolean
  onCreate: (payload: CharacterCreatePayload) => Promise<CharacterItem | null>
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

export function CharactersPage({ token, characters, loading = false, onCreate, onUpdate, onDelete, onGenerateCharacter, onRefresh }: CharactersPageProps) {
  const { text } = useI18n()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')
  const [imagePath, setImagePath] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState<Draft>({ name: '', description: '', tags: '' })
  const activeCount = useMemo(() => characters.filter((item) => item.status === 'active').length, [characters])

  async function upload(file: File | undefined) {
    if (!file) return
    setUploading(true)
    setMessage('')
    setImageFile(file)
    setImageUrl('')
    setImagePath('')
    try {
      const uploaded = await api.uploadImage(token, file)
      setImagePath(uploaded.path)
      setImageUrl(signedFileUrl(uploaded.url))
    } catch (error) {
      setImageFile(null)
      setMessage(error instanceof Error ? error.message : text('上传失败', 'Upload failed'))
    } finally {
      setUploading(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!imagePath || saving) return
    setSaving(true)
    setMessage('')
    try {
      await onCreate({ name: name.trim(), description: description.trim(), tags: tagsFromText(tags), image_path: imagePath })
      setName('')
      setDescription('')
      setTags('')
      setImagePath('')
      setImageUrl('')
      setImageFile(null)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : text('保存角色失败', 'Failed to save character'))
    } finally {
      setSaving(false)
    }
  }

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
        title={text('长期保存可复用角色参考图', 'Save reusable character references')}
        description={text('角色库是独立持久资源，不占普通作品库保留格；序列帧生成时可直接选择角色作为参考来源。', 'Character library items are persistent resources outside gallery retention. Sprite generation can use them directly as references.')}
        action={<div className="flex flex-wrap gap-2"><Button onClick={onGenerateCharacter}><Sparkles />{text('生成角色', 'Generate character')}</Button><Button variant="outline" onClick={onRefresh} disabled={loading}><RotateCw />{text('刷新', 'Refresh')}</Button></div>}
      />

      {message && <Alert variant="destructive">{message}</Alert>}

      <PixPanel eyebrow={text('新增', 'New')} title={text('上传角色参考图', 'Upload a character reference')} description={text('适合立绘、三视图、已整理好的角色设定图。', 'Use portraits, turnarounds, or cleaned character reference sheets.')}>
        <form className="grid gap-4" onSubmit={submit}>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
            <div className="grid gap-3">
              <Input value={name} maxLength={160} placeholder={text('角色名称，例如：蓝袍骑士', 'Character name, e.g. Blue Cloak Knight')} onChange={(event) => setName(event.target.value)} />
              <Textarea value={description} rows={3} maxLength={1000} placeholder={text('角色说明（可选）：身份、配色、服装、体型等', 'Notes (optional): identity, palette, costume, body shape, etc.')} onChange={(event) => setDescription(event.target.value)} />
              <Input value={tags} placeholder={text('标签（逗号分隔）：主角, 近战, 蓝色', 'Tags (comma-separated): hero, melee, blue')} onChange={(event) => setTags(event.target.value)} />
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" asChild>
                  <label className="cursor-pointer"><Upload />{uploading ? text('上传中…', 'Uploading…') : imagePath ? text('替换图片', 'Replace image') : text('上传图片', 'Upload image')}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => void upload(event.currentTarget.files?.[0])} /></label>
                </Button>
                <Button type="submit" disabled={!imagePath || uploading || saving}><Save />{saving ? text('保存中…', 'Saving…') : text('保存到角色库', 'Save to library')}</Button>
              </div>
            </div>
            <PixPreviewFrame url={imageUrl} file={imageFile} loading={uploading} label={imagePath ? text('角色图预览', 'Character preview') : text('等待上传', 'Waiting for upload')} />
          </div>
        </form>
      </PixPanel>

      <PixPanel eyebrow={text('角色', 'Characters')} title={text('我的角色库', 'My character library')} action={<div className="flex flex-wrap gap-2"><Badge variant="success">{text(`活跃 ${activeCount}`, `${activeCount} active`)}</Badge><Badge variant="outline">{text(`共 ${characters.length}`, `${characters.length} total`)}</Badge></div>}>
        {characters.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/45 p-8 text-center text-sm text-muted-foreground">{text('还没有角色。上传一张参考图，或在作品库里点击“保存为角色”。', 'No characters yet. Upload a reference, or click “Save as character” in the gallery.')}</div>
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
