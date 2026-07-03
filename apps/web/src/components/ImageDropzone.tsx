import { useId, useRef, useState, type DragEvent, type ReactNode } from 'react'
import { Upload } from 'lucide-react'
import { useI18n } from '../i18n'
import { cn } from '../lib/utils'
import { ACCEPTED_IMAGE_ACCEPT, formatBytes, imageValidationMessage, validateImageFile } from '../lib/upload'

type Props = {
  /** 单张上传大小上限（字节）。 */
  maxBytes: number
  /** 校验通过后回调有效文件；multiple 时可能多次触发所有文件一起回调。 */
  onFiles: (files: File[]) => void
  /** 校验失败回调（已翻译好的提示文本）。 */
  onError?: (message: string) => void
  /** 是否允许多选。默认单选。 */
  multiple?: boolean
  /** 是否禁用（如上传中）。 */
  disabled?: boolean
  /** 主标题文本；不传使用默认。 */
  label?: ReactNode
  /** 无障碍标签。 */
  ariaLabel?: string
  className?: string
}

/**
 * 可复用的图片拖拽 / 点击上传区。
 * - 点击或键盘 Enter/Space 打开文件选择；拖拽图片到区域内放置。
 * - 内置类型与大小前置校验：非法文件本地拦截并通过 onError 回调提示，不触发 onFiles。
 * - 仅负责选取 + 校验，实际上传请求由父组件在 onFiles 中处理。
 */
export function ImageDropzone({ maxBytes, onFiles, onError, multiple = false, disabled = false, label, ariaLabel, className }: Props) {
  const { text, isEnglish } = useI18n()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputId = useId()

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    const incoming = multiple ? Array.from(fileList) : [fileList[0]]
    const valid: File[] = []
    for (const file of incoming) {
      const result = validateImageFile(file, maxBytes)
      if (result.ok) {
        valid.push(file)
      } else {
        onError?.(imageValidationMessage(result, isEnglish))
        if (!multiple) return
      }
    }
    if (valid.length > 0) onFiles(valid)
  }

  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragOver(false)
    if (disabled) return
    handleFiles(event.dataTransfer.files)
  }

  function onDragOver(event: DragEvent<HTMLElement>) {
    if (disabled) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    if (!dragOver) setDragOver(true)
  }

  function openPicker() {
    if (disabled) return
    inputRef.current?.click()
  }

  const limitHint = text(
    `点击或拖拽图片到此处 · PNG/JPG/WebP · 最大 ${formatBytes(maxBytes)}`,
    `Click or drag an image here · PNG/JPG/WebP · max ${formatBytes(maxBytes)}`,
  )

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={ariaLabel || text('上传图片', 'Upload image')}
      aria-disabled={disabled}
      onClick={openPicker}
      onKeyDown={(event) => {
        if (disabled) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          openPicker()
        }
      }}
      onDragOver={onDragOver}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        dragOver ? 'border-primary bg-primary/10' : 'border-border bg-muted/30 hover:border-primary/50 hover:bg-primary/5',
        disabled && 'pointer-events-none opacity-60',
        'dark:border-[hsl(var(--pix-dark-hairline))]',
        className,
      )}
    >
      <span className="grid h-10 w-10 place-items-center rounded-lg border border-border bg-card/80 text-primary dark:border-[hsl(var(--pix-dark-hairline))]">
        <Upload className="h-5 w-5" />
      </span>
      <span className="text-sm font-medium text-foreground">{label ?? text('上传图片', 'Upload image')}</span>
      <span className="text-xs text-muted-foreground">{limitHint}</span>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={ACCEPTED_IMAGE_ACCEPT}
        multiple={multiple}
        className="hidden"
        aria-hidden="true"
        tabIndex={-1}
        disabled={disabled}
        onChange={(event) => {
          handleFiles(event.currentTarget.files)
          // 允许再次选择相同文件
          event.currentTarget.value = ''
        }}
      />
    </div>
  )
}
