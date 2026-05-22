import { useI18n } from '../../i18n'
import { Badge } from '../ui/badge'
import { statusLabel, statusTone } from '../../design/status'

export function PixStatusBadge({ status }: { status: string }) {
  const { language } = useI18n()
  const tone = statusTone(status)
  const variant = tone === 'success' ? 'success' : tone === 'danger' ? 'danger' : tone === 'info' ? 'info' : tone === 'warning' ? 'warning' : 'muted'
  return <Badge variant={variant}>{statusLabel(status, language)}</Badge>
}
