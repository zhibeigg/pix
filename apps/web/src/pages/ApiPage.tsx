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
  'characters:read',
  'characters:write',
]

const SCOPE_LABELS: Record<string, { zh: string; en: string }> = {
  'me:read': { zh: '读取账号', en: 'Read account' },
  'balance:read': { zh: '读取点数', en: 'Read credits' },
  'models:read': { zh: '读取模型', en: 'Read models' },
  'uploads:create': { zh: '上传图片', en: 'Upload images' },
  'jobs:create': { zh: '创建任务', en: 'Create jobs' },
  'jobs:read': { zh: '读取任务', en: 'Read jobs' },
  'files:read': { zh: '下载结果', en: 'Download files' },
  'characters:read': { zh: '读取角色库', en: 'Read characters' },
  'characters:write': { zh: '写入角色库', en: 'Write characters' },
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
  const authCurl = useMemo(() => text(String.raw`# 先把 API 页面创建出的令牌保存到环境变量
export PIX_API_KEY="pix_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export PIX_API_BASE="${baseUrl}"

# 所有外部接口都使用 Bearer 认证
curl "$PIX_API_BASE/me" \
  -H "Authorization: Bearer $PIX_API_KEY"`, String.raw`# Save the token created on this API page to environment variables first
export PIX_API_KEY="pix_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export PIX_API_BASE="${baseUrl}"

# All external endpoints use Bearer authentication
curl "$PIX_API_BASE/me" \
  -H "Authorization: Bearer $PIX_API_KEY"`), [baseUrl, text])
  const inspectCurl = useMemo(() => text(String.raw`# 查询账号、余额和可用模型
curl "$PIX_API_BASE/me" \
  -H "Authorization: Bearer $PIX_API_KEY"

curl "$PIX_API_BASE/balance" \
  -H "Authorization: Bearer $PIX_API_KEY"
# balance 会返回永久点数 available_credits、当日临时额度 daily_quota_balance、总可用 available_total

curl "$PIX_API_BASE/models" \
  -H "Authorization: Bearer $PIX_API_KEY"

# models 响应包含 limits，可在客户端表单校验前读取：
# limits.asset_subject_max_chars / asset_extra_prompt_max_chars
# limits.sprite_subject_max_chars / sprite_row_prompt_max_chars
# limits.raw_image_prompt_max_chars`, String.raw`# Query account, balance and available models
curl "$PIX_API_BASE/me" \
  -H "Authorization: Bearer $PIX_API_KEY"

curl "$PIX_API_BASE/balance" \
  -H "Authorization: Bearer $PIX_API_KEY"
# balance returns permanent available_credits, today's daily_quota_balance, and available_total

curl "$PIX_API_BASE/models" \
  -H "Authorization: Bearer $PIX_API_KEY"

# The models response includes limits you can read before client-side form validation:
# limits.asset_subject_max_chars / asset_extra_prompt_max_chars
# limits.sprite_subject_max_chars / sprite_row_prompt_max_chars
# limits.raw_image_prompt_max_chars`), [text])
  const uploadCurl = useMemo(() => text(String.raw`# 上传参考图 / 本地输入图，返回的 path 可作为后续 input_image_path
curl -X POST "$PIX_API_BASE/uploads/images" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -F "file=@reference.png"

# 返回示例
# { "path": ".../uploads/xxx.png", "url": "/files/...", "filename": "reference.png" }`, String.raw`# Upload a reference / local input image; the returned path can be used as input_image_path later
curl -X POST "$PIX_API_BASE/uploads/images" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -F "file=@reference.png"

# Example response
# { "path": ".../uploads/xxx.png", "url": "/files/...", "filename": "reference.png" }`), [text])
  const characterCurl = useMemo(() => text(String.raw`# 角色库：读取自动保存的角色。只有“素材直出 → 角色”(asset_kind=character) 的成功任务能成为角色
curl "$PIX_API_BASE/characters" \
  -H "Authorization: Bearer $PIX_API_KEY"

# 可选：从已完成的角色素材任务补建/重建角色记录；普通上传图或非角色任务会返回 409
curl -X POST "$PIX_API_BASE/characters/jobs/123" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "name": "蓝袍骑士", "image_kind": "pixelized" }'

# 序列帧任务可把角色响应中的 image_path 写入 sprite.reference_image_path。`, String.raw`# Character library: read auto-saved characters. Only successful "asset → character" (asset_kind=character) jobs become characters
curl "$PIX_API_BASE/characters" \
  -H "Authorization: Bearer $PIX_API_KEY"

# Optional: backfill/rebuild a character record from a finished character asset job; plain uploads or non-character jobs return 409
curl -X POST "$PIX_API_BASE/characters/jobs/123" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Blue Cloak Knight", "image_kind": "pixelized" }'

# Sprite jobs can put the image_path from a character response into sprite.reference_image_path.`), [text])
  const assetCurl = useMemo(() => text(String.raw`# 创建素材直出任务。Idempotency-Key 可选；相同 key 重试会复用同一任务
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
    "style_profile": {
      "project_name": "水晶地牢",
      "palette": "青色、紫罗兰、深海军蓝",
      "line_style": "细亮描边",
      "avoid_elements": "现代枪械、水印、文字"
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

# 角色示例：把 asset 改为
# { "name": "蓝袍骑士", "asset_kind": "character", "subject_kind": "single_character", "character_views": "three_view" }
# character_views 默认 three_view：一次生成正/侧/背横向三视图拼合图，画布自动横向 3 倍宽（pixelize.output_size 表示单个视图尺寸，成品宽度 = 单视图宽 × 3）；改为 "single" 则生成单张角色。
# 角色素材任务成功后会自动保存到角色库，可直接作为序列帧参考来源。

# 尺寸重试示例：在请求体加入以下字段，反复重新生成直到透明成品尺寸匹配 pixelize.output_size 或达到上限。
# 适用于主体类 asset（不含 tile_texture / dual_grid）；支持前端全部默认尺寸档位：16/24/32/48/64/96/128/256。
# {
#   "size_retry_enabled": true,
#   "size_retry_mode": "attempts",        // attempts=按最大次数 | credits=按最大点数预算
#   "size_retry_max_attempts": 5,          // attempts 模式：含首次，受 size_retry_max_attempts_limit 上限夹取
#   "size_retry_max_credits": 0            // credits 模式：最大点数预算，后端按单次 6 折单价折算成次数
# }
# 计费：每次尝试按标准价 6 折（与全局折扣取更优），按实际尝试次数结算；响应 outputs[].size_retry 返回实际尝试次数与是否命中。
# transition_style 可选 rounded（默认）/ hard / outline；pixelize.output_size 是单张瓦片尺寸，图集为其 4×4 排布。
# 输出读 JobOutput 的 dual_grid_atlas_path/url 与 dual_grid_preview_path/url。

# style_profile 可选：project_name / palette / line_style / lighting / view_rule / avoid_elements 会作为项目统一风格补充进入 prompt。
# 202 返回 JobResponse，记录 id 后轮询 /jobs/{id}`, String.raw`# Create an asset job. Idempotency-Key is optional; retrying with the same key reuses the same job
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-sword-001" \
  -d '{
    "job_type": "asset",
    "asset": {
      "name": "Blue magic sword",
      "asset_kind": "item_icon"
    },
    "style_profile": {
      "project_name": "Crystal Dungeon",
      "palette": "cyan, violet, deep navy",
      "line_style": "thin bright outline",
      "avoid_elements": "modern firearms, watermarks, text"
    },
    "pixelize": {
      "output_size": [32, 32],
      "colors": 16,
      "remove_bg": true
    },
    "image_model": "image2",
    "skip_vl": true
  }'

# Tile texture example: change asset to
# { "name": "Mossy flagstone path", "asset_kind": "tile_texture", "texture_kind": "path_floor" }
# and set pixelize.remove_bg to false. texture_kind options: auto / generic_texture / terrain_ground / path_floor / wall_surface / wood_planks / water_liquid / foliage_canopy / roof_tile / metal_panel / fabric_carpet.

# Dual-grid example: change asset to
# { "name": "Grass-dirt transition", "asset_kind": "dual_grid", "material_a": "grass", "material_b": "dirt", "transition_style": "rounded" }
# Produces 16 seamlessly tileable transition tiles as a 4×4 atlas + an application preview + meta (with bitmask→cell mapping) in one run.
# material_a is required; an empty material_b or "transparent" enables transparent mode. material_a_texture_kind / material_b_texture_kind reuse the texture_kind enum above (default auto).

# Character example: change asset to
# { "name": "Blue Cloak Knight", "asset_kind": "character", "subject_kind": "single_character", "character_views": "three_view" }
# character_views defaults to three_view: generates a front/side/back turnaround in one image and the canvas becomes 3x wider automatically (pixelize.output_size is the per-view size, final width = single view width x 3). Use "single" for a single-view character.
# Successful character asset jobs are saved to the character library automatically and can be used directly as sprite references.

# Size-retry example: add the fields below to keep regenerating until the transparent final output matches pixelize.output_size or a cap is hit.
# Applies to subject-style asset jobs (excluding tile_texture / dual_grid); supports every default frontend size preset: 16/24/32/48/64/96/128/256.
# {
#   "size_retry_enabled": true,
#   "size_retry_mode": "attempts",        // attempts=max attempt count | credits=max credit budget
#   "size_retry_max_attempts": 5,          // attempts mode: includes the first try, clamped by size_retry_max_attempts_limit
#   "size_retry_max_credits": 0            // credits mode: max credit budget; the backend converts it to attempts at 60% of the unit price
# }
# Billing: each attempt is charged at 60% of the standard price (or the global discount if better), settled by actual attempts; outputs[].size_retry in the response reports attempts made and whether the target was hit.
# transition_style options: rounded (default) / hard / outline; pixelize.output_size is the single-tile size, the atlas is its 4×4 layout.
# Read dual_grid_atlas_path/url and dual_grid_preview_path/url from JobOutput.

# style_profile is optional: project_name / palette / line_style / lighting / view_rule / avoid_elements are appended to the prompt as a consistent project style.
# 202 returns a JobResponse; record the id and poll /jobs/{id}`), [text])
  const assetBatchCurl = useMemo(() => text(String.raw`# 多张同参数素材直出：用 /jobs/batch 一次创建多个独立 asset 任务
# 每个子任务必须有自己的 client_request_id；每张会独立排队、扣点、进入作品库和素材包
curl -X POST "$PIX_API_BASE/jobs/batch" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "蓝色魔法剑抽卡 × 3",
    "mode": "asset_multi",
    "jobs": [
      {
        "job_type": "asset",
        "client_request_id": "sword-draw-001",
        "asset": { "name": "蓝色魔法剑", "asset_kind": "item_icon" },
        "pixelize": { "output_size": [32, 32], "colors": 16, "remove_bg": true },
        "image_model": "image2",
        "skip_vl": true
      },
      {
        "job_type": "asset",
        "client_request_id": "sword-draw-002",
        "asset": { "name": "蓝色魔法剑", "asset_kind": "item_icon" },
        "pixelize": { "output_size": [32, 32], "colors": 16, "remove_bg": true },
        "image_model": "image2",
        "skip_vl": true
      },
      {
        "job_type": "asset",
        "client_request_id": "sword-draw-003",
        "asset": { "name": "蓝色魔法剑", "asset_kind": "item_icon" },
        "pixelize": { "output_size": [32, 32], "colors": 16, "remove_bg": true },
        "image_model": "image2",
        "skip_vl": true
      }
    ]
  }'

# 202 返回 JobBatchCreateResponse：jobs[] 是独立任务，total_price_credits 是本批次冻结点数，batch_id 可用于站内素材包批次下载。`, String.raw`# Multi-output asset generation: create multiple independent asset jobs with one /jobs/batch request
# Each child job needs its own client_request_id; every output is queued, billed, saved to the gallery, and pack-downloadable independently
curl -X POST "$PIX_API_BASE/jobs/batch" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "Blue magic sword draws × 3",
    "mode": "asset_multi",
    "jobs": [
      {
        "job_type": "asset",
        "client_request_id": "sword-draw-001",
        "asset": { "name": "Blue magic sword", "asset_kind": "item_icon" },
        "pixelize": { "output_size": [32, 32], "colors": 16, "remove_bg": true },
        "image_model": "image2",
        "skip_vl": true
      },
      {
        "job_type": "asset",
        "client_request_id": "sword-draw-002",
        "asset": { "name": "Blue magic sword", "asset_kind": "item_icon" },
        "pixelize": { "output_size": [32, 32], "colors": 16, "remove_bg": true },
        "image_model": "image2",
        "skip_vl": true
      },
      {
        "job_type": "asset",
        "client_request_id": "sword-draw-003",
        "asset": { "name": "Blue magic sword", "asset_kind": "item_icon" },
        "pixelize": { "output_size": [32, 32], "colors": 16, "remove_bg": true },
        "image_model": "image2",
        "skip_vl": true
      }
    ]
  }'

# 202 returns JobBatchCreateResponse: jobs[] are independent jobs, total_price_credits is the reserved total, and batch_id can be used by in-app pack batch downloads.`), [text])
  const imageCurl = useMemo(() => text(String.raw`# 图生图 / 参考图重绘：先上传图片，再把返回 path 放到 input_image_path
# asset.asset_kind 可选 item_icon / ui_component / tile_texture / game_logo / dual_grid / character，决定按哪种素材规则重绘（默认 item_icon）
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
  }'`, String.raw`# Image-to-image / reference redraw: upload an image first, then put the returned path into input_image_path
# asset.asset_kind options: item_icon / ui_component / tile_texture / game_logo / dual_grid / character — decides which asset rules the redraw follows (default item_icon)
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-reference-redraw-001" \
  -d '{
    "job_type": "image_to_image",
    "prompt": "Redraw the reference into a 32x32 pixel-art game icon, transparent background, high-contrast outline",
    "input_image_path": "put the path returned by the upload endpoint here",
    "asset": { "asset_kind": "item_icon" },
    "pixelize": {
      "output_size": [32, 32],
      "colors": 16,
      "remove_bg": true
    },
    "image_model": "image2"
  }'`), [text])
  const bgRemoveCurl = useMemo(() => text(String.raw`# 本地去背景：不调用 AI；algorithm 可选 pixel_bg（像素）或 color_to_alpha（高清）
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

# 成功后通过 outputs/pixelized 下载透明 PNG。`, String.raw`# Local background removal: no AI call; algorithm options are pixel_bg (pixel art) or color_to_alpha (high-res)
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-bg-remove-001" \
  -d '{
    "job_type": "local_bg_remove",
    "input_image_path": "put the path returned by the upload endpoint here",
    "pixelize": {
      "remove_bg": true,
      "bg_removal_algorithm": "color_to_alpha"
    }
  }'

# After success, download the transparent PNG via outputs/pixelized.`), [text])
  const spriteCurl = useMemo(() => text(String.raw`# 创建序列帧任务（默认 mosaic）：rows 表示动作行，cols 表示每行动画帧数
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-hero-walk-001" \
  -d '{
    "job_type": "sprite_sheet",
    "prompt": "一个蓝色斗篷骑士，侧视角像素风行走动画，动作连贯",
    "sprite": {
      "mode": "mosaic",
      "rows": 1,
      "cols": 8,
      "fps": 8,
      "row_prompts": ["walk cycle, left to right"]
    },
    "pixelize": {
      "output_size": [48, 48],
      "colors": 24,
      "remove_bg": false,
      "edge_style": "hard",
      "generated_preprocess_method": "perfect_pixel"
    },
    "image_model": "image2"
  }'

# 首尾帧视频补间：sprite.video_model 可选 Standard / Fast / Mini 三档并透传 Ark；点数按 4–15 秒价格表精确计算（Standard 47/57/66/75/84/94/103/112/121/131/140/149，Fast 40/48/55/62/70/77/85/92/100/107/114/122，Mini 29/34/38/43/47/52/57/61/66/70/75/80）；先按 Seedance 指南生成首/尾关键帧和结构化 motion prompt，再以 role=first_frame / last_frame 提交 Ark；Ark 视频秒数按 rows×cols×duration_ms 锁定；video_return_to_first_frame=true 会要求尾帧后回到首帧以便循环；video_first_frame_only=true 时只生成首帧关键图，再以 role=first_frame 创建 Ark 首帧图生视频任务并抽帧输出完整序列帧，仍按视频任务计费
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-hero-slash-video-001" \
  -d '{
    "job_type": "sprite_sheet",
    "prompt": "一个蓝色斗篷骑士，侧视角像素风，身份和配色稳定",
    "sprite": {
      "mode": "video_bridge",
      "rows": 1,
      "cols": 8,
      "fps": 8,
      "duration_ms": 125,
      "video_model": "doubao-seedance-2-0-260128",
      "video_action_prompt": "从站立蓄力到挥剑释放一道蓝色剑气",
      "video_return_to_first_frame": true,
      "video_first_frame_only": false
    },
    "pixelize": {
      "output_size": [48, 48],
      "colors": 24,
      "remove_bg": false,
      "edge_style": "hard",
      "generated_preprocess_method": "perfect_pixel"
    },
    "image_model": "image2"
  }'`, String.raw`# Create a sprite-sheet job (default mosaic): rows = action rows, cols = frames per row
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-hero-walk-001" \
  -d '{
    "job_type": "sprite_sheet",
    "prompt": "A blue-cloaked knight, side-view pixel-art walking animation, coherent motion",
    "sprite": {
      "mode": "mosaic",
      "rows": 1,
      "cols": 8,
      "fps": 8,
      "row_prompts": ["walk cycle, left to right"]
    },
    "pixelize": {
      "output_size": [48, 48],
      "colors": 24,
      "remove_bg": false,
      "edge_style": "hard",
      "generated_preprocess_method": "perfect_pixel"
    },
    "image_model": "image2"
  }'

# First/last-frame video bridge: sprite.video_model offers Standard / Fast / Mini tiers passed through to Ark; credits follow the exact 4–15s price table (Standard 47/57/66/75/84/94/103/112/121/131/140/149, Fast 40/48/55/62/70/77/85/92/100/107/114/122, Mini 29/34/38/43/47/52/57/61/66/70/75/80); first/last keyframes and a structured motion prompt are generated per the Seedance guide, then submitted to Ark as role=first_frame / last_frame; the Ark video duration is locked to rows×cols×duration_ms; video_return_to_first_frame=true asks the ending to return to the first frame for looping; video_first_frame_only=true generates only the first keyframe image, then creates an Ark first-frame-to-video task with role=first_frame and extracts the full sprite sequence, still billed as a video task
curl -X POST "$PIX_API_BASE/jobs" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-hero-slash-video-001" \
  -d '{
    "job_type": "sprite_sheet",
    "prompt": "A blue-cloaked knight, side-view pixel art, stable identity and palette",
    "sprite": {
      "mode": "video_bridge",
      "rows": 1,
      "cols": 8,
      "fps": 8,
      "duration_ms": 125,
      "video_model": "doubao-seedance-2-0-260128",
      "video_action_prompt": "From a standing charge-up to a sword slash releasing a blue arc of energy",
      "video_return_to_first_frame": true,
      "video_first_frame_only": false
    },
    "pixelize": {
      "output_size": [48, 48],
      "colors": 24,
      "remove_bg": false,
      "edge_style": "hard",
      "generated_preprocess_method": "perfect_pixel"
    },
    "image_model": "image2"
  }'`), [text])
  const pollCurl = useMemo(() => text(String.raw`# 轮询任务详情，status 为 succeeded 后再下载
curl "$PIX_API_BASE/jobs/123" \
  -H "Authorization: Bearer $PIX_API_KEY"

# 列表分页：status 可选 pending / running / waiting / succeeded / failed，before_id 用于翻页
curl "$PIX_API_BASE/jobs?status=succeeded&limit=20" \
  -H "Authorization: Bearer $PIX_API_KEY"`, String.raw`# Poll job details; download only after status is succeeded
curl "$PIX_API_BASE/jobs/123" \
  -H "Authorization: Bearer $PIX_API_KEY"

# List pagination: status options are pending / running / waiting / succeeded / failed; use before_id to page
curl "$PIX_API_BASE/jobs?status=succeeded&limit=20" \
  -H "Authorization: Bearer $PIX_API_KEY"`), [text])
  const downloadCurl = useMemo(() => text(String.raw`# 单图任务常用输出：source / pixelized / preview
curl -L "$PIX_API_BASE/jobs/123/outputs/pixelized" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o pixelized.png

# 序列帧输出：sprite-sheet / sprite-mosaic / sprite-grid
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-sheet" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite-sheet.png

# 序列帧动画 GIF（按当前帧实时合成，无需生成时开启 gif_export）
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-gif" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite.gif

# 多行动作序列帧可打包下载每行动作图
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-actions.zip" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite-actions.zip`, String.raw`# Common single-image outputs: source / pixelized / preview
curl -L "$PIX_API_BASE/jobs/123/outputs/pixelized" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o pixelized.png

# Sprite outputs: sprite-sheet / sprite-mosaic / sprite-grid
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-sheet" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite-sheet.png

# Sprite animation GIF (composed on demand from current frames; no gif_export needed)
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-gif" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite.gif

# Multi-row action sprite sheets can bundle per-row action images
curl -L "$PIX_API_BASE/jobs/123/outputs/sprite-actions.zip" \
  -H "Authorization: Bearer $PIX_API_KEY" \
  -o sprite-actions.zip`), [text])

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
          <Badge variant="outline" className="min-w-0 max-w-full shrink whitespace-normal break-all">{text('Base URL', 'Base URL')}: {baseUrl}</Badge>
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
          <ApiDocNote title={text('输出类型', 'Outputs')} body={text('单图下载 source / pixelized / preview；序列帧下载 sprite-sheet / sprite-mosaic / sprite-grid / sprite-gif 或 sprite-actions.zip。', 'Single-image outputs: source / pixelized / preview; sprite outputs: sprite-sheet / sprite-mosaic / sprite-grid / sprite-gif or sprite-actions.zip.')} />
          <ApiDocNote title={text('权限 Scope', 'Scopes')} body={text('按最小权限创建 Key：jobs:create 创建任务，jobs:read 查询任务，files:read 下载结果，uploads:create 上传图片，characters:read/write 读写角色库。', 'Use least-privilege keys: jobs:create, jobs:read, files:read, uploads:create, and characters:read/write as needed.')} />
        </div>
        <CodeBlock title={text('1. 保存令牌并测试认证', '1. Save token and test auth')} description={text('把 API 页面创建出的令牌保存成环境变量，后续示例可直接复制运行。', 'Store the generated API token as an environment variable; later examples can be copied as-is.')} code={authCurl} copied={copied} onCopy={(code) => void copy(code, 'auth')} copyKey="auth" />
        <CodeBlock title={text('2. 查询账号、余额和模型', '2. Inspect account, credits, and models')} description={text('用于确认 Key 权限、账号余额和当前可选的生图模型。', 'Use this to verify key scopes, credit balance, and available generation models.')} code={inspectCurl} copied={copied} onCopy={(code) => void copy(code, 'inspect')} copyKey="inspect" />
        <CodeBlock title={text('3. 上传参考图（可选）', '3. Upload a reference image (optional)')} description={text('上传返回的 path 可以写入 input_image_path；角色库只接收“素材直出 → 角色”的成功任务产物。', 'The returned path can be used as input_image_path; the character library only accepts successful asset → character job outputs.')} code={uploadCurl} copied={copied} onCopy={(code) => void copy(code, 'upload')} copyKey="upload" />
        <CodeBlock title={text('4. 角色库读写', '4. Read/write character library')} description={text('角色库需要 characters:read / characters:write；只有像素直出的角色类型会进入角色库，角色 image_path 可写入序列帧 sprite.reference_image_path。', 'Character library calls require characters:read / characters:write; only pixel-direct character jobs enter the library, and their image_path can be used as sprite.reference_image_path for sprite jobs.')} code={characterCurl} copied={copied} onCopy={(code) => void copy(code, 'characters')} copyKey="characters" />
        <CodeBlock title={text('5. 创建素材直出任务', '5. Create an asset job')} description={text('适合游戏图标、道具、UI 小物件等单图素材；创建成功返回 202 和任务 id。', 'Best for icons, props, UI items, and other single-image assets; returns 202 with a job id.')} code={assetCurl} copied={copied} onCopy={(code) => void copy(code, 'asset')} copyKey="asset" />
        <CodeBlock title={text('6. 多张同参数素材直出', '6. Multi-output asset generation')} description={text('用 /jobs/batch 一次创建多个同参数 asset 任务；每张独立扣点、排队、入作品库。', 'Use /jobs/batch to create multiple same-parameter asset jobs; every output is billed, queued, and saved independently.')} code={assetBatchCurl} copied={copied} onCopy={(code) => void copy(code, 'asset-batch')} copyKey="asset-batch" />
        <CodeBlock title={text('7. 创建图生图 / 参考图重绘任务', '7. Create an image-to-image job')} description={text('先上传图片，再把上传结果 path 放到 input_image_path。', 'Upload an image first, then pass the returned path as input_image_path.')} code={imageCurl} copied={copied} onCopy={(code) => void copy(code, 'image')} copyKey="image" />
        <CodeBlock title={text('8. 创建本地去背景任务', '8. Create a local background-removal job')} description={text('先上传图片，再选择 pixel_bg（像素）或 color_to_alpha（高清）算法；不调用 AI。', 'Upload an image first, then choose pixel_bg (pixel) or color_to_alpha (HD); no AI call is made.')} code={bgRemoveCurl} copied={copied} onCopy={(code) => void copy(code, 'bg-remove')} copyKey="bg-remove" />
        <CodeBlock title={text('9. 创建序列帧任务', '9. Create a sprite-sheet job')} description={text('用于角色行走、攻击、待机等动画；rows × cols 决定动作行和帧数，可传入角色库 image_path 作为 reference_image_path。', 'Use this for walk, attack, idle, and other animations; rows × cols controls action rows and frame count. You can pass a character image_path as reference_image_path.')} code={spriteCurl} copied={copied} onCopy={(code) => void copy(code, 'sprite')} copyKey="sprite" />
        <CodeBlock title={text('10. 轮询任务和分页列表', '10. Poll jobs and list pages')} description={text('任务状态通常为 pending / running / waiting / succeeded / failed；video_bridge 在 Ark 视频生成期间会显示 waiting，可重试的 Ark 上游/网络/超时错误也会保持 waiting 后续重试。', 'Job status is usually pending / running / waiting / succeeded / failed; video_bridge shows waiting while Ark renders, and retryable Ark upstream/network/timeout errors stay waiting for later retries.')} code={pollCurl} copied={copied} onCopy={(code) => void copy(code, 'poll')} copyKey="poll" />
        <CodeBlock title={text('11. 下载输出文件', '11. Download output files')} description={text('下载接口需要 files:read 权限；文件不存在或任务未完成时会返回 404 / 409。', 'Download endpoints require files:read; unavailable files or unfinished jobs return 404 / 409.')} code={downloadCurl} copied={copied} onCopy={(code) => void copy(code, 'download')} copyKey="download" />
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
    <div className="overflow-hidden rounded-lg border border-border bg-card shadow-sm dark:border-white/10">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border bg-secondary px-4 py-2.5 text-sm dark:border-white/10 dark:bg-white/5">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="mt-1 hidden shrink-0 gap-1.5 sm:flex" aria-hidden="true">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          </span>
          <div className="min-w-0">
            <span className="font-semibold text-foreground">{title}</span>
            {description && <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>}
          </div>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={() => onCopy(code)}>{copied === copyKey ? <Check /> : <Clipboard />}{copied === copyKey ? text('已复制', 'Copied') : text('复制', 'Copy')}</Button>
      </div>
      <pre className="overflow-x-auto bg-[hsl(222_16%_8%)] p-4 font-mono text-xs leading-6 text-[hsl(220_16%_86%)]"><code>{code}</code></pre>
    </div>
  )
}
