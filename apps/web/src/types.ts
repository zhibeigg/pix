export type User = {
  id: number
  email: string
  display_name: string
  role: 'user' | 'admin' | string
  status: string
  created_at: string
}

export type TokenResponse = {
  access_token: string
  token_type: string
}

export type CreditBalance = {
  available_credits: number
  reserved_credits: number
  total_recharged: number
  total_consumed: number
}

export type CreditTransaction = {
  id: number
  type: string
  amount: number
  balance_after: number
  job_id: number | null
  note: string
  created_at: string
}

export type JobType = 'text_to_image' | 'image_to_image' | 'local_pixelize' | 'repixelize'

export type PixelizeParams = {
  output_size: [number, number]
  colors: number
  dither: string
  preset: string
  preview_scale: number
  edge_enhance: number
  saturation: number
  resample: string
  snap_to_grid: boolean
  remove_bg: boolean
  bg_tolerance: number
  bg_feather: number
  edge_style: string
  auto_crop: boolean
  crop_padding: number
  crop_square: boolean
}

export type JobCreateRequest = {
  job_type: JobType
  prompt?: string | null
  input_image_path?: string | null
  client_request_id?: string
  image_size?: string | null
  image_quality?: string | null
  image_model?: string | null
  vl_model?: string | null
  skip_vl?: boolean
  pixelize: PixelizeParams
}

export type JobOutput = {
  run_dir: string
  source_path: string
  pixelized_path: string
  preview_path: string | null
  analysis_json_path: string | null
  meta_json_path: string
}

export type GenerationJob = {
  id: number
  job_type: string
  status: string
  prompt: string | null
  input_image_path: string | null
  params_json: Record<string, unknown>
  price_credits: number
  reserved_credits: number
  error_message: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  outputs: JobOutput[]
}

export type UploadResponse = {
  path: string
  filename: string
  content_type: string
  size_bytes: number
}

export type PricingRule = {
  key: string
  price_credits: number
  enabled: boolean
  updated_at: string
}
