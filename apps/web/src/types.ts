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

export type SetupStatus = {
  needs_admin: boolean
  user_count: number
  admin_count: number
  email_provider: string
  debug_codes_available: boolean
  registration_bonus_credits: number
  local_test_login_available: boolean
  local_test_account_email?: string | null
  turnstile_enabled: boolean
  turnstile_site_key: string
}

export type BootstrapAdminResponse = TokenResponse & {
  user: User
}

export type EmailCodeResponse = {
  ok: boolean
  retry_after_seconds: number
  expires_in_seconds: number
  debug_code?: string | null
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

export type ApiKeyItem = {
  id: number
  name: string
  key_prefix: string
  scopes: string[]
  enabled: boolean
  last_used_at: string | null
  expires_at: string | null
  revoked_at: string | null
  created_at: string
  updated_at: string
}

export type ApiKeyCreatePayload = {
  name: string
  scopes: string[]
  expires_at?: string | null
  custom_key?: string | null
}

export type ApiKeyUpdatePayload = {
  name?: string
  enabled?: boolean
  scopes?: string[]
  expires_at?: string | null
}

export type ApiKeyCreateResponse = {
  key: string
  item: ApiKeyItem
}

export type AdminBatchAdjustCreditsResponse = {
  adjusted_count: number
  amount: number
  note: string
  all_users: boolean
  transactions: CreditTransaction[]
}

export type ReferralCurrencyTotals = {
  currency: string
  pending_cents: number
  available_cents: number
  total_reward_cents: number
}

export type ReferralInvite = {
  id: number
  referred_user_id: number
  referred_user_email: string
  referred_user_display_name: string
  created_at: string
}

export type ReferralReward = {
  id: number
  referred_user_id: number
  referred_user_email: string
  order_id: number
  order_amount_cents: number
  order_credits: number
  amount_cents: number
  remaining_cents: number
  currency: string
  rate_bps: number
  status: string
  available_at: string
  created_at: string
}

export type ReferralSettlement = {
  id: number
  type: string
  amount_cents: number
  currency: string
  credits: number
  status: string
  note: string
  created_at: string
  updated_at: string
}

export type ReferralSummary = {
  code: string
  invite_url: string
  enabled: boolean
  commission_rate_bps: number
  pending_days: number
  primary_currency: string
  pending_cents: number
  available_cents: number
  total_reward_cents: number
  invited_count: number
  totals_by_currency: ReferralCurrencyTotals[]
  invites: ReferralInvite[]
  rewards: ReferralReward[]
  settlements: ReferralSettlement[]
}

export type JobType = 'asset' | 'text_to_image' | 'image_to_image' | 'local_pixelize' | 'local_bg_remove' | 'repixelize' | 'sprite_sheet'
export type JobStatus = 'pending' | 'running' | 'waiting' | 'succeeded' | 'failed' | 'cancelled' | string
export type SpriteMode = 'mosaic' | 'video_bridge'

export type ImageModelInfo = {
  id: string
  label: string
  providers: string[]
  operations: string[]
  sizes: string[]
  qualities: string[]
  output_formats: string[]
  protocols: string[]
  provider_count: number
  default_size?: string
  default_quality?: string
}

export type PromptLimits = {
  prompt_max_chars: number
  raw_image_prompt_max_chars: number
  asset_subject_max_chars: number
  asset_extra_prompt_max_chars: number
  sprite_subject_max_chars: number
  sprite_row_prompt_max_chars: number
}

export type ImageModelsResponse = {
  default: string
  models: string[]
  items?: ImageModelInfo[]
  limits?: PromptLimits
}

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
  bg_removal_algorithm?: 'pixel_bg' | 'color_to_alpha' | string
  auto_crop: boolean
  crop_padding: number
  crop_square: boolean
  palette_mode: 'auto' | 'ramp' | 'kmeans' | string
  generated_preprocess_method: 'perfect_pixel' | 'legacy' | 'none' | string
}

export type GridDesignParams = {
  mode: 'off' | 'extract'
}

export type SpriteParams = {
  mode?: SpriteMode
  rows: number
  cols: number
  row_prompts?: string[]
  reference_image_path?: string | null
  frame_count: number
  fps: number
  gif_export?: boolean
  duration_ms: number
  loop: number
  video_action_prompt?: string
  video_return_to_first_frame?: boolean
  video_duration_seconds?: number | null
  video_resolution?: string | null
  video_ratio?: string | null
}

export type TextureKind = 'auto' | 'generic_texture' | 'terrain_ground' | 'path_floor' | 'wall_surface' | 'wood_planks' | 'water_liquid' | 'foliage_canopy' | 'roof_tile' | 'metal_panel' | 'fabric_carpet'
export type DualGridTransitionStyle = 'rounded' | 'hard' | 'outline'

export type StyleProfile = {
  project_name?: string
  palette?: string
  line_style?: string
  lighting?: string
  view_rule?: string
  avoid_elements?: string
}

export type AssetParams = {
  name: string
  extra_prompt?: string
  asset_kind?: 'item_icon' | 'ui_component' | 'tile_texture' | 'game_logo' | 'dual_grid'
  subject_kind?: 'single_prop' | 'single_ui' | 'tileable_pattern' | 'logo_mark'
  texture_kind?: TextureKind
  use_vl?: boolean | null
  no_preview?: boolean
  material_a?: string
  material_b?: string
  material_a_texture_kind?: TextureKind
  material_b_texture_kind?: TextureKind
  transition_style?: DualGridTransitionStyle
}

export type SequenceFrameAlignment = {
  index: number
  offset_x: number
  offset_y: number
  scale?: number
}

export type SequenceAlignmentRequest = {
  frames: SequenceFrameAlignment[]
  fps?: number | null
  gif_export?: boolean
}

export type SpriteFrameOutput = {
  index: number
  row: number
  col: number
  path: string
  url: string | null
  raw_path?: string | null
  raw_url?: string | null
  reference_path?: string | null
  reference_url?: string | null
  sheet_rect?: { x: number; y: number; w: number; h: number } | null
  action_phase?: string | null
  bbox?: [number, number, number, number] | null
}

export type SizeRetryMode = 'attempts' | 'credits'

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
  source_only?: boolean
  size_retry_enabled?: boolean
  size_retry_mode?: SizeRetryMode
  size_retry_max_attempts?: number
  size_retry_max_credits?: number
  pixelize: PixelizeParams
  grid?: GridDesignParams
  style_profile?: StyleProfile
  sprite?: SpriteParams
  asset?: AssetParams
}

export type PromptPreviewResponse = {
  mode: string
  positive_prompt: string
  applied_style_profile: string[]
  warnings?: string[]
}

export type GridReadabilityIssue = {
  level: 'blocking' | 'warning' | string
  code: string
  message: string
}

export type GridReadabilityReport = {
  ok: boolean
  width: number
  height: number
  visible_pixels: number
  visible_ratio: number
  bbox: [number, number, number, number] | null
  bbox_coverage: number
  color_count: number
  component_count: number
  isolated_pixels: number
  outline_ratio: number
  highlight_ratio: number
  issues: GridReadabilityIssue[]
}

export type GridOutputStatus = {
  mode?: 'off' | 'extract' | string
  readability?: GridReadabilityReport | null
  ramp_info?: {
    source?: string
    vl_error?: string | null
  } | null
}

export type ContactSheetCandidate = {
  candidate_kind?: 'contact_sheet' | 'size_retry_attempt' | string
  index: number
  attempt?: number | null
  row: number
  col: number
  path: string
  url: string | null
  source_path?: string | null
  source_url?: string | null
  bbox?: [number, number, number, number] | null
  score?: number | null
  rank?: number | null
  reason?: string | null
  selected?: boolean
  matched?: boolean
  final_size?: [number, number] | null
  target_size?: [number, number] | null
  pixelized_path?: string | null
  pixelized_url?: string | null
  preview_path?: string | null
  preview_url?: string | null
  meta_json_path?: string | null
}

export type SpriteRowOutput = {
  row_index: number
  frame_indices: number[]
  action_phase: string
  sheet_path: string | null
  sheet_url: string | null
  gif_path: string | null
  gif_url: string | null
}

export type JobOutput = {
  run_dir: string
  source_path: string
  source_url: string | null
  contact_sheet_path: string | null
  contact_sheet_url: string | null
  candidates: ContactSheetCandidate[]
  sprite_sheet_path: string | null
  sprite_sheet_url: string | null
  sprite_mosaic_path?: string | null
  sprite_mosaic_url?: string | null
  sprite_sheet_grid_path?: string | null
  sprite_sheet_grid_url?: string | null
  sprite_grid?: { rows: number; cols: number } | null
  sprite_gif_path: string | null
  sprite_gif_url: string | null
  sprite_rows_outputs?: SpriteRowOutput[]
  sequence_json_path: string | null
  sequence_json_url: string | null
  sprite_frames: SpriteFrameOutput[]
  pixelized_path: string
  pixelized_url: string | null
  pixelized_size?: [number, number] | null
  preview_path: string | null
  preview_url: string | null
  dual_grid_atlas_path?: string | null
  dual_grid_atlas_url?: string | null
  dual_grid_preview_path?: string | null
  dual_grid_preview_url?: string | null
  analysis_json_path: string | null
  meta_json_path: string
  grid_json_path: string | null
  grid_status: GridOutputStatus | null
  grid_readability: GridReadabilityReport | null
  size_retry?: SizeRetryResult | null
}

export type SizeRetryResult = {
  enabled: boolean
  max_attempts: number
  actual_attempts: number
  matched: boolean
  expected_size: [number, number] | null
  actual_size: [number, number] | null
  target_size?: [number, number] | null
  final_size?: [number, number] | null
  attempts?: ContactSheetCandidate[]
  aspect_ratio_protocol?: boolean
}

export type JobBatchCreateResponse = {
  jobs: GenerationJob[]
  total_price_credits: number
  batch_id: number | null
}

export type JobBulkDeleteResponse = {
  deleted: boolean
  deleted_count: number
  job_ids: number[]
}

export type GenerationBatch = {
  id: number
  name: string
  mode: string
  status: string
  created_at: string
  updated_at: string
  job_count: number
  succeeded_count: number
  failed_count: number
  running_count: number
  pending_count: number
  total_price_credits: number
}

export type AssetPack = {
  id: number
  name: string
  status: string
  capacity: number
  item_count: number
  remaining_capacity: number
  created_at: string
  updated_at: string
}

export type AssetPackQuota = {
  pack_count: number
  pack_limit: number
  remaining_packs: number
  expand_price_credits: number
  pack_capacity: number
}

export type GalleryQuota = {
  retained_count: number
  retained_limit: number
  remaining_slots: number
  expand_price_credits: number
  expand_slots: number
}

export type JobShareSummary = {
  id: number
  status: 'pending' | 'active' | 'rejected' | 'hidden' | 'deleted' | string
  like_count: number
  download_count: number
  reward_credits: number
  review_note: string
  reviewed_at: string | null
  published_at: string | null
}

export type SharedDownloadOption = {
  kind: string
  label: string
  description: string
  url: string
  filename: string
}

export type SharedWorkStatus = 'pending' | 'active' | 'rejected' | 'hidden' | 'deleted' | string

export type SharedWork = {
  id: number
  job_id: number | null
  user_id: number
  status: SharedWorkStatus
  title: string
  asset_kind: string
  preview_url: string
  parameter_snapshot: Record<string, unknown>
  download_options: SharedDownloadOption[]
  like_count: number
  download_count: number
  reward_credits: number
  liked_by_me: boolean
  owned_by_me: boolean
  review_note: string
  reviewed_at: string | null
  published_at: string | null
  created_at: string
  updated_at: string
}

export type SharedWorkListResponse = {
  items: SharedWork[]
  total: number
  limit: number
  offset: number
}

export type AdminSharedWork = Omit<SharedWork, 'download_options' | 'liked_by_me' | 'owned_by_me'> & {
  user_email: string
  reviewed_by_user_id: number | null
}

export type AdminSharedWorkListResponse = {
  items: AdminSharedWork[]
  total: number
  limit: number
  offset: number
}

export type GenerationJob = {
  id: number
  user_id: number
  batch_id: number | null
  batch_name: string | null
  job_type: string
  status: JobStatus
  prompt: string | null
  input_image_path: string | null
  input_image_url: string | null
  sprite_reference_image_url?: string | null
  params_json: Record<string, unknown>
  price_credits: number
  reserved_credits: number
  error_message: string
  user_error_message?: string
  error_diagnostics_json?: Record<string, unknown>
  failure_type: string
  failure_source: string
  failure_code: string
  candidate_failure_count: number
  pipeline_warning_count: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  outputs: JobOutput[]
  share?: JobShareSummary | null
}

export type UploadResponse = {
  path: string
  url: string | null
  filename: string
  content_type: string
  size_bytes: number
}

export type CharacterItem = {
  id: number
  user_id: number
  source_job_id: number | null
  status: 'active' | 'archived' | string
  name: string
  description: string
  tags_json: unknown[]
  tags: string[]
  image_path: string
  image_url: string | null
  preview_path: string
  preview_url: string | null
  parameter_snapshot_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type CharacterCreatePayload = {
  name?: string
  description?: string
  tags?: string[]
  image_path: string
  preview_path?: string | null
}

export type CharacterFromJobPayload = {
  name?: string
  description?: string
  tags?: string[]
  image_kind?: 'source' | 'pixelized' | 'preview'
}

export type CharacterUpdatePayload = {
  name?: string
  description?: string
  tags?: string[]
  status?: 'active' | 'archived'
}

export type PricingRule = {
  key: string
  price_credits: number
  enabled: boolean
  updated_at: string
}

export type PricingDiscount = {
  active: boolean
  rate: number
  label: string
}

export type SettingType = 'string' | 'number' | 'boolean' | 'textarea' | 'select' | 'secret' | 'status'

export type PublicAnnouncement = {
  enabled: boolean
  title: string
  body: string
  updated_at: string | null
}

export type AnnouncementPublishPayload = {
  title: string
  body: string
  enabled: boolean
}

export type AnnouncementPublishResponse = PublicAnnouncement & {
  email_notification_queued: boolean
  email_recipient_count: number
  email_skipped_reason: 'unchanged' | 'disabled' | 'no_recipients' | string
}

export type AnnouncementItem = {
  id: number
  title: string
  body: string
  enabled: boolean
  published_at: string | null
  created_at: string
  updated_at: string
}

export type AnnouncementListResponse = {
  items: AnnouncementItem[]
  active_count: number
}

export type SystemSetting = {
  key: string
  value: string
  updated_at: string | null
  label: string
  category: string
  type: SettingType
  help: string
  options: string[]
  secret: boolean
  masked: boolean
  restart_required: boolean
  editable: boolean
  env_var: string
  source: 'database' | 'environment_only' | string
}

export type CreditPackage = {
  key: string
  name: string
  credits: number
  amount_cents: number
  currency: string
  enabled: boolean
  sort_order: number
}

export type CustomRechargeOptions = {
  min_credits: number
  max_credits: number
  currency: string
  unit_amount_cents_per_credit: number
  base_package_key: string | null
  base_package_credits: number
  base_package_amount_cents: number
  suggested_credits: number[]
}

export type RechargeRequest = {
  package_key?: string
  custom_credits?: number
  provider?: string
}

export type EmailTestResponse = {
  ok: boolean
  message: string
  debug_code?: string | null
}

export type PaymentOrder = {
  id: number
  provider: string
  provider_order_id: string
  status: string
  amount_cents: number
  currency: string
  credits: number
  created_at: string
  paid_at: string | null
}

export type PaymentCheckout = {
  order: PaymentOrder
  provider: string
  payment_url: string | null
  code_url: string | null
}

export type AdminDashboard = {
  total_users: number
  new_users_today: number
  active_users_today: number
  paying_users_today: number
  jobs_today: number
  succeeded_today: number
  failed_today: number
  policy_blocked_today: number
  upstream_errors_today: number
  timeout_jobs_today: number
  pipeline_errors_today: number
  pending_jobs: number
  running_jobs: number
  running_over_30m_jobs: number
  candidate_failures_today: number
  pipeline_warnings_today: number
  average_generation_seconds_today: number
  p95_generation_seconds_today: number
  credits_consumed_today: number
  credits_recharged_today: number
  orders_created_today?: number
  orders_paid_today: number
  uploads_today: number
  failure_rate: number
}

export type PerfKpi = { success_rate: number; running: number; total: number; failed: number; avg_seconds: number; p95_seconds: number }
export type PerfSeriesPoint = { t: string; succeeded: number; failed: number; total: number }
export type PerfProvider = { provider: string; display_name: string; enabled: boolean; priority: number; succeeded: number; failed: number; total: number; success_rate: number }
export type PerfFailure = { code: string; count: number }
export type PerfRecentJob = { id: number; job_type: string; status: string; provider: string; provider_display_name: string; failure_code: string; seconds: number; created_at: string }
export type PerformanceMetrics = { range: string; bucket_seconds: number; generated_at: string; kpi: PerfKpi; series: PerfSeriesPoint[]; providers: PerfProvider[]; failures: PerfFailure[]; recent: PerfRecentJob[] }

export interface ImageProviderModelPayload {
  id: string
  provider_model: string
  label: string
  protocol: string
  operations: string[]
  sizes: string[]
  qualities: string[]
  output_formats: string[]
  edit_mode: string
}

export interface ImageProvider {
  id: string
  display_name: string
  enabled: boolean
  base_url: string
  has_api_key: boolean
  api_key_env: string
  priority: number
  discover_models: boolean
  protocols: string[]
  models: ImageProviderModelPayload[]
  preset_key: string | null
}

export interface ImageProviderPreset {
  key: string
  display_name: string
  protocols: string[]
  base_url: string
  api_key_env: string
  discover_models: boolean
  models: ImageProviderModelPayload[]
  note: string
}

export interface ImageProviderCreatePayload {
  id: string
  display_name: string
  enabled: boolean
  base_url: string
  api_key: string
  api_key_env: string
  priority: number
  discover_models: boolean
  protocols: string[]
  models: ImageProviderModelPayload[]
  preset_key: string | null
}

export interface ImageProviderUpdatePayload {
  display_name: string
  enabled: boolean
  base_url: string
  api_key: string
  clear_api_key: boolean
  api_key_env: string
  priority: number
  discover_models: boolean
  protocols: string[]
  models: ImageProviderModelPayload[]
}
