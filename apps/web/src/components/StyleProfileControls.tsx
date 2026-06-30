import type { StyleProfile } from '../types'
import { useI18n } from '../i18n'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Textarea } from './ui/textarea'
import { PixField } from './pix/PixField'

type StyleProfileKey = keyof StyleProfile

type FieldSpec = {
  key: StyleProfileKey
  maxLength: number
  zh: string
  en: string
  placeholderZh: string
  placeholderEn: string
  multiline?: boolean
}

const STYLE_FIELDS: FieldSpec[] = [
  { key: 'project_name', maxLength: 80, zh: '项目 / 世界观', en: 'Project / world', placeholderZh: '例如：水晶地牢、星尘纪元', placeholderEn: 'e.g. Crystal Dungeon, Starfall Age' },
  { key: 'palette', maxLength: 120, zh: '配色方案', en: 'Color palette', placeholderZh: '例如：青色、紫罗兰、深海军蓝', placeholderEn: 'e.g. cyan, violet, deep navy' },
  { key: 'line_style', maxLength: 120, zh: '线条风格', en: 'Line style', placeholderZh: '例如：细亮描边、粗黑轮廓、无描边', placeholderEn: 'e.g. thin bright outline, chunky dark outline' },
  { key: 'lighting', maxLength: 120, zh: '光照规则', en: 'Lighting rule', placeholderZh: '例如：柔和边缘光、无高光、顶部冷光', placeholderEn: 'e.g. soft rim light, no highlights, cool top light' },
  { key: 'view_rule', maxLength: 120, zh: '视角规则', en: 'View rule', placeholderZh: '例如：严格正面、俯视 3/4、侧视角色', placeholderEn: 'e.g. strict front-facing, top-down 3/4, side-view character' },
  { key: 'avoid_elements', maxLength: 200, zh: '避免元素', en: 'Avoid elements', placeholderZh: '例如：现代武器、文字、水印、写实材质', placeholderEn: 'e.g. modern weapons, text, watermark, realistic materials', multiline: true },
]

export function compactStyleProfile(value: StyleProfile | undefined | null): StyleProfile | undefined {
  if (!value) return undefined
  const entries = STYLE_FIELDS.flatMap(({ key }) => {
    const text = (value[key] ?? '').trim()
    return text ? [[key, text] as const] : []
  })
  return entries.length > 0 ? Object.fromEntries(entries) as StyleProfile : undefined
}

export function styleProfileRuleCount(value: StyleProfile | undefined | null): number {
  return Object.keys(compactStyleProfile(value) ?? {}).length
}

export function StyleProfileControls({ value, onChange }: { value: StyleProfile; onChange: (value: StyleProfile) => void }) {
  const { text } = useI18n()
  const ruleCount = styleProfileRuleCount(value)

  function update(key: StyleProfileKey, nextValue: string) {
    onChange({ ...value, [key]: nextValue })
  }

  return (
    <details className="group rounded-xl border border-border bg-muted/35 p-4 dark:border-[hsl(var(--pix-dark-hairline))] dark:bg-[hsl(var(--pix-dark-band-soft))]">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block text-sm font-bold">{text('项目风格档案', 'Project style profile')}</span>
          <span className="mt-1 block text-xs leading-5 text-muted-foreground">
            {text('作为项目统一风格补充进入 Prompt，不覆盖 Pix 的像素尺寸、背景、瓦片和序列帧硬约束。', 'Adds project-wide style constraints to the prompt without overriding Pix pixel-size, background, tile, or sequence rules.')}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <Badge variant={ruleCount > 0 ? 'info' : 'outline'}>{text(`已填写 ${ruleCount} 项`, `${ruleCount} set`)}</Badge>
          <span className="text-xs font-semibold text-primary group-open:hidden">{text('展开', 'Expand')}</span>
          <span className="hidden text-xs font-semibold text-primary group-open:inline">{text('收起', 'Collapse')}</span>
        </span>
      </summary>

      <div className="mt-4 grid gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {STYLE_FIELDS.map((field) => (
            <PixField key={field.key} label={text(field.zh, field.en)} hint={`${(value[field.key] ?? '').length}/${field.maxLength}`}>
              {field.multiline ? (
                <Textarea
                  value={value[field.key] ?? ''}
                  rows={2}
                  maxLength={field.maxLength}
                  placeholder={text(field.placeholderZh, field.placeholderEn)}
                  onChange={(event) => update(field.key, event.target.value)}
                />
              ) : (
                <Input
                  value={value[field.key] ?? ''}
                  maxLength={field.maxLength}
                  placeholder={text(field.placeholderZh, field.placeholderEn)}
                  onChange={(event) => update(field.key, event.target.value)}
                />
              )}
            </PixField>
          ))}
        </div>
        {ruleCount > 0 && <Button type="button" variant="ghost" size="sm" onClick={() => onChange({})}>{text('清空风格档案', 'Clear style profile')}</Button>}
      </div>
    </details>
  )
}
