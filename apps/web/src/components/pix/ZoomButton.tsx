import { ScanSearch } from 'lucide-react'
import { useI18n } from '../../i18n'

/**
 * 预览悬停放大按钮。默认隐藏，容器 hover / focus-within 时淡入。
 * 点击时阻止冒泡，避免触发画廊卡片选中等父级交互。
 */
export function ZoomButton({ onClick }: { onClick: () => void }) {
  const { t } = useI18n()
  return (
    <button
      type="button"
      title={t('lightbox.zoom')}
      aria-label={t('lightbox.zoom')}
      onClick={(event) => {
        event.stopPropagation()
        event.preventDefault()
        onClick()
      }}
      className="absolute right-2 top-2 z-10 grid h-8 w-8 place-items-center rounded-md bg-black/45 text-white opacity-0 backdrop-blur-sm transition duration-150 hover:bg-black/65 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 group-hover:opacity-100 pointer-coarse:opacity-100"
    >
      <ScanSearch className="h-4 w-4" />
    </button>
  )
}
