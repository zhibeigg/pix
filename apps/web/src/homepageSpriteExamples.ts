/**
 * 首页序列帧示例数据。
 *
 * 与 homepageTextureExamples 同样基于 sprite sheet：
 * 后端 sprite_mosaic pipeline 一次 API 调用产出整个 rows×cols mosaic（单图 mosaic 模式），
 * 后处理时再把 mosaic 拉平成 1 行 N 列的横向 sprite_sheet.png（每帧的 sheet_rect.y 始终为 0），
 * 前端直接按 frameCount 顺序切帧即可，无需自己处理多行偏移。
 *
 * 同时记录 `mosaicRows × mosaicCols` 以便展示「原始 mosaic 网格」结构信息（如 2×3 仍标记 2×3）。
 *
 * 4 张示例都来自实跑过的 sprite_sheet 任务产物，已复制到
 * `apps/web/public/homepage-examples/sprites/` 下。
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
  /** 主体描述（用户实际写在 prompt 字段里的） */
  prompt: string
  promptEn: string
  /** 每行的动作描述（mosaicRows 个；前端只展示，不参与播放） */
  rowPrompts: string[]
  rowPromptsEn: string[]
  /** 横向 sprite sheet 静态资源路径（已被后端拉平成 1 行 N 列） */
  src: string
  /** sprite sheet 真实宽 / 高（像素） */
  sheetWidth: number
  sheetHeight: number
  /** 单帧逻辑像素尺寸（effective_frame_size，后端 padding 后的实际帧大小） */
  frameWidth: number
  frameHeight: number
  /** 总帧数（= mosaicRows × mosaicCols；也等于 sheet 横向带上的列数） */
  frameCount: number
  /** 用户提交的原始 mosaic 行数（仅展示用） */
  mosaicRows: number
  /** 用户提交的原始 mosaic 列数（仅展示用） */
  mosaicCols: number
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
    id: '01_knight_idle_1x3',
    number: '01',
    category: 'character',
    theme: '骑士 idle 呼吸',
    themeEn: 'Knight idle breathing',
    subject: '蓝甲骑士',
    subjectEn: 'Blue-armored knight',
    prompt: 'A pixel-art knight in blue armor with a sword, centered on a pure magenta background.',
    promptEn: 'A pixel-art knight in blue armor with a sword, centered on a pure magenta background.',
    rowPrompts: ['3 帧 idle 呼吸：身体随呼吸节奏轻微起伏'],
    rowPromptsEn: ["3 frames showing the knight's idle stance (slight breathing motion)"],
    src: '/homepage-examples/sprites/01_knight_idle_1x3.png',
    sheetWidth: 192,
    sheetHeight: 80,
    frameWidth: 64,
    frameHeight: 80,
    frameCount: 3,
    mosaicRows: 1,
    mosaicCols: 3,
    fps: 3,
  },
  {
    id: '02_knight_walk_slash_2x3',
    number: '02',
    category: 'character',
    theme: '骑士行走 + 斩击 2×3 mosaic',
    themeEn: 'Knight walk + slash 2×3 mosaic',
    subject: '蓝甲骑士',
    subjectEn: 'Blue-armored knight',
    prompt: 'A pixel-art knight in blue armor, centered, pure magenta background.',
    promptEn: 'A pixel-art knight in blue armor, centered, pure magenta background.',
    rowPrompts: ['第 1 行：骑士向右行走的 3 帧', '第 2 行：骑士面向右下劈斩的 3 帧'],
    rowPromptsEn: [
      'Row 1: 3 frames of the knight walking to the right',
      'Row 2: 3 frames of the knight performing a downward sword slash facing right',
    ],
    src: '/homepage-examples/sprites/02_knight_walk_slash_2x3.png',
    sheetWidth: 384,
    sheetHeight: 64,
    frameWidth: 64,
    frameHeight: 64,
    frameCount: 6,
    mosaicRows: 2,
    mosaicCols: 3,
    fps: 8,
  },
  {
    id: '03_adventurer_torch_1x3',
    number: '03',
    category: 'character',
    theme: '冒险者高举火把',
    themeEn: 'Adventurer with torch',
    subject: '绿兜帽冒险者',
    subjectEn: 'Green-hooded adventurer',
    prompt: 'A pixel-art adventurer with green hood and brown leather armor, holding a torch.',
    promptEn: 'A pixel-art adventurer with green hood and brown leather armor, holding a torch.',
    rowPrompts: ['3 帧火把高举循环'],
    rowPromptsEn: ['3-frame torch-raised loop'],
    src: '/homepage-examples/sprites/03_adventurer_torch_1x3.png',
    sheetWidth: 192,
    sheetHeight: 80,
    frameWidth: 64,
    frameHeight: 80,
    frameCount: 3,
    mosaicRows: 1,
    mosaicCols: 3,
    fps: 5,
  },
  {
    id: '04_knight_1x9',
    number: '04',
    category: 'character',
    theme: '骑士 9 帧动作集',
    themeEn: 'Knight 9-frame action set',
    subject: '骑士',
    subjectEn: 'Knight',
    prompt: 'knight',
    promptEn: 'knight',
    rowPrompts: ['9 帧综合动作集（待机、行走等）'],
    rowPromptsEn: ['9-frame combined action set (idle, walking, etc.)'],
    src: '/homepage-examples/sprites/04_knight_1x9.png',
    sheetWidth: 720,
    sheetHeight: 64,
    frameWidth: 80,
    frameHeight: 64,
    frameCount: 9,
    mosaicRows: 1,
    mosaicCols: 9,
    fps: 8,
  },
]

export const homepageSpriteCategoriesInUse: HomepageSpriteCategory[] = Array.from(
  new Set(homepageSpriteExamples.map((item) => item.category))
) as HomepageSpriteCategory[]

export function getHomepageSpriteLabel(
  example: HomepageSpriteExample,
  language: 'zh-CN' | 'en',
): { theme: string; subject: string; category: string; prompt: string; rowPrompts: string[] } {
  const cat = homepageSpriteExampleCategoryLabels[example.category]
  return language === 'en'
    ? {
        theme: example.themeEn,
        subject: example.subjectEn,
        category: cat.en,
        prompt: example.promptEn,
        rowPrompts: example.rowPromptsEn,
      }
    : {
        theme: example.theme,
        subject: example.subject,
        category: cat.zh,
        prompt: example.prompt,
        rowPrompts: example.rowPrompts,
      }
}
