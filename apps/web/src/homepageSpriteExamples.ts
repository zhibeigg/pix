/**
 * 首页序列帧示例数据。
 *
 * 与 homepageTextureExamples 同样基于 sprite sheet（横向单行 N 帧），前端用 CSS
 * background-position 在固定 fps 下切帧，避免 GIF 体积大、缩放糊、播放速率不可控的问题。
 *
 * 当前 3 个示例都来自 1.51.x 实跑过的 sprite_sheet 任务产物，已复制到
 * `apps/web/public/homepage-examples/sprites/` 下，体积仅 ~10KB。
 */

export type HomepageSpriteCategory = 'character' | 'effect' | 'creature'

export type HomepageSpriteExample = {
  id: string
  number: string
  category: HomepageSpriteCategory
  /** 主题（中文） */
  theme: string
  /** 主题（英文） */
  themeEn: string
  /** 用户面板里输入的"主体"字段（中英文） */
  subject: string
  subjectEn: string
  /** 完整 prompt（用户实际写的） */
  prompt: string
  promptEn: string
  /** 横向 sprite sheet 静态资源路径 */
  src: string
  /** sprite sheet 真实宽 / 高（像素） */
  sheetWidth: number
  sheetHeight: number
  /** 单帧逻辑像素尺寸 */
  frameWidth: number
  frameHeight: number
  /** 帧数（cols） */
  frameCount: number
  /** 推荐播放速率 */
  fps: number
}

export const homepageSpriteExampleCategoryLabels: Record<HomepageSpriteCategory, { zh: string; en: string }> = {
  character: { zh: '角色', en: 'Character' },
  effect: { zh: '特效', en: 'Effect' },
  creature: { zh: '生物', en: 'Creature' },
}

export const homepageSpriteExamples: HomepageSpriteExample[] = [
  {
    id: '01_blue_slime_hop',
    number: '01',
    category: 'creature',
    theme: '蓝史莱姆跳跃循环',
    themeEn: 'Blue slime hop loop',
    subject: '蓝色史莱姆',
    subjectEn: 'Tiny blue slime',
    prompt:
      '一只小蓝史莱姆原地完成一次平滑的跳跃循环：压扁、拉伸、起跳、落地、回到 idle，简洁的侧视游戏精灵风格。',
    promptEn:
      'Tiny blue slime completes a smooth hop loop in place — squash, stretch, jump up, land, return to idle. Simple side-view game sprite.',
    src: '/homepage-examples/sprites/01_blue_slime_hop.png',
    sheetWidth: 512,
    sheetHeight: 64,
    frameWidth: 64,
    frameHeight: 64,
    frameCount: 8,
    fps: 8,
  },
  {
    id: '02_knight_walk',
    number: '02',
    category: 'character',
    theme: '骑士行走循环',
    themeEn: 'Knight walk cycle',
    subject: '一名骑士',
    subjectEn: 'A knight',
    prompt: '一名骑士的 8 帧无缝行走循环，侧视像素游戏角色。',
    promptEn: 'An 8-frame seamless walk cycle of a knight, side-view pixel game character.',
    src: '/homepage-examples/sprites/02_knight_walk.png',
    sheetWidth: 512,
    sheetHeight: 64,
    frameWidth: 64,
    frameHeight: 64,
    frameCount: 8,
    fps: 8,
  },
  {
    id: '03_knight_idle',
    number: '03',
    category: 'character',
    theme: '骑士 idle 呼吸',
    themeEn: 'Knight idle breathing',
    subject: '一名骑士',
    subjectEn: 'A knight',
    prompt: '骑士站立 idle 的 3 帧呼吸循环，身体轻微起伏。',
    promptEn: '3 frames of an idle stance, the character breathing slightly.',
    src: '/homepage-examples/sprites/03_knight_idle.png',
    sheetWidth: 192,
    sheetHeight: 64,
    frameWidth: 64,
    frameHeight: 64,
    frameCount: 3,
    fps: 6,
  },
]

export const homepageSpriteCategoriesInUse: HomepageSpriteCategory[] = Array.from(
  new Set(homepageSpriteExamples.map((item) => item.category))
) as HomepageSpriteCategory[]

export function getHomepageSpriteLabel(
  example: HomepageSpriteExample,
  language: 'zh-CN' | 'en',
): { theme: string; subject: string; category: string; prompt: string } {
  const cat = homepageSpriteExampleCategoryLabels[example.category]
  return language === 'en'
    ? { theme: example.themeEn, subject: example.subjectEn, category: cat.en, prompt: example.promptEn }
    : { theme: example.theme, subject: example.subject, category: cat.zh, prompt: example.prompt }
}
