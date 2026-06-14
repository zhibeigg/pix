import { useCallback } from 'react'
import { api } from '../api'
import type { CreditPackage, PaymentCheckout } from '../types'
import type { ToastVariant } from '../components/AppOverlays'

type TextFn = (zh: string, en: string) => string

type BillingActionDeps = {
  token: string
  refreshCore: (activeToken?: string) => Promise<void>
  setMessage: (message: string, variant?: ToastVariant) => void
  showError: (error: unknown) => void
  text: TextFn
  setCheckout: (checkout: PaymentCheckout | null) => void
}

/**
 * 充值 / 订单 / 套餐写操作。state（balance/orders/checkout/packages 等）仍由 App 持有，
 * 操作通过注入的 refreshCore 全量刷新，保持与既有数据流一致。
 */
export function useBillingActions({ token, refreshCore, setMessage, showError, text, setCheckout }: BillingActionDeps) {
  const createPaymentOrder = useCallback(async (packageKey: string) => {
    if (!token) return
    try {
      const order = await api.createOrder(token, { package_key: packageKey, provider: 'mock' })
      setCheckout(null)
      await refreshCore(token)
      setMessage(text(`订单 #${order.id} 已创建`, `Order #${order.id} created`))
    } catch (error) {
      showError(error)
    }
  }, [token, refreshCore, setMessage, showError, text, setCheckout])

  const startCheckout = useCallback(async (packageKey: string, provider: string) => {
    if (!token) return
    try {
      const result = await api.checkout(token, { package_key: packageKey, provider })
      setCheckout(result)
      if (result.payment_url) {
        window.open(result.payment_url, '_blank', 'noopener,noreferrer')
      }
      await refreshCore(token)
      setMessage(text(`订单 #${result.order.id} 已创建：${provider}`, `Order #${result.order.id} created: ${provider}`))
    } catch (error) {
      showError(error)
    }
  }, [token, refreshCore, setMessage, showError, text, setCheckout])

  const createCustomPaymentOrder = useCallback(async (customCredits: number) => {
    if (!token) return
    try {
      const order = await api.createOrder(token, { custom_credits: customCredits, provider: 'mock' })
      setCheckout(null)
      await refreshCore(token)
      setMessage(text(`自定义订单 #${order.id} 已创建`, `Custom order #${order.id} created`))
    } catch (error) {
      showError(error)
    }
  }, [token, refreshCore, setMessage, showError, text, setCheckout])

  const startCustomCheckout = useCallback(async (customCredits: number, provider: string) => {
    if (!token) return
    try {
      const result = await api.checkout(token, { custom_credits: customCredits, provider })
      setCheckout(result)
      if (result.payment_url) {
        window.open(result.payment_url, '_blank', 'noopener,noreferrer')
      }
      await refreshCore(token)
      setMessage(text(`自定义订单 #${result.order.id} 已创建：${provider}`, `Custom order #${result.order.id} created: ${provider}`))
    } catch (error) {
      showError(error)
    }
  }, [token, refreshCore, setMessage, showError, text, setCheckout])

  const mockPayPaymentOrder = useCallback(async (orderId: number) => {
    if (!token) return
    try {
      await api.mockPayOrder(token, orderId)
      await refreshCore(token)
      setMessage(text('模拟支付成功，点数已到账', 'Mock payment succeeded; credits received'))
    } catch (error) {
      showError(error)
    }
  }, [token, refreshCore, setMessage, showError, text])

  const createAdminPackage = useCallback(async (payload: CreditPackage) => {
    if (!token) return
    await api.createAdminPackage(token, payload)
    await refreshCore(token)
    setMessage(text('充值套餐已创建', 'Credit package created'))
  }, [token, refreshCore, setMessage, text])

  const updateAdminPackage = useCallback(async (key: string, payload: Omit<CreditPackage, 'key'>) => {
    if (!token) return
    await api.updateAdminPackage(token, key, payload)
    await refreshCore(token)
    setMessage(text('充值套餐已更新', 'Credit package updated'))
  }, [token, refreshCore, setMessage, text])

  return { createPaymentOrder, startCheckout, createCustomPaymentOrder, startCustomCheckout, mockPayPaymentOrder, createAdminPackage, updateAdminPackage }
}
