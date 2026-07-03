// 上传图片的前端前置校验与展示工具。
// 后端 storage 层仍是最终防线（类型 + 大小 + 空文件），这里只是提前拦截、给出更友好的提示，
// 避免大文件白白上传占用带宽。

export const ACCEPTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'] as const
export const ACCEPTED_IMAGE_ACCEPT = 'image/png,image/jpeg,image/webp'
const ACCEPTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp']

export type ImageValidationError = 'type' | 'empty' | 'too_large'

export type ImageValidationResult =
  | { ok: true }
  | { ok: false; reason: ImageValidationError; maxBytes?: number }

/** 校验单个文件是否为受支持的图片且不超过大小上限。 */
export function validateImageFile(file: File, maxBytes: number): ImageValidationResult {
  const name = (file.name || '').toLowerCase()
  const typeOk =
    (file.type && (ACCEPTED_IMAGE_TYPES as readonly string[]).includes(file.type)) ||
    ACCEPTED_IMAGE_EXTENSIONS.some((ext) => name.endsWith(ext))
  if (!typeOk) return { ok: false, reason: 'type' }
  if (file.size === 0) return { ok: false, reason: 'empty' }
  if (maxBytes > 0 && file.size > maxBytes) return { ok: false, reason: 'too_large', maxBytes }
  return { ok: true }
}

/** 人类可读的字节大小，如 900 KB / 10 MB。 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const exponent = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  const value = bytes / 1024 ** exponent
  const rounded = value >= 10 || exponent === 0 ? Math.round(value) : Math.round(value * 10) / 10
  return `${rounded} ${units[exponent]}`
}

/** 把校验失败原因翻译成中英文提示。 */
export function imageValidationMessage(
  result: Extract<ImageValidationResult, { ok: false }>,
  isEnglish: boolean,
): string {
  if (result.reason === 'type') {
    return isEnglish ? 'Only PNG / JPG / WebP images are supported.' : '仅支持 PNG / JPG / WebP 图片。'
  }
  if (result.reason === 'empty') {
    return isEnglish ? 'The selected file is empty.' : '所选文件为空。'
  }
  const limit = formatBytes(result.maxBytes ?? 0)
  return isEnglish
    ? `Image exceeds the ${limit} size limit. Please compress it and try again.`
    : `图片超过 ${limit} 大小限制，请压缩后再上传。`
}
