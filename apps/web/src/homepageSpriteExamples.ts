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

/**
 * 生成模式：
 * - mosaic：1 次生图产出 rows×cols 网格 sprite sheet（单图 mosaic 模式）。
 * - video_bridge：先生成首/尾关键帧，再调用火山方舟 Ark 首尾帧图生视频补间，抽帧成序列帧。
 * - video_bridge_loop：video_bridge 的「回到首帧」变体，视频先到尾帧再平滑回到首帧，末帧对齐首帧做无缝循环。
 */
export type HomepageSpriteGenerationMode = 'mosaic' | 'video_bridge' | 'video_bridge_loop'

export type HomepageSpriteExample = {
  id: string
  number: string
  category: HomepageSpriteCategory
  /** 主题（中文） */
  theme: string
  /** 主题（英文） */
  themeEn: string
  /** 生成模式：mosaic 单图 / video_bridge 视频补间 / video_bridge_loop 视频补间回首帧循环 */
  generationMode: HomepageSpriteGenerationMode
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

export const homepageSpriteGenerationModeLabels: Record<
  HomepageSpriteGenerationMode,
  { zh: string; en: string; hint: string; hintEn: string }
> = {
  mosaic: {
    zh: 'Mosaic 单图',
    en: 'Mosaic',
    hint: '1 次生图产出 rows×cols 全帧网格',
    hintEn: 'One API call renders the full rows×cols frame grid',
  },
  video_bridge: {
    zh: '视频补间',
    en: 'Video bridge',
    hint: '首/尾关键帧 → Ark 图生视频补间 → 抽帧序列帧',
    hintEn: 'Start/end keyframes → Ark image-to-video → sampled frames',
  },
  video_bridge_loop: {
    zh: '视频补间·回首帧循环',
    en: 'Video bridge · loop',
    hint: '视频先到尾帧再回到首帧，末帧对齐首帧无缝循环',
    hintEn: 'Video reaches the end pose then returns to the first frame for a seamless loop',
  },
}

export const homepageSpriteExamples: HomepageSpriteExample[] = [
  {
    id: '01_knight_idle_1x3',
    number: '01',
    category: 'character',
    generationMode: 'mosaic',
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
    generationMode: 'mosaic',
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
    generationMode: 'mosaic',
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
    generationMode: 'mosaic',
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
  {
    id: '05_xianxia_flying_sword',
    number: '05',
    category: 'character',
    generationMode: 'video_bridge',
    theme: '御剑青衣剑修',
    themeEn: 'Sword-riding cultivator',
    subject: '青衣御剑剑修',
    subjectEn: 'Blue-robed sword cultivator',
    prompt: '青衣御剑剑修，长发飘带，脚踏青色飞剑侧身悬立。',
    promptEn: 'A pixel-art xianxia sword cultivator in flowing azure robes, standing on a glowing cyan flying sword.',
    rowPrompts: ['御剑向前飞行：衣袂发丝后扬，青色剑气沿剑身流转，平稳滑翔微微前倾'],
    rowPromptsEn: ['Riding the flying sword forward: robes and hair stream back, cyan sword-qi flows along the blade'],
    src: '/homepage-examples/sprites/05_xianxia_flying_sword.png',
    sheetWidth: 4096,
    sheetHeight: 256,
    frameWidth: 256,
    frameHeight: 256,
    frameCount: 16,
    mosaicRows: 2,
    mosaicCols: 8,
    fps: 8,
  },
  {
    id: '06_xianxia_thunder_talisman',
    number: '06',
    category: 'character',
    generationMode: 'video_bridge',
    theme: '踏罡雷法道人',
    themeEn: 'Thunder-rite daoist',
    subject: '玄袍雷法道人',
    subjectEn: 'Dark-robed thunder daoist',
    prompt: '玄袍金边雷法道人，双手掐诀，脚下九宫雷阵旋转发光，正面。',
    promptEn: 'A pixel-art xianxia daoist in dark robes forming a hand seal, a spinning nine-palace thunder array under his feet.',
    rowPrompts: ['施展雷法：紫金雷弧缠绕周身与双手，脚下雷阵旋转变亮，衣摆被上涌灵气吹动'],
    rowPromptsEn: ['Channeling thunder: violet-gold lightning coils around body and hands, the thunder array rotates and brightens'],
    src: '/homepage-examples/sprites/06_xianxia_thunder_talisman.png',
    sheetWidth: 2048,
    sheetHeight: 128,
    frameWidth: 128,
    frameHeight: 128,
    frameCount: 16,
    mosaicRows: 2,
    mosaicCols: 8,
    fps: 8,
  },
  {
    id: '07_xianxia_nascent_soul',
    number: '07',
    category: 'character',
    generationMode: 'video_bridge',
    theme: '吐纳元婴修士',
    themeEn: 'Nascent-soul meditator',
    subject: '白袍打坐修士',
    subjectEn: 'White-robed meditating cultivator',
    prompt: '白袍盘坐修士，双手结印置于膝上，丹田金色灵光，正面。',
    promptEn: 'A pixel-art xianxia cultivator in white robes meditating cross-legged, a faint golden glow at the dantian.',
    rowPrompts: ['吐纳炼气：丹田金光脉动上升，一缕半透明元婴虚影自头顶缓缓升起，衣发随灵气轻飘'],
    rowPromptsEn: ['Refining energy: the golden dantian glow rises, a translucent nascent-soul image floats up above the head'],
    src: '/homepage-examples/sprites/07_xianxia_nascent_soul.png',
    sheetWidth: 2048,
    sheetHeight: 128,
    frameWidth: 128,
    frameHeight: 128,
    frameCount: 16,
    mosaicRows: 2,
    mosaicCols: 8,
    fps: 8,
  },
  {
    id: '08_dark_fantasy_undead_greatsword',
    number: '08',
    category: 'character',
    generationMode: 'video_bridge_loop',
    theme: '不死巨剑骑士',
    themeEn: 'Undead greatsword knight',
    subject: '锈甲巨剑骑士',
    subjectEn: 'Rusted-armor greatsword knight',
    prompt: '锈灰重甲、破损黑披风的不死巨剑骑士，双手持巨剑，中世纪阴郁风，侧面。',
    promptEn: 'A pixel-art dark-fantasy Souls-like undead knight in rusted armor and a tattered cape, holding a huge greatsword.',
    rowPrompts: ['沉重巨剑连招并归位：向后蓄力 → 缓慢横扫 → 收剑回到起始持剑站姿（无缝循环）'],
    rowPromptsEn: ['Heavy greatsword combo returning to guard: wind back → slow horizontal swing → settle back to the ready stance (seamless loop)'],
    src: '/homepage-examples/sprites/08_dark_fantasy_undead_greatsword.png',
    sheetWidth: 4096,
    sheetHeight: 256,
    frameWidth: 256,
    frameHeight: 256,
    frameCount: 16,
    mosaicRows: 2,
    mosaicCols: 8,
    fps: 8,
  },
  {
    id: '09_dark_fantasy_hollow_lantern',
    number: '09',
    category: 'character',
    generationMode: 'video_bridge_loop',
    theme: '褪色巡夜人',
    themeEn: 'Hollow lantern-bearer',
    subject: '破披风提灯者',
    subjectEn: 'Ragged lantern-bearer',
    prompt: '裹着破烂兜帽斗篷的褪色巡夜人，高举一盏暖焰铁灯，中世纪朝圣者，侧面。',
    promptEn: 'A pixel-art dark-fantasy Souls-like hollow wanderer in a ragged hooded cloak, holding up an old iron lantern.',
    rowPrompts: ['提灯探照并回到待机：高举铁灯照向黑暗 → 火焰摇曳投光 → 放下灯回到休息待机姿势（无缝循环）'],
    rowPromptsEn: ['Lantern-scouting returning to rest: raise the lantern to peer into the dark → flame flickers → lower it back to idle (seamless loop)'],
    src: '/homepage-examples/sprites/09_dark_fantasy_hollow_lantern.png',
    sheetWidth: 4096,
    sheetHeight: 256,
    frameWidth: 256,
    frameHeight: 256,
    frameCount: 16,
    mosaicRows: 2,
    mosaicCols: 8,
    fps: 8,
  },
  {
    id: '10_dark_fantasy_shield_spear',
    number: '10',
    category: 'character',
    generationMode: 'video_bridge_loop',
    theme: '持盾长矛守卫',
    themeEn: 'Shield-and-spear sentinel',
    subject: '铁盔盾矛守卫',
    subjectEn: 'Iron-helm shield sentinel',
    prompt: '深色铁甲闭盔守卫，一手持高大鸢盾一手竖握长矛，中世纪冷峻守卫警戒中，侧面。',
    promptEn: 'A pixel-art dark-fantasy Souls-like sentinel in dark iron armor holding a tall kite shield and an upright spear.',
    rowPrompts: ['沉稳警戒并归位：举盾架矛戒备环视 → 放下盾牌回到平静休息站姿（无缝循环）'],
    rowPromptsEn: ['Steady guarding watch returning to rest: raise shield into a braced guard and scan → lower back to the calm stance (seamless loop)'],
    src: '/homepage-examples/sprites/10_dark_fantasy_shield_spear.png',
    sheetWidth: 4096,
    sheetHeight: 256,
    frameWidth: 256,
    frameHeight: 256,
    frameCount: 16,
    mosaicRows: 2,
    mosaicCols: 8,
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
