import type { AppPage } from '../components/AppTabs'
import type { PixLanguage } from '../theme'

const SITE_NAME_ZH = 'Pix Forge · 像素素材工坊'
const SITE_NAME_EN = 'Pix Forge · Pixel Asset Forge'

const pageSeo: Record<AppPage, Record<PixLanguage, { title: string; description: string }>> = {
  home: {
    'zh-CN': {
      title: 'AI 像素素材生成器｜游戏图标、平铺纹理、序列帧 - Pix Forge',
      description: 'Pix Forge 是面向游戏开发者的 AI 像素素材工坊，可在 10–30 分钟内批量生成统一尺寸、透明背景、可导出的像素 PNG、物品图标、平铺纹理和序列帧动画。',
    },
    en: {
      title: 'AI Pixel Asset Generator for Game Icons, Textures and Sprites - Pix Forge',
      description: 'Pix Forge helps game developers generate consistent transparent pixel PNGs, item icons, tileable textures, and sprite sheets for prototypes in 10–30 minutes.',
    },
  },
  workspace: {
    'zh-CN': {
      title: '生产工作台｜批量生成 AI 像素游戏素材 - Pix Forge',
      description: '在 Pix Forge 生产工作台中创建单图或批量像素素材任务，统一尺寸、色板和透明背景输出。',
    },
    en: {
      title: 'Production Workspace for AI Pixel Game Assets - Pix Forge',
      description: 'Create single or batch pixel asset jobs with consistent sizes, palettes, and transparent PNG output in Pix Forge.',
    },
  },
  'raw-image': {
    'zh-CN': {
      title: '原始生图｜AI 游戏素材草图生成 - Pix Forge',
      description: '使用 Pix Forge 原始生图模式快速生成游戏素材草图，再进入像素化和作品库流程。',
    },
    en: {
      title: 'Raw Image Generation for Game Asset Concepts - Pix Forge',
      description: 'Generate raw game asset concepts before pixelization, review, and export in Pix Forge.',
    },
  },
  gallery: {
    'zh-CN': {
      title: '作品库｜查看、微调和导出像素素材 - Pix Forge',
      description: '在 Pix Forge 作品库中查看生成结果、调整序列帧、复制参数并导出透明像素 PNG。',
    },
    en: {
      title: 'Gallery for Reviewing and Exporting Pixel Assets - Pix Forge',
      description: 'Review generated works, tune sprite frames, copy parameters, and export transparent pixel PNGs in Pix Forge.',
    },
  },
  packs: {
    'zh-CN': {
      title: '素材包｜归档和批量导出游戏像素素材 - Pix Forge',
      description: '用 Pix Forge 素材包归档项目素材，集中管理物品图标、纹理和序列帧并批量导出。',
    },
    en: {
      title: 'Asset Packs for Organizing Pixel Game Assets - Pix Forge',
      description: 'Organize item icons, textures, and sprite sheets into reusable asset packs for batch export in Pix Forge.',
    },
  },
  billing: {
    'zh-CN': {
      title: '点数中心｜AI 像素素材生成计费 - Pix Forge',
      description: '查看 Pix Forge 点数余额、充值订单和 AI 像素素材生成价格规则。',
    },
    en: {
      title: 'Billing and Credits for AI Pixel Asset Generation - Pix Forge',
      description: 'Manage credits, orders, and pricing for AI pixel asset generation in Pix Forge.',
    },
  },
  rewards: {
    'zh-CN': {
      title: '邀请奖励｜分享 Pix Forge 获得点数奖励',
      description: '分享 Pix Forge 邀请链接给游戏开发者好友，获得可用于 AI 像素素材生成的奖励点数。',
    },
    en: {
      title: 'Referral Rewards for Pix Forge',
      description: 'Share Pix Forge with other game developers and earn credits for AI pixel asset generation.',
    },
  },
  admin: {
    'zh-CN': {
      title: '后台管理｜Pix Forge 运营控制台',
      description: 'Pix Forge 管理后台用于查看用户、订单、价格规则和系统设置。',
    },
    en: {
      title: 'Admin Console for Pix Forge Operations',
      description: 'Pix Forge admin console for users, orders, pricing rules, and system settings.',
    },
  },
  'not-found': {
    'zh-CN': {
      title: '页面未找到｜Pix Forge 像素素材工坊',
      description: '你访问的 Pix Forge 页面不存在或已经移动。回到首页重新选择素材类型，或进入工作台继续生成游戏像素素材。',
    },
    en: {
      title: 'Page Not Found - Pix Forge',
      description: 'The Pix Forge page you requested does not exist or has moved. Return home or open the workspace to keep generating pixel game assets.',
    },
  },
}

function upsertMeta(selector: string, create: () => HTMLMetaElement, content: string) {
  let node = document.head.querySelector<HTMLMetaElement>(selector)
  if (!node) {
    node = create()
    document.head.appendChild(node)
  }
  node.content = content
}

function setNamedMeta(name: string, content: string) {
  upsertMeta(
    `meta[name="${name}"]`,
    () => {
      const node = document.createElement('meta')
      node.name = name
      return node
    },
    content,
  )
}

function setPropertyMeta(property: string, content: string) {
  upsertMeta(
    `meta[property="${property}"]`,
    () => {
      const node = document.createElement('meta')
      node.setAttribute('property', property)
      return node
    },
    content,
  )
}

export function applyPageSeo(page: AppPage, language: PixLanguage) {
  const seo = pageSeo[page][language]
  const siteName = language === 'en' ? SITE_NAME_EN : SITE_NAME_ZH
  document.title = seo.title
  setNamedMeta('description', seo.description)
  setPropertyMeta('og:title', seo.title)
  setPropertyMeta('og:description', seo.description)
  setPropertyMeta('og:site_name', siteName)
  setPropertyMeta('og:locale', language === 'en' ? 'en_US' : 'zh_CN')
  setNamedMeta('twitter:title', seo.title)
  setNamedMeta('twitter:description', seo.description)
}
