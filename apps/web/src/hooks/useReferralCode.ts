import { useEffect, useState } from 'react'

// 历史版本曾把邀请码持久化到 localStorage，会导致用户即使从普通 URL 进来也一直被"识别"为邀请。
// 现在改为只信任当前 URL 的 ?aff=xxx，并在启动时清理历史残留。
export const LEGACY_REFERRAL_CODE_KEY = 'pix_referral_code'

export function referralCodeFromLocation() {
  const candidates: string[] = []
  if (typeof window === 'undefined') return ''
  candidates.push(new URLSearchParams(window.location.search).get('aff') ?? '')
  const hash = window.location.hash || ''
  const queryIndex = hash.indexOf('?')
  if (queryIndex >= 0) candidates.push(new URLSearchParams(hash.slice(queryIndex + 1)).get('aff') ?? '')
  return candidates.map((item) => item.trim().toUpperCase()).find(Boolean) ?? ''
}

/**
 * 邀请码：启动时从当前 URL 读取 ?aff=xxx，并清理历史持久化残留，
 * 避免老用户每次进站都被误判为带邀请。
 */
export function useReferralCode() {
  const [referralCode, setReferralCode] = useState(() => {
    if (typeof window !== 'undefined') {
      try { localStorage.removeItem(LEGACY_REFERRAL_CODE_KEY) } catch { /* ignore */ }
    }
    return referralCodeFromLocation()
  })

  useEffect(() => {
    const fromUrl = referralCodeFromLocation()
    if (!fromUrl) return
    setReferralCode(fromUrl)
  }, [])

  return { referralCode, setReferralCode }
}
