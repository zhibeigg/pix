import type { PixLanguage } from './theme'
import { localText } from './i18n'

export function jobTypeLabel(type: string, language: PixLanguage = 'zh-CN') {
  const labels: Record<string, { zh: string; en: string }> = {
    asset: { zh: '素材直出', en: 'Asset output' },
    text_to_image: { zh: '文字生成', en: 'Text to image' },
    image_to_image: { zh: '参考图微调', en: 'Image to image' },
    sprite_sheet: { zh: '动画精灵表', en: 'Sprite sheet' },
    local_pixelize: { zh: '本地像素化', en: 'Local pixelize' },
    repixelize: { zh: '重新像素化', en: 'Repixelize' },
  }
  const label = labels[type]
  return label ? localText(language, label.zh, label.en) : type
}

export const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'primary',
  succeeded: 'success',
  failed: 'error',
  cancelled: 'default',
}

export function jobStatusLabel(status: string, language: PixLanguage = 'zh-CN') {
  const labels: Record<string, { zh: string; en: string }> = {
    pending: { zh: '排队中', en: 'Queued' },
    running: { zh: '生产中', en: 'Running' },
    succeeded: { zh: '已完成', en: 'Completed' },
    failed: { zh: '失败', en: 'Failed' },
    cancelled: { zh: '已取消', en: 'Cancelled' },
  }
  const label = labels[status]
  return label ? localText(language, label.zh, label.en) : status
}
