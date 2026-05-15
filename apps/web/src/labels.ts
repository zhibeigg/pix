export function jobTypeLabel(type: string) {
  const labels: Record<string, string> = {
    asset: '素材直出',
    text_to_image: '文字生成',
    image_to_image: '参考图微调',
    sprite_sheet: '动画精灵表',
    local_pixelize: '本地像素化',
    repixelize: '重新像素化',
  }
  return labels[type] ?? type
}

export function jobStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '排队中',
    running: '生产中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status] ?? status
}
