import { useEffect, useMemo, useState } from 'react'
import { Check, Clipboard, Code2, KeyRound, RotateCw, ShieldCheck, Trash2 } from 'lucide-react'
import { api, API_BASE } from '../api'
import { useI18n } from '../i18n'
import type { ApiKeyItem } from '../types'
import { PageHeader } from '../components/PageHeader'
import { Alert } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'

const API_SCOPES = [
  'me:read',
  'balance:read',
  'models:read',
  'uploads:create',
  'jobs:create',
  'jobs:read',
  'files:read',
]

const SCOPE_LABELS: Record<string, { zh: string; en: string }> = {
  'me:read': { zh: '读取账号', en: 'Read account' },
  'balance:read': { zh: '读取点数', en: 'Read credits' },
  'models:read': { zh: '读取模型', en: 'Read models' },
  'uploads:create': { zh: '上传图片', en: 'Upload images' },
  'jobs:create': { zh: '创建任务', en: 'Create jobs' },
  'jobs:read': { zh: '读取任务', en: 'Read jobs' },
  'files:read': { zh: '下载结果', en: 'Download files' },
}

function externalBaseUrl() {
  if (typeof window === 'undefined') return `${API_BASE}/external/v1`
  if (API_BASE.startsWith('http')) return `${API_BASE}/external/v1`
  return `${window.location.origin}${API_BASE}/external/v1`
}

function shortDate(value?: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return true
  }
  const area = document.createElement('textarea')
  area.value = value
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.left = '-9999px'
  document.body.appendChild(area)
  area.select()
  const ok = document.execCommand('copy')
  area.remove()
  return ok
}

export function ApiPage({ token }: { token: string }) {
  const { language, text } = useI18n()
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [selectedScopes, setSelectedScopes] = useState<string[]>(API_SCOPES)
  const [expiresAt, setExpiresAt] = useState('')
  const [createdKey, setCreatedKey] = useState('')
  const [copied, setCopied] = useState('')
  const baseUrl = useMemo(() => externalBaseUrl(), [])
  const assetCurl = useMemo(() => `curl -X POST "${baseUrl}/jobs" \\
  -H "Authorization: Bearer $PIX_API_KEY" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: demo-sword-001" \\
  -d '{
    "job_type": "asset",
    "asset": { "name": "蓝色魔法剑", "asset_kind": "item_icon" },
    "pixelize": { "output_size": [32, 32], "colors": 16, "transparent": true },
    "image_model": "image2",
    "skip_vl": true
  }'`, [baseUrl])
  const pollCurl = useMemo(() => `curl "${baseUrl}/jobs/123" \\
  -H "Authorization: Bearer $PIX_API_KEY"

curl -L "${baseUrl}/jobs/123/outputs/pixelized" \\
  -H "Authorization: Bearer $PIX_API_KEY" \\
  -o pixelized.png`, [baseUrl])
  const uploadCurl = useMemo(() => `curl -X POST "${baseUrl}/uploads/images" \\
  -H "Authorization: Bearer $PIX_API_KEY" \\
  -F "file=@reference.png"`, [baseUrl])

  async function load() {
    setLoading(true)
    try {
      setKeys(await api.apiKeys(token))
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [token])

  function toggleScope(scope: string) {
    setSelectedScopes((current) => current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope])
  }

  async function createKey() {
    setSaving(true)
    try {
      const payload = {
        name: name.trim() || text('外部调用 Key', 'External API key'),
        scopes: selectedScopes.length > 0 ? selectedScopes : API_SCOPES,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      }
      const result = await api.createApiKey(token, payload)
      setCreatedKey(result.key)
      setName('')
      setExpiresAt('')
      setSelectedScopes(API_SCOPES)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function toggleKey(key: ApiKeyItem) {
    setSaving(true)
    try {
      await api.updateApiKey(token, key.id, { enabled: !key.enabled })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function revokeKey(key: ApiKeyItem) {
    if (!window.confirm(text(`撤销 API Key「${key.name}」？撤销后无法恢复。`, `Revoke API key “${key.name}”? This cannot be undone.`))) return
    setSaving(true)
    try {
      await api.revokeApiKey(token, key.id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function copy(value: string, label: string) {
    const ok = await copyText(value)
    if (ok) {
      setCopied(label)
      window.setTimeout(() => setCopied(''), 1500)
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        eyebrow={text('开发者 API', 'Developer API')}
        title={text('让外部程序调用 Pix 生图能力', 'Call Pix generation from external programs')}
        description={text('创建长期 API Key，通过 /external/v1 上传参考图、创建生成任务、轮询状态并下载结果。调用会使用当前账号点数余额和同一套安全 / 队列 / 计费规则。', 'Create long-lived API keys to upload references, create generation jobs, poll status, and download outputs through /external/v1. Calls use your account credits and the same safety, queueing, and billing rules.')}
        action={<Button variant="outline" onClick={() => void load()} disabled={loading}><RotateCw />{text('刷新', 'Refresh')}</Button>}
      />

      {error && <Alert variant="destructive">{error}</Alert>}
      {createdKey && (
        <Alert variant="success">
          <div className="grid gap-3">
            <div className="font-semibold">{text('API Key 已创建，请立即复制保存。明文只显示这一次。', 'API key created. Copy it now; the secret is shown only once.')}</div>
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-card p-3 font-mono text-xs break-all dark:bg-black/20">
              <span className="min-w-0 flex-1">{createdKey}</span>
              <Button size="sm" variant="outline" onClick={() => void copy(createdKey, 'new-key')}>{copied === 'new-key' ? <Check /> : <Clipboard />}{copied === 'new-key' ? text('已复制', 'Copied') : text('复制', 'Copy')}</Button>
            </div>
          </div>
        </Alert>
      )}

      <section className="grid gap-5 rounded-lg border border-border bg-card p-5 pix-shadow-panel dark:bg-[hsl(var(--pix-dark-card))]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-xl font-semibold"><KeyRound className="h-5 w-5 text-primary" />{text('API Key 管理', 'API key management')}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{text('Key 只与当前账号绑定；外部请求会按账号余额扣点。建议按用途创建不同 Key。', 'Keys are bound to your account; external requests consume your account credits. Create separate keys per integration.')}</p>
          </div>
          <Badge variant="outline">{text('Base URL', 'Base URL')}: {baseUrl}</Badge>
        </div>

        <div className="grid gap-4 rounded-lg border border-border bg-muted/30 p-4 lg:grid-cols-[minmax(220px,1fr)_1.8fr_auto]">
          <label className="grid gap-1 text-sm font-medium">
            {text('名称', 'Name')}
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder={text('例如：Unity 插件 / Bot', 'e.g. Unity plugin / Bot')} className="rounded-md border border-input bg-background px-3 py-2 text-sm" />
          </label>
          <div className="grid gap-2 text-sm font-medium">
            {text('权限', 'Scopes')}
            <div className="flex flex-wrap gap-2">
              {API_SCOPES.map((scope) => {
                const label = SCOPE_LABELS[scope]
                const active = selectedScopes.includes(scope)
                return <button key={scope} type="button" onClick={() => toggleScope(scope)} className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-muted-foreground hover:text-foreground'}`}>{language === 'en' ? label.en : label.zh}</button>
              })}
            </div>
          </div>
          <div className="grid content-end gap-2">
            <label className="grid gap-1 text-sm font-medium">
              {text('过期时间（可选）', 'Expires at (optional)')}
              <input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} className="rounded-md border border-input bg-background px-3 py-2 text-sm" />
            </label>
            <Button onClick={() => void createKey()} disabled={saving}><ShieldCheck />{saving ? text('创建中…', 'Creating…') : text('创建 Key', 'Create key')}</Button>
          </div>
        </div>

        <div className="grid gap-3">
          {loading && <div className="text-sm text-muted-foreground">{text('正在加载 API Key…', 'Loading API keys…')}</div>}
          {!loading && keys.length === 0 && <div className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">{text('还没有 API Key。创建一个后即可从外部程序调用。', 'No API keys yet. Create one to call Pix from external programs.')}</div>}
          {keys.map((key) => {
            const revoked = Boolean(key.revoked_at)
            return (
              <div key={key.id} className="grid gap-3 rounded-md border border-border bg-background p-4 md:grid-cols-[1fr_auto] md:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{key.name}</span>
                    <Badge variant={revoked ? 'danger' : key.enabled ? 'success' : 'muted'}>{revoked ? text('已撤销', 'Revoked') : key.enabled ? text('启用', 'Enabled') : text('停用', 'Disabled')}</Badge>
                    <span className="font-mono text-xs text-muted-foreground">{key.key_prefix}…</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {key.scopes.map((scope) => <Badge key={scope} variant="outline">{language === 'en' ? (SCOPE_LABELS[scope]?.en ?? scope) : (SCOPE_LABELS[scope]?.zh ?? scope)}</Badge>)}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{text('创建', 'Created')} {shortDate(key.created_at)} · {text('最后使用', 'Last used')} {shortDate(key.last_used_at)} · {text('过期', 'Expires')} {shortDate(key.expires_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  {!revoked && <Button variant="outline" size="sm" onClick={() => void toggleKey(key)} disabled={saving}>{key.enabled ? text('停用', 'Disable') : text('启用', 'Enable')}</Button>}
                  {!revoked && <Button variant="outline" size="sm" onClick={() => void revokeKey(key)} disabled={saving}><Trash2 />{text('撤销', 'Revoke')}</Button>}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="grid gap-5 rounded-lg border border-border bg-card p-5 pix-shadow-panel dark:bg-[hsl(var(--pix-dark-card))]">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-semibold"><Code2 className="h-5 w-5 text-primary" />{text('快速开始', 'Quick start')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{text('以下示例可直接给脚本、游戏编辑器插件或自动化流水线使用。', 'Use these examples from scripts, editor plugins, or automation pipelines.')}</p>
        </div>
        <CodeBlock title={text('1. 创建素材直出任务', '1. Create an asset job')} code={assetCurl} copied={copied} onCopy={(code) => void copy(code, 'asset')} copyKey="asset" />
        <CodeBlock title={text('2. 上传参考图', '2. Upload a reference image')} code={uploadCurl} copied={copied} onCopy={(code) => void copy(code, 'upload')} copyKey="upload" />
        <CodeBlock title={text('3. 轮询并下载结果', '3. Poll and download output')} code={pollCurl} copied={copied} onCopy={(code) => void copy(code, 'poll')} copyKey="poll" />
      </section>
    </div>
  )
}

function CodeBlock({ title, code, copied, copyKey, onCopy }: { title: string; code: string; copied: string; copyKey: string; onCopy: (code: string) => void }) {
  const { text } = useI18n()
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-[hsl(var(--pix-ink))] text-white dark:bg-black/35">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-2 text-sm">
        <span className="font-semibold">{title}</span>
        <Button type="button" size="sm" variant="secondary" onClick={() => onCopy(code)}>{copied === copyKey ? <Check /> : <Clipboard />}{copied === copyKey ? text('已复制', 'Copied') : text('复制', 'Copy')}</Button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-6"><code>{code}</code></pre>
    </div>
  )
}
