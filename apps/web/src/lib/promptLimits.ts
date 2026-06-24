import type { ImageModelsResponse, PromptLimits } from '../types'

export const DEFAULT_PROMPT_LIMITS: PromptLimits = {
  prompt_max_chars: 3000,
  raw_image_prompt_max_chars: 3000,
  asset_subject_max_chars: 160,
  asset_extra_prompt_max_chars: 3000,
  sprite_subject_max_chars: 3000,
  sprite_row_prompt_max_chars: 600,
}

function positiveLimit(value: unknown, fallback: number): number {
  const next = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
  return Number.isFinite(next) && next > 0 ? Math.floor(next) : fallback
}

export function promptLimitsFromModels(imageModels: ImageModelsResponse): PromptLimits {
  const limits = imageModels.limits ?? DEFAULT_PROMPT_LIMITS
  return {
    prompt_max_chars: positiveLimit(limits.prompt_max_chars, DEFAULT_PROMPT_LIMITS.prompt_max_chars),
    raw_image_prompt_max_chars: positiveLimit(limits.raw_image_prompt_max_chars, DEFAULT_PROMPT_LIMITS.raw_image_prompt_max_chars),
    asset_subject_max_chars: positiveLimit(limits.asset_subject_max_chars, DEFAULT_PROMPT_LIMITS.asset_subject_max_chars),
    asset_extra_prompt_max_chars: positiveLimit(limits.asset_extra_prompt_max_chars, DEFAULT_PROMPT_LIMITS.asset_extra_prompt_max_chars),
    sprite_subject_max_chars: positiveLimit(limits.sprite_subject_max_chars, DEFAULT_PROMPT_LIMITS.sprite_subject_max_chars),
    sprite_row_prompt_max_chars: positiveLimit(limits.sprite_row_prompt_max_chars, DEFAULT_PROMPT_LIMITS.sprite_row_prompt_max_chars),
  }
}
