export type HomepageShowcaseKind = 'logo' | 'skillbook'
export type HomepageShowcaseModel = 'image2' | 'gemini-3.1-flash-image-preview'

export type HomepageShowcaseExample = {
  id: string
  kind: HomepageShowcaseKind
  title: string
  titleEn: string
  prompt: string
  promptEn: string
  model: HomepageShowcaseModel
  modelLabel: string
  jobId: number
  src: string
  width: number
  height: number
  requestedSize: string
  colors: number
}

export const homepageShowcaseKindLabels: Record<HomepageShowcaseKind, { zh: string; en: string }> = {
  logo: { zh: 'Logo', en: 'Logo' },
  skillbook: { zh: '技能书', en: 'Skill book' },
}

export const homepageShowcaseModelLabels: Record<HomepageShowcaseModel, string> = {
  image2: 'image2',
  'gemini-3.1-flash-image-preview': 'Gemini 3.1 Flash',
}

export const homepageShowcaseExamples: HomepageShowcaseExample[] = [
  {
    id: 'logo_chuangshilu_image2',
    kind: 'logo',
    title: '创世录',
    titleEn: 'Genesis Chronicle',
    prompt: '创世录 — 金白神圣创世题材，古卷与星辰光芒，庄严史诗感，字形厚重清晰，只使用标题文字。',
    promptEn: 'Genesis Chronicle — sacred gold-white creation theme, ancient scroll and starlight, solemn epic lettering, title text only.',
    model: 'image2',
    modelLabel: 'image2',
    jobId: 18,
    src: '/homepage-examples/showcase/logo_chuangshilu_image2_job18_pixelized.png',
    width: 128,
    height: 128,
    requestedSize: '128×64',
    colors: 24,
  },
  {
    id: 'logo_zhuxian_image2',
    kind: 'logo',
    title: '诛仙',
    titleEn: 'Zhu Xian',
    prompt: '诛仙 — 赤金仙侠剑气，锋利飞剑穿过云雾，危险而华丽，字形有杀伐感，只使用标题文字。',
    promptEn: 'Zhu Xian — red-gold xianxia sword aura, flying blades through cloud and mist, dangerous ornate title lettering.',
    model: 'image2',
    modelLabel: 'image2',
    jobId: 19,
    src: '/homepage-examples/showcase/logo_zhuxian_image2_job19_pixelized.png',
    width: 256,
    height: 256,
    requestedSize: '128×64',
    colors: 24,
  },
  {
    id: 'logo_qishilu_image2',
    kind: 'logo',
    title: '启示录',
    titleEn: 'Apocalypse',
    prompt: '启示录 — 黑金末日预言，破碎太阳、暗红符文和古老碑刻感，字形神秘厚重，只使用标题文字。',
    promptEn: 'Apocalypse — black-gold doomsday prophecy, broken sun, dark red runes, ancient inscription-like title lettering.',
    model: 'image2',
    modelLabel: 'image2',
    jobId: 8,
    src: '/homepage-examples/showcase/logo_qishilu_image2_job8_pixelized.png',
    width: 256,
    height: 256,
    requestedSize: '128×64',
    colors: 24,
  },
  {
    id: 'logo_chuangshilu_gemini',
    kind: 'logo',
    title: '创世录',
    titleEn: 'Genesis Chronicle',
    prompt: '创世录 — 金白神圣创世题材，古卷与星辰光芒，庄严史诗感，字形厚重清晰，只使用标题文字。',
    promptEn: 'Genesis Chronicle — sacred gold-white creation theme, ancient scroll and starlight, solemn epic lettering, title text only.',
    model: 'gemini-3.1-flash-image-preview',
    modelLabel: 'Gemini 3.1 Flash',
    jobId: 12,
    src: '/homepage-examples/showcase/logo_chuangshilu_gemini_job12_pixelized.png',
    width: 128,
    height: 128,
    requestedSize: '128×64',
    colors: 24,
  },
  {
    id: 'logo_zhuxian_gemini',
    kind: 'logo',
    title: '诛仙',
    titleEn: 'Zhu Xian',
    prompt: '诛仙 — 赤金仙侠剑气，锋利飞剑穿过云雾，危险而华丽，字形有杀伐感，只使用标题文字。',
    promptEn: 'Zhu Xian — red-gold xianxia sword aura, flying blades through cloud and mist, dangerous ornate title lettering.',
    model: 'gemini-3.1-flash-image-preview',
    modelLabel: 'Gemini 3.1 Flash',
    jobId: 13,
    src: '/homepage-examples/showcase/logo_zhuxian_gemini_job13_pixelized.png',
    width: 96,
    height: 96,
    requestedSize: '128×64',
    colors: 24,
  },
  {
    id: 'logo_qishilu_gemini',
    kind: 'logo',
    title: '启示录',
    titleEn: 'Apocalypse',
    prompt: '启示录 — 黑金末日预言，破碎太阳、暗红符文和古老碑刻感，字形神秘厚重，只使用标题文字。',
    promptEn: 'Apocalypse — black-gold doomsday prophecy, broken sun, dark red runes, ancient inscription-like title lettering.',
    model: 'gemini-3.1-flash-image-preview',
    modelLabel: 'Gemini 3.1 Flash',
    jobId: 14,
    src: '/homepage-examples/showcase/logo_qishilu_gemini_job14_pixelized.png',
    width: 96,
    height: 96,
    requestedSize: '128×64',
    colors: 24,
  },
  {
    id: 'skillbook_jinghuangmu_image2',
    kind: 'skillbook',
    title: '惊慌木',
    titleEn: 'Panic Wood',
    prompt: '惊慌木技能书 — 24×24 小型技能书图标，扭曲木纹与惊恐表情符号感，绿色木属性能量，清晰剪影，不要文字。',
    promptEn: 'Panic Wood skill book — 24×24 icon with twisted wood grain, anxious expression-like mark, green wood-element energy, no text.',
    model: 'image2',
    modelLabel: 'image2',
    jobId: 9,
    src: '/homepage-examples/showcase/skillbook_jinghuangmu_image2_job9_pixelized.png',
    width: 48,
    height: 48,
    requestedSize: '24×24',
    colors: 12,
  },
  {
    id: 'skillbook_ciyuanzhan_image2',
    kind: 'skillbook',
    title: '次元斩',
    titleEn: 'Dimensional Slash',
    prompt: '次元斩技能书 — 24×24 小型技能书图标，紫蓝色空间裂缝和斜向月牙斩击，发光边缘，清晰剪影，不要文字。',
    promptEn: 'Dimensional Slash skill book — 24×24 icon with blue-violet rift and diagonal crescent slash, glowing edges, no text.',
    model: 'image2',
    modelLabel: 'image2',
    jobId: 10,
    src: '/homepage-examples/showcase/skillbook_ciyuanzhan_image2_job10_pixelized.png',
    width: 64,
    height: 64,
    requestedSize: '24×24',
    colors: 12,
  },
  {
    id: 'skillbook_aoyi_ying_image2',
    kind: 'skillbook',
    title: '奥义！影',
    titleEn: 'Secret Art: Shadow',
    prompt: '奥义！影技能书 — 24×24 小型技能书图标，黑紫色影子忍术符号和暗影旋涡，神秘高对比，清晰剪影，不要文字。',
    promptEn: 'Secret Art: Shadow skill book — 24×24 icon with black-violet shadow ninjutsu mark and vortex, high contrast, no text.',
    model: 'image2',
    modelLabel: 'image2',
    jobId: 11,
    src: '/homepage-examples/showcase/skillbook_aoyi_ying_image2_job11_pixelized.png',
    width: 96,
    height: 96,
    requestedSize: '24×24',
    colors: 12,
  },
  {
    id: 'skillbook_jinghuangmu_gemini',
    kind: 'skillbook',
    title: '惊慌木',
    titleEn: 'Panic Wood',
    prompt: '惊慌木技能书 — 24×24 小型技能书图标，扭曲木纹与惊恐表情符号感，绿色木属性能量，清晰剪影，不要文字。',
    promptEn: 'Panic Wood skill book — 24×24 icon with twisted wood grain, anxious expression-like mark, green wood-element energy, no text.',
    model: 'gemini-3.1-flash-image-preview',
    modelLabel: 'Gemini 3.1 Flash',
    jobId: 15,
    src: '/homepage-examples/showcase/skillbook_jinghuangmu_gemini_job15_pixelized.png',
    width: 96,
    height: 96,
    requestedSize: '24×24',
    colors: 12,
  },
  {
    id: 'skillbook_ciyuanzhan_gemini',
    kind: 'skillbook',
    title: '次元斩',
    titleEn: 'Dimensional Slash',
    prompt: '次元斩技能书 — 24×24 小型技能书图标，紫蓝色空间裂缝和斜向月牙斩击，发光边缘，清晰剪影，不要文字。',
    promptEn: 'Dimensional Slash skill book — 24×24 icon with blue-violet rift and diagonal crescent slash, glowing edges, no text.',
    model: 'gemini-3.1-flash-image-preview',
    modelLabel: 'Gemini 3.1 Flash',
    jobId: 16,
    src: '/homepage-examples/showcase/skillbook_ciyuanzhan_gemini_job16_pixelized.png',
    width: 32,
    height: 32,
    requestedSize: '24×24',
    colors: 12,
  },
  {
    id: 'skillbook_aoyi_ying_gemini',
    kind: 'skillbook',
    title: '奥义！影',
    titleEn: 'Secret Art: Shadow',
    prompt: '奥义！影技能书 — 24×24 小型技能书图标，黑紫色影子忍术符号和暗影旋涡，神秘高对比，清晰剪影，不要文字。',
    promptEn: 'Secret Art: Shadow skill book — 24×24 icon with black-violet shadow ninjutsu mark and vortex, high contrast, no text.',
    model: 'gemini-3.1-flash-image-preview',
    modelLabel: 'Gemini 3.1 Flash',
    jobId: 17,
    src: '/homepage-examples/showcase/skillbook_aoyi_ying_gemini_job17_pixelized.png',
    width: 64,
    height: 64,
    requestedSize: '24×24',
    colors: 12,
  },
]

export const homepageShowcaseKindsInUse = Array.from(new Set(homepageShowcaseExamples.map((item) => item.kind))) as HomepageShowcaseKind[]
export const homepageShowcaseModelsInUse = Array.from(new Set(homepageShowcaseExamples.map((item) => item.model))) as HomepageShowcaseModel[]

export function getHomepageShowcaseLabel(example: HomepageShowcaseExample, language: 'zh-CN' | 'en'): { title: string; prompt: string; kind: string; model: string } {
  const kind = homepageShowcaseKindLabels[example.kind]
  return language === 'en'
    ? { title: example.titleEn, prompt: example.promptEn, kind: kind.en, model: example.modelLabel }
    : { title: example.title, prompt: example.prompt, kind: kind.zh, model: example.modelLabel }
}
