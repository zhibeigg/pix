import type {
  CreditBalance,
  CreditTransaction,
  GenerationJob,
  JobCreateRequest,
  PricingRule,
  TokenResponse,
  User,
} from './types'

export const API_BASE = import.meta.env.VITE_PIX_API_BASE ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const text = await response.text()
  const body = text ? JSON.parse(text) : null
  if (!response.ok) {
    const message = typeof body?.detail === 'string' ? body.detail : `请求失败 (${response.status})`
    throw new ApiError(message, response.status, body)
  }
  return body as T
}

export const api = {
  register(email: string, password: string, displayName: string) {
    return request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName }),
    })
  },
  login(email: string, password: string) {
    return request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
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
  createJob(token: string, payload: JobCreateRequest) {
    return request<GenerationJob>('/jobs', { method: 'POST', body: JSON.stringify(payload) }, token)
  },
  jobs(token: string) {
    return request<GenerationJob[]>('/jobs?limit=50', {}, token)
  },
  adminUsers(token: string) {
    return request<User[]>('/admin/users?limit=100', {}, token)
  },
  adjustCredits(token: string, userId: number, amount: number, note: string) {
    return request<CreditTransaction>(
      `/admin/users/${userId}/adjust-credits`,
      { method: 'POST', body: JSON.stringify({ amount, note }) },
      token,
    )
  },
  pricing(token: string) {
    return request<PricingRule[]>('/admin/pricing', {}, token)
  },
  updatePricing(token: string, key: string, priceCredits: number, enabled: boolean) {
    return request<PricingRule>(
      `/admin/pricing/${key}`,
      { method: 'PUT', body: JSON.stringify({ price_credits: priceCredits, enabled }) },
      token,
    )
  },
}
