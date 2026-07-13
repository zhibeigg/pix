import type {
  AdminDashboard,
  AdminDashboardQueryParams,
  AdminPaymentOrder,
  AdminSharedWork,
  AdminSharedWorkListResponse,
  PerformanceMetrics,
  ApiKeyCreatePayload,
  ApiKeyCreateResponse,
  ApiKeyItem,
  ApiKeyUpdatePayload,
  AnnouncementItem,
  AnnouncementListResponse,
  AnnouncementPublishPayload,
  AnnouncementPublishResponse,
  AssetPack,
  AssetPackQuota,
  CharacterCreatePayload,
  CharacterFromJobPayload,
  CharacterItem,
  CharacterUpdatePayload,
  CreditBalance,
  AdminBatchAdjustCreditsResponse,
  GenerationBatch,
  CreditTransaction,
  SequenceAlignmentRequest,
  GalleryQuota,
  GenerationJob,
  ImageModelsResponse,
  JobBatchCreateResponse,
  JobBulkDeleteResponse,
  JobCreateRequest,
  EmailTestResponse,
  PaymentCheckout,
  PaymentOrder,
  PricingRule,
  PricingDiscount,
  PromoLink,
  PromoLinkInfo,
  PromoLinkPayload,
  PromoLinkStats,
  PromptPreviewResponse,
  PublicAnnouncement,
  ReferralSettlement,
  ReferralSummary,
  CreditPackage,
  CustomRechargeOptions,
  MembershipPlan,
  UserMembership,
  RechargeRequest,
  SystemSetting,
  SetupStatus,
  SharedWork,
  SharedWorkListResponse,
  UploadResponse,
  User,
  EmailCodeResponse,
  ImageProvider,
  ImageProviderPreset,
  ImageProviderCreatePayload,
  ImageProviderUpdatePayload,
  AdminUpdateStatus,
  UpdateStepUpResponse,
  UpdateOperation,
} from './types'

const configuredApiBase = (import.meta.env.VITE_PIX_API_BASE as string | undefined)?.trim()
const configuredTimeout = Number(import.meta.env.VITE_PIX_API_TIMEOUT_MS ?? 15000)
const API_TIMEOUT_MS = Number.isFinite(configuredTimeout) && configuredTimeout > 0 ? configuredTimeout : 15000

function normalizeLocalApiBase(base: string) {
  if (base !== '/api' || typeof window === 'undefined') return base
  const { hostname, port, protocol } = window.location
  if (!['127.0.0.1', '::1', '[::1]'].includes(hostname)) return base
  return `${protocol}//localhost${port ? `:${port}` : ''}/api`
}

export const API_BASE = normalizeLocalApiBase((configuredApiBase || '/api').replace(/\/+$/, ''))
export const SESSION_AUTH_MARKER = 'cookie-session'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.status = status
    this.body = body
  }
}

function apiUrl(path: string) {
  return `${API_BASE}${path}`
}

function apiLocationLabel() {
  return API_BASE || '当前站点'
}

function networkApiError(error: unknown): ApiError {
  const detail = error instanceof Error ? error.message : String(error)
  const timeoutHint = error instanceof DOMException && error.name === 'AbortError' ? `请求超过 ${Math.round(API_TIMEOUT_MS / 1000)} 秒未响应。` : ''
  return new ApiError(
    `${timeoutHint}无法连接 Pix API（${apiLocationLabel()}）。请确认后端服务已启动，并检查 VITE_PIX_API_BASE、/api 反向代理或 CORS 允许域名配置。`,
    0,
    { detail },
  )
}

function parseResponseBody(text: string): unknown {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function responseErrorMessage(body: unknown, status: number): string {
  const detail = typeof body === 'object' && body && 'detail' in body ? (body as { detail?: unknown }).detail : null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (typeof item === 'string') return [item]
      if (!item || typeof item !== 'object') return []
      const record = item as { loc?: unknown; msg?: unknown; message?: unknown }
      const loc = Array.isArray(record.loc) ? record.loc.filter((part) => part !== 'body').join('.') : ''
      const msg = typeof record.msg === 'string' ? record.msg : typeof record.message === 'string' ? record.message : ''
      return msg ? [`${loc ? `${loc}: ` : ''}${msg}`] : []
    })
    if (messages.length > 0) return messages.slice(0, 3).join('；')
  }
  if (typeof body === 'string' && body.trim()) return body
  return `请求失败 (${status})`
}

async function request<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token && token !== SESSION_AUTH_MARKER) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      ...options,
      credentials: options.credentials ?? 'include',
      headers,
      signal: options.signal ?? controller.signal,
    })
  } catch (error) {
    throw networkApiError(error)
  } finally {
    window.clearTimeout(timeoutId)
  }
  const text = await response.text()
  const body = parseResponseBody(text)
  if (!response.ok) {
    throw new ApiError(responseErrorMessage(body, response.status), response.status, body)
  }
  return body as T
}

async function downloadBlob(path: string, token: string, options: RequestInit = {}): Promise<Blob> {
  let response: Response
  try {
    const headers = new Headers(options.headers)
    if (token && token !== SESSION_AUTH_MARKER) headers.set('Authorization', `Bearer ${token}`)
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    response = await fetch(apiUrl(path), {
      ...options,
      credentials: options.credentials ?? 'include',
      headers,
    })
  } catch (error) {
    throw networkApiError(error)
  }
  if (!response.ok) {
    const text = await response.text()
    const body = parseResponseBody(text)
    throw new ApiError(responseErrorMessage(body, response.status), response.status, body)
  }
  return response.blob()
}

export const api = {
  setupStatus() {
    return request<SetupStatus>('/auth/setup-status')
  },
  bootstrapAdmin(email: string, password: string, displayName: string) {
    return request<User>('/auth/session/bootstrap-admin', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName }),
    })
  },
  requestRegisterCode(email: string, turnstileToken = '') {
    return request<EmailCodeResponse>('/auth/register-code', {
      method: 'POST',
      body: JSON.stringify({ email, turnstile_token: turnstileToken }),
    })
  },
  register(email: string, password: string, displayName: string, verificationCode: string, referralCode = '', promoCode = '') {
    return request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName, verification_code: verificationCode, referral_code: referralCode, promo_code: promoCode }),
    })
  },
  promoInfo(code: string) {
    return request<PromoLinkInfo>(`/pricing/promo/${encodeURIComponent(code)}`)
  },
  login(email: string, password: string) {
    return request<User>('/auth/session/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },
  requestResetCode(email: string, turnstileToken = '') {
    return request<EmailCodeResponse>('/auth/reset-code', {
      method: 'POST',
      body: JSON.stringify({ email, turnstile_token: turnstileToken }),
    })
  },
  resetPassword(email: string, newPassword: string, verificationCode: string) {
    return request<User>('/auth/session/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, new_password: newPassword, verification_code: verificationCode }),
    })
  },
  localTestLogin() {
    return request<User>('/auth/session/local-test-login', { method: 'POST' })
  },
  logout() {
    return request<void>('/auth/session/logout', { method: 'POST' })
  },
  me(token: string) {
    return request<User>('/auth/me', {}, token)
  },
  balance(token: string) {
    return request<CreditBalance>('/credits/balance', {}, token)
  },
  transactions(token: string) {
    return request<CreditTransaction[]>('/credits/transactions?limit=20', {}, token)
  },
  apiKeys(token: string) {
    return request<ApiKeyItem[]>('/api-keys', {}, token)
  },
  createApiKey(token: string, payload: ApiKeyCreatePayload) {
    return request<ApiKeyCreateResponse>('/api-keys', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateApiKey(token: string, keyId: number, payload: ApiKeyUpdatePayload) {
    return request<ApiKeyItem>(`/api-keys/${keyId}`, { method: 'PATCH', body: JSON.stringify(payload) }, token)
  },
  revokeApiKey(token: string, keyId: number) {
    return request<ApiKeyItem>(`/api-keys/${keyId}`, { method: 'DELETE' }, token)
  },
  packages() {
    return request<CreditPackage[]>('/billing/packages')
  },
  membershipPlans() {
    return request<MembershipPlan[]>('/membership/plans')
  },
  myMembership(token: string) {
    return request<UserMembership>('/membership/me', {}, token)
  },
  membershipCheckout(token: string, planKey: string, provider: string) {
    return request<PaymentCheckout>('/membership/checkout', {
      method: 'POST',
      body: JSON.stringify({ plan_key: planKey, provider }),
    }, token)
  },
  currentAnnouncement() {
    return request<PublicAnnouncement>('/announcements/current')
  },
  announcements() {
    return request<AnnouncementListResponse>('/announcements/list')
  },
  customRechargeOptions() {
    return request<CustomRechargeOptions>('/billing/custom-recharge-options')
  },
  createOrder(token: string, payload: RechargeRequest) {
    return request<PaymentOrder>('/billing/orders', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  checkout(token: string, payload: RechargeRequest) {
    return request<PaymentCheckout>('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, token)
  },
  orders(token: string) {
    return request<PaymentOrder[]>('/billing/orders?limit=20', {}, token)
  },
  mockPayOrder(token: string, orderId: number) {
    return request<PaymentOrder>(`/billing/mock-pay/${orderId}`, { method: 'POST' }, token)
  },
  referralSummary(token: string) {
    return request<ReferralSummary>('/referrals/summary', {}, token)
  },
  transferReferralRewards(token: string, currency: string) {
    return request<ReferralSettlement>('/referrals/transfer', { method: 'POST', body: JSON.stringify({ currency }) }, token)
  },
  withdrawReferralRewards(token: string, amountCents: number, currency: string, note = '') {
    return request<ReferralSettlement>('/referrals/withdrawals', { method: 'POST', body: JSON.stringify({ amount_cents: amountCents, currency, note }) }, token)
  },
  uploadImage(token: string, file: File) {
    const form = new FormData()
    form.set('file', file)
    return request<UploadResponse>('/uploads/image', { method: 'POST', body: form }, token)
  },
  createJob(token: string, payload: JobCreateRequest) {
    return request<GenerationJob>('/jobs', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  promptPreview(token: string, payload: JobCreateRequest) {
    return request<PromptPreviewResponse>('/jobs/prompt-preview', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  retryJob(token: string, jobId: number) {
    return request<GenerationJob>(`/jobs/${jobId}/retry`, { method: 'POST' }, token)
  },
  regenerateJob(token: string, jobId: number) {
    return request<GenerationJob>(`/jobs/${jobId}/regenerate`, { method: 'POST' }, token)
  },
  saveSequenceAlignment(token: string, jobId: number, payload: SequenceAlignmentRequest) {
    return request<GenerationJob>(`/jobs/${jobId}/sequence-alignment`, { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  deleteJob(token: string, jobId: number) {
    return request<{ deleted: boolean }>(`/jobs/${jobId}`, { method: 'DELETE' }, token)
  },
  deleteJobs(token: string, jobIds: number[]) {
    return request<JobBulkDeleteResponse>('/jobs/bulk-delete', { method: 'POST', body: JSON.stringify({ job_ids: jobIds }) }, token)
  },
  bulkDownloadJobs(token: string, jobIds: number[]) {
    return downloadBlob('/jobs/bulk-download', token, { method: 'POST', body: JSON.stringify({ job_ids: jobIds }) })
  },
  createJobsBatch(token: string, payloads: JobCreateRequest[], batchName = '', mode = 'mixed') {
    return request<JobBatchCreateResponse>('/jobs/batch', { method: 'POST', body: JSON.stringify({ jobs: payloads, batch_name: batchName, mode }) }, token)
  },
  jobs(token: string) {
    return request<GenerationJob[]>('/jobs?limit=50', {}, token)
  },
  characters(token: string) {
    return request<CharacterItem[]>('/characters?limit=100', {}, token)
  },
  createCharacter(token: string, payload: CharacterCreatePayload) {
    return request<CharacterItem>('/characters', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  createCharacterFromJob(token: string, jobId: number, payload: CharacterFromJobPayload = {}) {
    return request<CharacterItem>(`/characters/jobs/${jobId}`, { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateCharacter(token: string, characterId: number, payload: CharacterUpdatePayload) {
    return request<CharacterItem>(`/characters/${characterId}`, { method: 'PATCH', body: JSON.stringify(payload) }, token)
  },
  deleteCharacter(token: string, characterId: number) {
    return request<{ deleted: boolean }>(`/characters/${characterId}`, { method: 'DELETE' }, token)
  },
  galleryQuota(token: string) {
    return request<GalleryQuota>('/jobs/gallery-quota', {}, token)
  },
  expandGalleryQuota(token: string) {
    return request<GalleryQuota>('/jobs/gallery-quota/expand', { method: 'POST' }, token)
  },
  sharedWorks(token?: string | null, params: { limit?: number; offset?: number; assetKind?: string; outputSize?: string; imageModel?: string } = {}) {
    const search = new URLSearchParams()
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    if (params.assetKind) search.set('asset_kind', params.assetKind)
    if (params.outputSize) search.set('output_size', params.outputSize)
    if (params.imageModel) search.set('image_model', params.imageModel)
    const query = search.toString()
    return request<SharedWorkListResponse>(`/shares${query ? `?${query}` : ''}`, {}, token)
  },
  publishJobShare(token: string, jobId: number) {
    return request<SharedWork>(`/shares/jobs/${jobId}/publish`, { method: 'POST' }, token)
  },
  unpublishShare(token: string, shareId: number) {
    return request<SharedWork>(`/shares/${shareId}/unpublish`, { method: 'POST' }, token)
  },
  likeShare(token: string, shareId: number) {
    return request<SharedWork>(`/shares/${shareId}/like`, { method: 'POST' }, token)
  },
  unlikeShare(token: string, shareId: number) {
    return request<SharedWork>(`/shares/${shareId}/like`, { method: 'DELETE' }, token)
  },
  batches(token: string) {
    return request<GenerationBatch[]>('/batches?limit=50', {}, token)
  },
  packs(token: string) {
    return request<AssetPack[]>('/packs?limit=100', {}, token)
  },
  packQuota(token: string) {
    return request<AssetPackQuota>('/packs/quota', {}, token)
  },
  createPack(token: string, name: string) {
    return request<AssetPack>('/packs', { method: 'POST', body: JSON.stringify({ name }) }, token)
  },
  updatePack(token: string, packId: number, payload: { name?: string; status?: string }) {
    return request<AssetPack>(`/packs/${packId}`, { method: 'PATCH', body: JSON.stringify(payload) }, token)
  },
  deletePack(token: string, packId: number) {
    return request<{ deleted: boolean }>(`/packs/${packId}`, { method: 'DELETE' }, token)
  },
  packJobs(token: string, packId: number) {
    return request<GenerationJob[]>(`/packs/${packId}/jobs`, {}, token)
  },
  addJobToPack(token: string, packId: number, jobId: number) {
    return request<AssetPack>(`/packs/${packId}/items`, { method: 'POST', body: JSON.stringify({ job_id: jobId }) }, token)
  },
  removeJobFromPack(token: string, packId: number, jobId: number) {
    return request<AssetPack>(`/packs/${packId}/items/${jobId}`, { method: 'DELETE' }, token)
  },
  expandPackLimit(token: string) {
    return request<AssetPackQuota>('/packs/expand', { method: 'POST' }, token)
  },
  downloadPack(token: string, packId: number) {
    return downloadBlob(`/packs/${packId}/download`, token)
  },
  batchJobs(token: string, batchId: number) {
    return request<GenerationJob[]>(`/batches/${batchId}/jobs`, {}, token)
  },
  retryFailedBatch(token: string, batchId: number) {
    return request<JobBatchCreateResponse>(`/batches/${batchId}/retry-failed`, { method: 'POST' }, token)
  },
  downloadBatch(token: string, batchId: number) {
    return downloadBlob(`/batches/${batchId}/download`, token)
  },
  updateBatch(token: string, batchId: number, payload: { name?: string; status?: string }) {
    return request<GenerationBatch>(`/batches/${batchId}`, { method: 'PATCH', body: JSON.stringify(payload) }, token)
  },
  deleteBatch(token: string, batchId: number) {
    return request<{ deleted: boolean }>(`/batches/${batchId}`, { method: 'DELETE' }, token)
  },
  adminDashboard(token: string, params?: AdminDashboardQueryParams) {
    const search = new URLSearchParams()
    if (params) {
      search.set('range', params.range)
      search.set('granularity', params.granularity)
      search.set('compare', String(params.compare))
      if (params.range === 'custom' && params.from) search.set('from', params.from)
      if (params.range === 'custom' && params.to) search.set('to', params.to)
    }
    const query = search.toString()
    return request<AdminDashboard>(`/admin/dashboard${query ? `?${query}` : ''}`, {}, token)
  },
  adminUsers(token: string) {
    return request<User[]>('/admin/users?limit=500', {}, token)
  },
  adminJobs(token: string) {
    return request<GenerationJob[]>('/admin/jobs?limit=500', {}, token)
  },
  adminOrders(token: string) {
    return request<AdminPaymentOrder[]>('/admin/orders?limit=500', {}, token)
  },
  adminListShares(token: string, params: { status?: string; limit?: number; offset?: number } = {}) {
    const search = new URLSearchParams()
    search.set('status', params.status ?? 'pending')
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    const query = search.toString()
    return request<AdminSharedWorkListResponse>(`/admin/shares${query ? `?${query}` : ''}`, {}, token)
  },
  approveShare(token: string, shareId: number) {
    return request<AdminSharedWork>(`/admin/shares/${shareId}/approve`, { method: 'POST' }, token)
  },
  rejectShare(token: string, shareId: number, note: string) {
    return request<AdminSharedWork>(`/admin/shares/${shareId}/reject`, { method: 'POST', body: JSON.stringify({ note }) }, token)
  },
  adminUnpublishShare(token: string, shareId: number) {
    return request<AdminSharedWork>(`/admin/shares/${shareId}/unpublish`, { method: 'POST' }, token)
  },
  deleteAdminShare(token: string, shareId: number) {
    return request<{ deleted: boolean }>(`/admin/shares/${shareId}`, { method: 'DELETE' }, token)
  },
  performanceMetrics(token: string, range: string) {
    return request<PerformanceMetrics>(`/admin/performance-metrics?range=${encodeURIComponent(range)}`, {}, token)
  },
  adminRetryJob(token: string, jobId: number) {
    return request<GenerationJob>(`/admin/jobs/${jobId}/retry`, { method: 'POST' }, token)
  },
  adminCancelJob(token: string, jobId: number) {
    return request<GenerationJob>(`/admin/jobs/${jobId}/cancel`, { method: 'POST' }, token)
  },
  adminFailRefundJob(token: string, jobId: number) {
    return request<GenerationJob>(`/admin/jobs/${jobId}/fail-refund`, { method: 'POST' }, token)
  },
  adjustCredits(token: string, userId: number, amount: number, note: string) {
    return request<CreditTransaction>(
      `/admin/users/${userId}/adjust-credits`,
      { method: 'POST', body: JSON.stringify({ amount, note }) },
      token,
    )
  },
  adjustCreditsBatch(token: string, payload: { user_ids?: number[]; all_users?: boolean; amount: number; note: string }) {
    return request<AdminBatchAdjustCreditsResponse>(
      '/admin/users/adjust-credits-batch',
      { method: 'POST', body: JSON.stringify(payload) },
      token,
    )
  },
  pricing(token?: string | null) {
    return request<PricingRule[]>('/pricing', {}, token)
  },
  pricingDiscount(token?: string | null) {
    return request<PricingDiscount>('/pricing/discount', {}, token)
  },
  imageModels() {
    return request<ImageModelsResponse>('/settings/image-models')
  },
  adminPricing(token: string) {
    return request<PricingRule[]>('/admin/pricing', {}, token)
  },
  updatePricing(token: string, key: string, priceCredits: number, enabled: boolean) {
    return request<PricingRule>(
      `/admin/pricing/${key}`,
      { method: 'PUT', body: JSON.stringify({ price_credits: priceCredits, enabled }) },
      token,
    )
  },
  adminPackages(token: string) {
    return request<CreditPackage[]>('/admin/packages', {}, token)
  },
  createAdminPackage(token: string, payload: CreditPackage) {
    return request<CreditPackage>('/admin/packages', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateAdminPackage(token: string, key: string, payload: Omit<CreditPackage, 'key'>) {
    return request<CreditPackage>(`/admin/packages/${key}`, { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  adminMembershipPlans(token: string) {
    return request<MembershipPlan[]>('/admin/membership-plans', {}, token)
  },
  createAdminMembershipPlan(token: string, payload: MembershipPlan) {
    return request<MembershipPlan>('/admin/membership-plans', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateAdminMembershipPlan(token: string, key: string, payload: Omit<MembershipPlan, 'key'>) {
    return request<MembershipPlan>(`/admin/membership-plans/${key}`, { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  adminPromoLinks(token: string) {
    return request<PromoLinkStats[]>('/admin/promo-links', {}, token)
  },
  createAdminPromoLink(token: string, payload: PromoLinkPayload) {
    return request<PromoLink>('/admin/promo-links', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateAdminPromoLink(token: string, id: number, payload: Omit<PromoLinkPayload, 'code'>) {
    return request<PromoLink>(`/admin/promo-links/${id}`, { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  deleteAdminPromoLink(token: string, id: number) {
    return request<{ deleted: boolean }>(`/admin/promo-links/${id}`, { method: 'DELETE' }, token)
  },
  adminSettings(token: string) {
    return request<SystemSetting[]>('/admin/settings', {}, token)
  },
  updateSetting(token: string, key: string, value: string, clear = false) {
    return request<SystemSetting>(`/admin/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value, clear }) }, token)
  },
  publishAnnouncement(token: string, payload: AnnouncementPublishPayload) {
    return request<AnnouncementPublishResponse>('/admin/announcement', { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  adminAnnouncements(token: string) {
    return request<AnnouncementListResponse>('/admin/announcements', {}, token)
  },
  createAnnouncement(token: string, payload: { title: string; body: string; enabled: boolean; publish_now: boolean; notify: boolean }) {
    return request<AnnouncementItem>('/admin/announcements', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateAnnouncement(token: string, id: number, payload: { title?: string; body?: string; enabled?: boolean }) {
    return request<AnnouncementItem>(`/admin/announcements/${id}`, { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  deleteAnnouncement(token: string, id: number) {
    return request<{ deleted: boolean }>(`/admin/announcements/${id}`, { method: 'DELETE' }, token)
  },
  testAnnouncementEmail(token: string, payload: { email: string; title: string; body: string }) {
    return request<EmailTestResponse>('/admin/announcements/test-email', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  testEmailSetting(token: string, email: string) {
    return request<EmailTestResponse>('/admin/settings/test-email', { method: 'POST', body: JSON.stringify({ email }) }, token)
  },
  adminProviders(token: string) {
    return request<ImageProvider[]>('/admin/providers', {}, token)
  },
  adminProviderPresets(token: string) {
    return request<ImageProviderPreset[]>('/admin/providers/presets', {}, token)
  },
  createAdminProvider(token: string, payload: ImageProviderCreatePayload) {
    return request<ImageProvider>('/admin/providers', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  updateAdminProvider(token: string, id: string, payload: ImageProviderUpdatePayload) {
    return request<ImageProvider>(`/admin/providers/${id}`, { method: 'PUT', body: JSON.stringify(payload) }, token)
  },
  deleteAdminProvider(token: string, id: string) {
    return request<{ deleted: boolean }>(`/admin/providers/${id}`, { method: 'DELETE' }, token)
  },
  adminUpdateStatus(token: string) {
    return request<AdminUpdateStatus>('/admin/updates/status', {}, token)
  },
  checkAdminUpdates(token: string) {
    return request<AdminUpdateStatus>('/admin/updates/check', { method: 'POST' }, token)
  },
  stepUpAdminUpdate(token: string, password: string) {
    return request<UpdateStepUpResponse>('/auth/session/step-up-update', { method: 'POST', body: JSON.stringify({ password }) }, token)
  },
  applyAdminUpdate(token: string, payload: { target_version: string; expected_manifest_sha256: string; idempotency_key: string }) {
    return request<AdminUpdateStatus>('/admin/updates/apply', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  adminUpdateOperation(token: string, operationId: string) {
    return request<UpdateOperation>(`/admin/updates/operations/${encodeURIComponent(operationId)}`, {}, token)
  },
  rollbackAdminUpdate(token: string, idempotencyKey: string) {
    return request<AdminUpdateStatus>('/admin/updates/rollback', { method: 'POST', body: JSON.stringify({ idempotency_key: idempotencyKey }) }, token)
  },
}
