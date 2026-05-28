import { Alert, AlertDescription, AlertTitle } from './ui/alert'
import { useI18n } from '../i18n'
import { cn } from '../lib/utils'

type TextFn = (zh: string, en: string) => string

type FriendlyJobError = {
  title: string
  description: string
  action: string
}

export function JobErrorSummary({ error, compact = false, className }: { error?: string | null; compact?: boolean; className?: string }) {
  const { text } = useI18n()
  const friendly = summarizeJobError(error, text)
  const detail = normalizeErrorDetail(error)

  return (
    <Alert variant="destructive" className={cn('space-y-2 text-left', compact && 'p-3', className)}>
      <AlertTitle>{friendly.title}</AlertTitle>
      <AlertDescription>
        <p>{friendly.description}</p>
        <p className="mt-1 font-medium">{friendly.action}</p>
      </AlertDescription>
      {detail && (
        <details className="rounded-md border border-destructive/20 bg-card/70 px-3 py-2 text-xs text-foreground/80 dark:bg-black/20" onClick={(event) => event.stopPropagation()}>
          <summary className="cursor-pointer font-semibold text-destructive dark:text-red-100">{text('查看技术详情', 'Show technical details')}</summary>
          <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-muted-foreground">{detail}</pre>
        </details>
      )}
    </Alert>
  )
}

export function summarizeJobError(error: string | null | undefined, text: TextFn): FriendlyJobError {
  const message = normalizeErrorDetail(error).toLowerCase()

  if (!message) {
    return {
      title: text('生成失败', 'Generation failed'),
      description: text('这次任务没有生成可用结果。', 'This job did not produce a usable result.'),
      action: text('请稍后重试，或稍微简化提示词后再生成。', 'Try again later, or simplify the prompt and generate again.'),
    }
  }

  if (message.includes('readtimeout') || message.includes('timed out') || message.includes('timeout')) {
    return {
      title: text('图片下载超时', 'Image download timed out'),
      description: text('AI 服务响应较慢，后端在下载生成图片时等太久了。', 'The AI service was slow, and the backend waited too long while downloading the generated image.'),
      action: text('请先重试；如果连续失败，请检查服务器网络或提高后端 api.timeout。', 'Retry first; if it keeps failing, check server networking or increase backend api.timeout.'),
    }
  }

  if (
    message.includes('remoteprotocolerror') ||
    message.includes('server disconnected') ||
    message.includes('remote disconnected') ||
    message.includes('connection closed') ||
    message.includes('peer closed connection')
  ) {
    return {
      title: text('远端服务中途断开', 'Remote service closed the connection'),
      description: text('AI 服务在生成期间主动关闭了连接，常见于单次响应过长（例如超长 prompt 或 quality=high）。', 'The image service closed the connection mid-response. This usually happens when a single response is too long (e.g., very long prompt or quality=high).'),
      action: text('请精简素材描述（建议 800 字以内），或在管理后台把 pix.image_gen.quality 改为 low/auto；序列帧素材请使用「序列帧」模式而不是「素材直出」。', 'Shorten the prompt (≤ 800 chars recommended), or set pix.image_gen.quality to low/auto in admin. For sprite sheets, use the sequence mode instead of single-asset mode.'),
    }
  }

  if (message.includes('connecttimeout') || message.includes('connection') || message.includes('network') || message.includes('temporary failure')) {
    return {
      title: text('网络连接不稳定', 'Network connection issue'),
      description: text('后端连接图片服务时遇到网络问题。', 'The backend hit a network issue while contacting the image service.'),
      action: text('请稍后重试；如果服务器在海外或网络受限，请检查代理、DNS 或出口网络。', 'Try again later; if the server network is restricted, check proxy, DNS, or outbound connectivity.'),
    }
  }

  if (message.includes('401') || message.includes('403') || message.includes('unauthorized') || message.includes('forbidden') || message.includes('api key')) {
    return {
      title: text('图片服务认证失败', 'Image service authentication failed'),
      description: text('后端连接图片服务时没有通过认证。', 'The backend could not authenticate with the image service.'),
      action: text('请检查 PACKY_API_KEY / PACKY_VL_API_KEY 是否正确，并重启服务。', 'Check PACKY_API_KEY / PACKY_VL_API_KEY and restart the service.'),
    }
  }

  if (message.includes('content policy') || message.includes('safety') || message.includes('blocked') || message.includes('moderation')) {
    return {
      title: text('提示词未通过安全检查', 'Prompt was blocked'),
      description: text('当前提示词可能触发了图片服务的安全限制。', 'The prompt may have triggered the image service safety rules.'),
      action: text('请换一种更中性的描述，避免敏感、血腥或侵权内容。', 'Use a more neutral description and avoid sensitive, graphic, or infringing content.'),
    }
  }

  if (message.includes('insufficient') || message.includes('credits') || message.includes('余额') || message.includes('点数')) {
    return {
      title: text('点数不足或扣费失败', 'Credits unavailable'),
      description: text('任务提交或扣费时没有拿到足够点数。', 'The job could not reserve enough credits.'),
      action: text('请刷新点数余额后再试。', 'Refresh your credit balance and try again.'),
    }
  }

  return {
    title: text('生成失败', 'Generation failed'),
    description: text('这次任务没有生成可用结果，可能是远程服务临时异常。', 'This job did not produce a usable result, possibly due to a temporary remote service issue.'),
    action: text('请重试；如果连续失败，请把技术详情发给管理员排查。', 'Retry; if it keeps failing, send the technical details to an administrator.'),
  }
}

function normalizeErrorDetail(error: string | null | undefined) {
  return (error ?? '').replace(/\r\n/g, '\n').trim()
}
