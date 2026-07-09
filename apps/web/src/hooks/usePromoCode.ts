import { useEffect, useState } from 'react'

// 优惠码：只信任当前 URL 的 ?promo=xxx，与邀请码（?aff=）独立并存。
// 不做持久化，避免老用户每次进站都被误判为带优惠。
export function promoCodeFromLocation() {
  const candidates: string[] = []
  if (typeof window === 'undefined') return ''
  candidates.push(new URLSearchParams(window.location.search).get('promo') ?? '')
  const hash = window.location.hash || ''
  const queryIndex = hash.indexOf('?')
  if (queryIndex >= 0) candidates.push(new URLSearchParams(hash.slice(queryIndex + 1)).get('promo') ?? '')
  return candidates.map((item) => item.trim().toUpperCase()).find(Boolean) ?? ''
}

/**
 * 优惠码：启动时从当前 URL 读取 ?promo=xxx。
 * 通过该链接注册的用户会永久绑定优惠码，之后所有充值/月卡按折扣计费。
 */
export function usePromoCode() {
  const [promoCode, setPromoCode] = useState(() => promoCodeFromLocation())

  useEffect(() => {
    const fromUrl = promoCodeFromLocation()
    if (!fromUrl) return
    setPromoCode(fromUrl)
  }, [])

  return { promoCode, setPromoCode }
}
