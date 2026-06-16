import { useCallback } from 'react'
import { api } from '../api'
import type { AnnouncementItem, AnnouncementListResponse, AnnouncementPublishPayload, AnnouncementPublishResponse, GenerationJob, ImageProvider, ImageProviderPreset, ImageProviderCreatePayload, ImageProviderUpdatePayload } from '../types'
import type { ToastVariant } from '../components/AppOverlays'

type TextFn = (zh: string, en: string) => string

type AdminActionDeps = {
  token: string
  refreshCore: (activeToken?: string) => Promise<void>
  setMessage: (message: string, variant?: ToastVariant) => void
  text: TextFn
}

/**
 * 管理后台写操作：调点 / 价格 / 配置 / 公告 / 任务退款。
 * 这些操作沿用原有「不吞错误，向调用方冒泡」的约定（由 AdminPanel 内部处理），
 * state 仍由 App 持有，通过注入的 refreshCore 全量刷新。
 */
export function useAdminActions({ token, refreshCore, setMessage, text }: AdminActionDeps) {
  const adjustCredits = useCallback(async (userId: number, amount: number, note: string) => {
    if (!token) return
    await api.adjustCredits(token, userId, amount, note)
    await refreshCore(token)
    setMessage(text('点数已调整', 'Credits adjusted'))
  }, [token, refreshCore, setMessage, text])

  const adjustCreditsBatch = useCallback(async (payload: { userIds: number[]; allUsers: boolean; amount: number; note: string }) => {
    if (!token) return
    const result = await api.adjustCreditsBatch(token, {
      user_ids: payload.userIds,
      all_users: payload.allUsers,
      amount: payload.amount,
      note: payload.note,
    })
    await refreshCore(token)
    setMessage(text(`已为 ${result.adjusted_count} 个用户调整点数`, `Credits adjusted for ${result.adjusted_count} users`))
    return result
  }, [token, refreshCore, setMessage, text])

  const updatePricing = useCallback(async (key: string, priceCredits: number, enabled: boolean) => {
    if (!token) return
    await api.updatePricing(token, key, priceCredits, enabled)
    await refreshCore(token)
    setMessage(text('价格规则已更新', 'Pricing rule updated'))
  }, [token, refreshCore, setMessage, text])

  const updateSetting = useCallback(async (key: string, value: string, clear = false) => {
    if (!token) return
    await api.updateSetting(token, key, value, clear)
    await refreshCore(token)
    setMessage(text('配置已更新', 'Settings updated'))
  }, [token, refreshCore, setMessage, text])

  const testEmailSetting = useCallback(async (email: string) => {
    if (!token) return
    const result = await api.testEmailSetting(token, email)
    setMessage(result.debug_code ? `${result.message}：${result.debug_code}` : result.message, 'info')
  }, [token, setMessage])

  const adminRetryJob = useCallback(async (job: GenerationJob) => {
    if (!token || job.status !== 'failed') return
    const created = await api.adminRetryJob(token, job.id)
    setMessage(text(`管理员已重试任务 #${job.id}，新任务 #${created.id} 已提交。`, `Admin retried job #${job.id}; new job #${created.id} submitted.`))
    await refreshCore(token)
  }, [token, refreshCore, setMessage, text])

  const adminCancelJob = useCallback(async (job: GenerationJob) => {
    if (!token || !['pending', 'running'].includes(job.status)) return
    await api.adminCancelJob(token, job.id)
    setMessage(text(`任务 #${job.id} 已取消并退款。`, `Job #${job.id} cancelled and refunded.`))
    await refreshCore(token)
  }, [token, refreshCore, setMessage, text])

  const adminFailRefundJob = useCallback(async (job: GenerationJob) => {
    if (!token || !['pending', 'running', 'failed'].includes(job.status)) return
    await api.adminFailRefundJob(token, job.id)
    setMessage(text(`任务 #${job.id} 已标记失败并退款。`, `Job #${job.id} marked failed and refunded.`))
    await refreshCore(token)
  }, [token, refreshCore, setMessage, text])

  const publishAnnouncement = useCallback(async (payload: AnnouncementPublishPayload): Promise<AnnouncementPublishResponse> => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    const result = await api.publishAnnouncement(token, payload)
    await refreshCore(token)
    return result
  }, [refreshCore, text, token])

  const adminAnnouncements = useCallback(async (): Promise<AnnouncementListResponse> => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    return api.adminAnnouncements(token)
  }, [text, token])

  const createAnnouncement = useCallback(async (payload: { title: string; body: string; enabled: boolean; publish_now: boolean; notify: boolean }): Promise<AnnouncementItem> => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    const result = await api.createAnnouncement(token, payload)
    await refreshCore(token)
    return result
  }, [refreshCore, text, token])

  const updateAnnouncement = useCallback(async (id: number, payload: { title?: string; body?: string; enabled?: boolean }): Promise<AnnouncementItem> => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    const result = await api.updateAnnouncement(token, id, payload)
    await refreshCore(token)
    return result
  }, [refreshCore, text, token])

  const deleteAnnouncement = useCallback(async (id: number) => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    const result = await api.deleteAnnouncement(token, id)
    await refreshCore(token)
    return result
  }, [refreshCore, text, token])

  const testAnnouncementEmail = useCallback(async (email: string, title: string, body: string) => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    return api.testAnnouncementEmail(token, { email, title, body })
  }, [text, token])

  const listProviders = useCallback(async (): Promise<ImageProvider[]> => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    return api.adminProviders(token)
  }, [text, token])

  const listProviderPresets = useCallback(async (): Promise<ImageProviderPreset[]> => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    return api.adminProviderPresets(token)
  }, [text, token])

  const createProvider = useCallback(async (payload: ImageProviderCreatePayload) => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    await api.createAdminProvider(token, payload)
    await refreshCore(token)
    setMessage(text('供应商已新增', 'Provider created'))
  }, [refreshCore, setMessage, text, token])

  const updateProvider = useCallback(async (id: string, payload: ImageProviderUpdatePayload) => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    await api.updateAdminProvider(token, id, payload)
    await refreshCore(token)
    setMessage(text('供应商已更新', 'Provider updated'))
  }, [refreshCore, setMessage, text, token])

  const deleteProvider = useCallback(async (id: string) => {
    if (!token) throw new Error(text('请先登录', 'Please sign in first'))
    await api.deleteAdminProvider(token, id)
    await refreshCore(token)
    setMessage(text('供应商已删除', 'Provider deleted'))
  }, [refreshCore, setMessage, text, token])

  return { adjustCredits, adjustCreditsBatch, updatePricing, updateSetting, testEmailSetting, adminRetryJob, adminCancelJob, adminFailRefundJob, publishAnnouncement, adminAnnouncements, createAnnouncement, updateAnnouncement, deleteAnnouncement, testAnnouncementEmail, listProviders, listProviderPresets, createProvider, updateProvider, deleteProvider }
}
