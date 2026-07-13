import type { GenerationJob, JobOutput } from '../types'

const MAX_SPRITE_PREVIEW_FRAMES = 256

export function spriteFpsFromJob(job: GenerationJob) {
  const sprite = asRecord(job.params_json?.sprite)
  const fps = Number(sprite?.fps)
  return Number.isFinite(fps) && fps > 0 ? fps : 8
}

export function spriteFrameCountFromJob(job: GenerationJob, output?: JobOutput | null) {
  const positionedFrameCount = (output?.sprite_frames ?? []).filter((frame) => {
    const rect = frame.sheet_rect
    return rect && rect.w > 0 && rect.h > 0
  }).length
  if (positionedFrameCount > 1) return Math.min(positionedFrameCount, MAX_SPRITE_PREVIEW_FRAMES)

  const sprite = asRecord(job.params_json?.sprite)
  const requestedFrameCount = normalizedFrameCount(sprite?.frame_count)
  if (requestedFrameCount) return requestedFrameCount

  const rows = positiveInt(sprite?.rows)
  const cols = positiveInt(sprite?.cols)
  const gridFrameCount = rows && cols ? normalizedFrameCount(rows * cols) : 0
  if (gridFrameCount) return gridFrameCount

  return normalizedFrameCount(output?.sprite_frames?.length)
}

export function spriteSheetUrlFromJob(job: GenerationJob, output?: JobOutput | null) {
  if (!output || !isSpriteOutput(job, output)) return null
  return output.sprite_sheet_url || output.pixelized_url || null
}

function isSpriteOutput(job: GenerationJob, output: JobOutput) {
  return job.job_type === 'sprite_sheet'
    || Boolean(output.sprite_sheet_url)
    || Boolean(output.sequence_json_url)
    || Boolean(output.sprite_frames?.length)
    || spriteFrameCountFromJob(job, output) > 1
}

function normalizedFrameCount(value: unknown) {
  const count = positiveInt(value)
  return count && count > 1 && count <= MAX_SPRITE_PREVIEW_FRAMES ? count : 0
}

function positiveInt(value: unknown) {
  const number = Math.floor(Number(value))
  return Number.isFinite(number) && number > 0 ? number : 0
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
}
