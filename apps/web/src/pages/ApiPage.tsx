import { useEffect, useMemo, useState } from 'react'
import { Check, Clipboard, Code2, KeyRound, RotateCw, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { api, API_BASE } from '../api'
import { useI18n } from '../i18n'
import type { ApiKeyItem } from '../types'
import { PageHeader } from '../components/PageHeader'
import { Alert } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'

const API_TOKEN_PREFIX = 'pix_live_'

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

function generateApiTokenCandidate() {
  const bytes = new Uint8Array(32)
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(bytes)
  } else {
    for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256)
  }
  return `${API_TOKEN_PREFIX}${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`
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
  const [tokenCandidate, setTokenCandidate] = useState(() => generateApiTokenCandidate())
  const [createdKey, setCreatedKey] = useState('')
  const [copied, setCopied] = useState('')
  const baseUrl = useMemo(() => externalBaseUrl(), [])
  const authCurl = useMemo(() => String.raw`# 先把 API 页面创建出的令牌保存到环境变量
export PIX_API_KEY="pix_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export PIX_API_BASE="${baseUrl}"

# 所有外部接口都使用 Bearer 认证
curl "$PIX_API_BASE/me" \
  -H "Authorization: Bearer $PIX_API_KEY"`, [baseUrl])
  const inspectCurl = useMemo(() => String.raw`# 查询账号、余额和可用模型
curl "$PIX_API_BASE/me" \
  -H "Authorization: Bearer $PIX_API_KEY"

curl "$PIX_API_BASE/balance" \
  -H "Authorization: Bearer $PIX_API_KEY"

curl "$PIX_API_BASE/models" \
  -H "Authorization: Bearer $PIX_API_KEY"`, [])
  const uploadCurl = useMemo(() => String.raw`# 上传参考图 / 本地输入图，返回的 path 可作为后续 input_image_path
curl -X POST "$PIX_API_BASE/uploads/images" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -F "file=@reference.png"

# 返回示例
# { "path": ".../uploads/xxx.png", "url": "/files/...", "filename": "reference.png" }`, [])
  const assetCurl = useMemo(() => String.raw`# 创建素材直出任务。Idempotency-Key 可选；相同 key 重试会复用同一任务
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-sword-001" \
  -d '{
    "job_type": "asset",
    "asset": {
      "name": "蓝色魔法剑",
      "asset_kind": "item_icon"
    },
    "pixelize": {
      "output_size": [32, 32],
      "colors": 16,
      "remove_bg": true
    },
    "image_model": "image2",
    "skip_vl": true
  }'

# 平铺纹理示例：把 asset 改为
# { "name": "苔藓石板路面", "asset_kind": "tile_texture", "texture_kind": "path_floor" }
# 并把 pixelize.remove_bg 设为 false。texture_kind 可选 auto / generic_texture / terrain_ground / path_floor / wall_surface / wood_planks / water_liquid / foliage_canopy / roof_tile / metal_panel / fabric_carpet。

# 双瓦片示例：把 asset 改为
# { "name": "草地泥土过渡", "asset_kind": "dual_grid", "material_a": "草地", "material_b": "泥土", "transition_style": "rounded" }
# 一次产出 16 张可无缝拼接的 4×4 过渡瓦片图集 + 应用预览 + meta（含 bitmask→cell 映射）。
# material_a 必填；material_b 空串或 "transparent" 即透明模式。material_a_texture_kind / material_b_texture_kind 复用上面的 texture_kind 枚举（默认 auto）。
# transition_style 可选 rounded（默认）/ hard / outline；pixelize.output_size 是单张瓦片尺寸，图集为其 4×4 排布。
# 输出读 JobOutput 的 dual_grid_atlas_path/url 与 dual_grid_preview_path/url。

# 202 返回 JobResponse，记录 id 后轮询 /jobs/{id}`, [])
  const imageCurl = useMemo(() => String.raw`# 图生图 / 参考图重绘：先上传图片，再把返回 path 放到 input_image_path
# asset.asset_kind 可选 item_icon / ui_component / tile_texture / game_logo / dual_grid，决定按哪种素材规则重绘（默认 item_icon）
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-reference-redraw-001" \
  -d '{
    "job_type": "image_to_image",
    "prompt": "把参考图重绘成 32x32 像素风游戏图标，透明背景，高对比轮廓",
    "input_image_path": "把上传接口返回的 path 填在这里",
    "asset": { "asset_kind": "item_icon" },
    "pixelize": {
      "output_size": [32, 32],
      "colors": 16,
      "remove_bg": true
    },
    "image_model": "image2"
  }'`, [])
  const bgRemoveCurl = useMemo(() => String.raw`# 本地去背景：不调用 AI；algorithm 可选 pixel_bg（像素）或 color_to_alpha（高清）
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-bg-remove-001" \
  -d '{
    "job_type": "local_bg_remove",
    "input_image_path": "把上传接口返回的 path 填在这里",
    "pixelize": {
      "remove_bg": true,
      "bg_removal_algorithm": "color_to_alpha"
    }
  }'

# 成功后通过 outputs/pixelized 下载透明 PNG。`, [])
  const spriteCurl = useMemo(() => String.raw`# 创建序列帧任务：rows 表示动作行，cols 表示每行动画帧数
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-hero-walk-001" \
  -d '{
    "job_type": "sprite_sheet",
    "prompt": "一个蓝色斗篷骑士，侧视角像素风行走动画，动作连贯",
    "sprite": {
      "rows": 1,
      "cols": 8,
      "fps": 8,
      "row_prompts": ["walk cycle, left to right"]
    },
    "pixelize": {
      "output_size": [48, 48],
      "colors": 24,
      "remove_bg": true
    },
    "image_model": "image2"
  }'`, [])
  const pollCurl = useMemo(() => String.raw`# 轮询任务详情，status 为 succeeded 后再下载
curl "$PIX_API_BASE/jobs/123" \
  -H "Authorization: Bearer $PIX_API_KEY"

# 列表分页：status 可选 pending / running / succeeded / failed，before_id 用于翻页
curl "$PIX_API_BASE/jobs?status=succeeded&limit=20" \
  -H "Authorization: Bearer $PIX_API_KEY"`, [])
  const downloadCurl = useMemo(() => String.raw`# 单图任务常用输出：source / pixelized / preview
curl -L "$PIX_API_BASE/jobs/123/outputs/pixelized" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o pixelized.png

# 序列帧输出：sprite-sheet / sprite-mosaic / sprite-grid
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-sheet" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite-sheet.png

# 多行动作序列帧可打包下载每行动作图
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-actions.zip" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite-actions.zip`, [])

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
        custom_key: tokenCandidate.trim(),
      }
      const result = await api.createApiKey(token, payload)
      setCreatedKey(result.key)
      setName('')
      setExpiresAt('')
      setTokenCandidate(generateApiTokenCandidate())
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

        <div className="grid gap-5 rounded-lg border border-border bg-muted/30 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="grid gap-1.5 text-sm font-medium">
              {text('名称', 'Name')}
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder={text('例如：Unity 插件 / Bot', 'e.g. Unity plugin / Bot')} className="h-10 rounded-md border border-input bg-background px-3 text-sm transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
            </label>
            <label className="grid gap-1.5 text-sm font-medium">
              {text('过期时间（可选）', 'Expires at (optional)')}
              <input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} className="h-10 rounded-md border border-input bg-background px-3 text-sm transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
            </label>
          </div>

          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{text('权限', 'Scopes')}</span>
              <span className="text-xs font-medium text-muted-foreground">{text(`已选 ${selectedScopes.length}/${API_SCOPES.length}`, `${selectedScopes.length}/${API_SCOPES.length} selected`)}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {API_SCOPES.map((scope) => {
                const label = SCOPE_LABELS[scope]
                const active = selectedScopes.includes(scope)
                return (
                  <button key={scope} type="button" onClick={() => toggleScope(scope)} aria-pressed={active} className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-semibold transition-colors ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground'}`}>
                    {active && <Check className="h-3.5 w-3.5" />}
                    {language === 'en' ? label.en : label.zh}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="grid gap-2 rounded-lg border border-border bg-background p-3">
            <span className="flex items-center gap-1.5 text-sm font-medium"><Sparkles className="h-3.5 w-3.5 text-primary" />{text('令牌生成', 'Token generation')}</span>
            <div className="flex flex-wrap items-center gap-2">
              <input value={tokenCandidate} readOnly className="h-9 min-w-0 flex-1 basis-64 rounded-md border border-input bg-muted/50 px-2.5 font-mono text-[11px]" />
              <Button type="button" size="sm" variant="outline" onClick={() => setTokenCandidate(generateApiTokenCandidate())}><Sparkles />{text('重新生成', 'Regenerate')}</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => void copy(tokenCandidate, 'candidate-key')}>{copied === 'candidate-key' ? <Check /> : <Clipboard />}{copied === 'candidate-key' ? text('已复制', 'Copied') : text('复制', 'Copy')}</Button>
            </div>
            <span className="text-xs text-muted-foreground">{text('类似 sub2api 的 32 字节随机令牌；点击创建后才会生效，服务端仅保存哈希。', 'A sub2api-style 32-byte random token; it becomes active only after creation and is stored as a hash.')}</span>
          </div>

          <div className="flex justify-end border-t border-border pt-4">
            <Button className="w-full sm:w-auto" onClick={() => void createKey()} disabled={saving}><ShieldCheck />{saving ? text('创建中…', 'Creating…') : text('创建令牌', 'Create token')}</Button>
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
          <h2 className="flex items-center gap-2 text-xl font-semibold"><Code2 className="h-5 w-5 text-primary" />{text('API 调用文档', 'API reference')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{text('按下面顺序接入：保存令牌 → 检查账号和模型 → 上传参考图（可选）→ 创建任务 → 轮询任务 → 下载结果。', 'Integrate in this order: save token → inspect account/models → upload references (optional) → create jobs → poll jobs → download outputs.')}</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <ApiDocNote title={text('认证', 'Auth')} body={text('所有 /external/v1 接口都支持 Authorization: Bearer <API Key>，也兼容 X-Pix-Api-Key 请求头。', 'All /external/v1 endpoints accept Authorization: Bearer <API Key>, and X-Pix-Api-Key is also supported.')} />
          <ApiDocNote title={text('幂等', 'Idempotency')} body={text('创建任务建议传 Idempotency-Key；同一账号同一 key 重试会返回同一个任务，避免重复扣点。', 'Pass Idempotency-Key when creating jobs; retries with the same key reuse the same job and avoid duplicate charges.')} />
          <ApiDocNote title={text('输出类型', 'Outputs')} body={text('单图下载 source / pixelized / preview；序列帧下载 sprite-sheet / sprite-mosaic / sprite-grid 或 sprite-actions.zip。', 'Single-image outputs: source / pixelized / preview; sprite outputs: sprite-sheet / sprite-mosaic / sprite-grid or sprite-actions.zip.')} />
          <ApiDocNote title={text('权限 Scope', 'Scopes')} body={text('按最小权限创建 Key：jobs:create 创建任务，jobs:read 查询任务，files:read 下载结果，uploads:create 上传图片。', 'Use least-privilege keys: jobs:create, jobs:read, files:read, and uploads:create as needed.')} />
        </div>
        <CodeBlock title={text('1. 保存令牌并测试认证', '1. Save token and test auth')} description={text('把 API 页面创建出的令牌保存成环境变量，后续示例可直接复制运行。', 'Store the generated API token as an environment variable; later examples can be copied as-is.')} code={authCurl} copied={copied} onCopy={(code) => void copy(code, 'auth')} copyKey="auth" />
        <CodeBlock title={text('2. 查询账号、余额和模型', '2. Inspect account, credits, and models')} description={text('用于确认 Key 权限、账号余额和当前可选的生图模型。', 'Use this to verify key scopes, credit balance, and available generation models.')} code={inspectCurl} copied={copied} onCopy={(code) => void copy(code, 'inspect')} copyKey="inspect" />
        <CodeBlock title={text('3. 上传参考图（可选）', '3. Upload a reference image (optional)')} description={text('上传返回的 path 可以写入 input_image_path，用于图生图或角色参考图。', 'The returned path can be used as input_image_path for image-to-image jobs or character references.')} code={uploadCurl} copied={copied} onCopy={(code) => void copy(code, 'upload')} copyKey="upload" />
        <CodeBlock title={text('4. 创建素材直出任务', '4. Create an asset job')} description={text('适合游戏图标、道具、UI 小物件等单图素材；创建成功返回 202 和任务 id。', 'Best for icons, props, UI items, and other single-image assets; returns 202 with a job id.')} code={assetCurl} copied={copied} onCopy={(code) => void copy(code, 'asset')} copyKey="asset" />
        <CodeBlock title={text('5. 创建图生图 / 参考图重绘任务', '5. Create an image-to-image job')} description={text('先上传图片，再把上传结果 path 放到 input_image_path。', 'Upload an image first, then pass the returned path as input_image_path.')} code={imageCurl} copied={copied} onCopy={(code) => void copy(code, 'image')} copyKey="image" />
        <CodeBlock title={text('6. 创建本地去背景任务', '6. Create a local background-removal job')} description={text('先上传图片，再选择 pixel_bg（像素）或 color_to_alpha（高清）算法；不调用 AI。', 'Upload an image first, then choose pixel_bg (pixel) or color_to_alpha (HD); no AI call is made.')} code={bgRemoveCurl} copied={copied} onCopy={(code) => void copy(code, 'bg-remove')} copyKey="bg-remove" />
        <CodeBlock title={text('7. 创建序列帧任务', '7. Create a sprite-sheet job')} description={text('用于角色行走、攻击、待机等动画；rows × cols 决定动作行和帧数。', 'Use this for walk, attack, idle, and other animations; rows × cols controls action rows and frame count.')} code={spriteCurl} copied={copied} onCopy={(code) => void copy(code, 'sprite')} copyKey="sprite" />
        <CodeBlock title={text('8. 轮询任务和分页列表', '8. Poll jobs and list pages')} description={text('任务状态通常为 pending / running / succeeded / failed；成功后再下载输出。', 'Job status is usually pending / running / succeeded / failed; download outputs after success.')} code={pollCurl} copied={copied} onCopy={(code) => void copy(code, 'poll')} copyKey="poll" />
        <CodeBlock title={text('9. 下载输出文件', '9. Download output files')} description={text('下载接口需要 files:read 权限；文件不存在或任务未完成时会返回 404 / 409。', 'Download endpoints require files:read; unavailable files or unfinished jobs return 404 / 409.')} code={downloadCurl} copied={copied} onCopy={(code) => void copy(code, 'download')} copyKey="download" />
      </section>
    </div>
  )
}

function ApiDocNote({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-sky))]/45 p-3 text-sm dark:border-white/10 dark:bg-white/6">
      <p className="font-semibold text-[hsl(var(--pix-ink))] dark:text-white">{title}</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground dark:text-white/62">{body}</p>
    </div>
  )
}

function CodeBlock({ title, description, code, copied, copyKey, onCopy }: { title: string; description?: string; code: string; copied: string; copyKey: string; onCopy: (code: string) => void }) {
  const { text } = useI18n()
  return (
    <div className="overflow-hidden rounded-lg border border-[hsl(var(--pix-paper-border))] bg-white text-[hsl(var(--pix-ink))] shadow-sm dark:border-white/10 dark:bg-black/35 dark:text-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[hsl(var(--pix-paper-border))] bg-[hsl(var(--pix-sky))]/55 px-4 py-2.5 text-sm dark:border-white/10 dark:bg-white/7">
        <div className="min-w-0">
          <span className="font-semibold">{title}</span>
          {description && <p className="mt-1 text-xs leading-5 text-muted-foreground dark:text-white/60">{description}</p>}
        </div>
        <Button type="button" size="sm" variant="outline" className="bg-white/80 dark:bg-white/10" onClick={() => onCopy(code)}>{copied === copyKey ? <Check /> : <Clipboard />}{copied === copyKey ? text('已复制', 'Copied') : text('复制', 'Copy')}</Button>
      </div>
      <pre className="overflow-x-auto bg-[hsl(var(--pix-paper))] p-4 text-xs leading-6 text-[hsl(var(--pix-charcoal))] dark:bg-black/25 dark:text-white/88"><code>{code}</code></pre>
    </div>
  )
}
