/**
 * 首页平铺纹理示例数据。
 *
 * 与 homepageIconExamples 不同的是，纹理示例自带分类与可拼接预览，每张纹理
 * 都是 32×32（或更小）的单图，前端用 CSS background-repeat 平铺出 4×4 拼接预览。
 */

export type HomepageTextureCategory = 'natural' | 'man_made' | 'fantasy' | 'modern'

export type HomepageTextureExample = {
  id: string
  number: string
  category: HomepageTextureCategory
  /** 主题（中文） */
  theme: string
  /** 主题（英文） */
  themeEn: string
  /** 用户面板里输入的"主体"字段（中英文） */
  subject: string
  subjectEn: string
  /** 完整 prompt（含 extra_prompt） */
  prompt: string
  /** 静态资源相对路径 */
  src: string
  /** PNG 真实尺寸 */
  width: number
  height: number
}

export const homepageTextureExampleCategoryLabels: Record<HomepageTextureCategory, { zh: string; en: string }> = {
  natural: { zh: '自然', en: 'Natural' },
  man_made: { zh: '人造', en: 'Man-made' },
  fantasy: { zh: '幻想', en: 'Fantasy' },
  modern: { zh: '现代', en: 'Modern' },
}

export const homepageTextureExamples: HomepageTextureExample[] = [
  {
    id: '01_cobblestone_moss',
    number: '01',
    category: 'man_made',
    theme: '苔藓砖石路面',
    themeEn: 'Mossy cobblestone',
    subject: '苔藓砖石路面',
    subjectEn: 'Mossy cobblestone road',
    prompt:
      '苔藓砖石路面 — 古老欧洲风格，绿色苔藓填补石缝；32×32 无缝平铺地砖，灰石主调点缀苔藓绿，每块石头边界清晰。',
    src: '/homepage-examples/textures/01_cobblestone_moss.png',
    width: 32,
    height: 32,
  },
  {
    id: '02_wood_planks',
    number: '02',
    category: 'man_made',
    theme: '木板地面',
    themeEn: 'Wood planks',
    subject: '木板地面',
    subjectEn: 'Wood plank floor',
    prompt:
      '木板地面 — 温暖橡木色调，自然木纹纹理，木板之间有细缝，轻微做旧；32×32 无缝平铺，整张铺满。',
    src: '/homepage-examples/textures/02_wood_planks.png',
    width: 32,
    height: 32,
  },
  {
    id: '03_grass_field',
    number: '03',
    category: 'natural',
    theme: '像素草地',
    themeEn: 'Grass field',
    subject: '像素草地',
    subjectEn: 'Pixel grass field',
    prompt:
      '像素草地 — 鲜活的草绿色调，混入少量浅黄花朵和深绿丛簇，自然不规则；32×32 无缝平铺地图素材。',
    src: '/homepage-examples/textures/03_grass_field.png',
    width: 32,
    height: 32,
  },
]

export const homepageTextureCategoriesInUse: HomepageTextureCategory[] = Array.from(
  new Set(homepageTextureExamples.map((item) => item.category))
) as HomepageTextureCategory[]

export function getHomepageTextureLabel(example: HomepageTextureExample, language: 'zh-CN' | 'en'): { theme: string; subject: string; category: string } {
  const cat = homepageTextureExampleCategoryLabels[example.category]
  return language === 'en'
    ? { theme: example.themeEn, subject: example.subjectEn, category: cat.en }
    : { theme: example.theme, subject: example.subject, category: cat.zh }
}
