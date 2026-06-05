import { useState, useCallback } from 'react'
import { api } from '../api'
import { signedFileUrl } from '../fileUrls'

export interface UploadResult {
  path: string
  url: string
}

export interface UseUploadOptions {
  token: string
  onSuccess?: (result: UploadResult) => void
  successMessage?: string
  failMessage?: string
}

export interface UseUploadReturn {
  uploading: boolean
  message: string
  upload: (file: File | undefined) => Promise<UploadResult | null>
  clear: () => void
  setMessage: (msg: string) => void
}

/**
 * Generic file upload hook. Handles uploading state, error messages, and API call.
 */
export function useUpload({ token, onSuccess, successMessage = '', failMessage = 'Upload failed' }: UseUploadOptions): UseUploadReturn {
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')

  const upload = useCallback(async (file: File | undefined): Promise<UploadResult | null> => {
    if (!file) return null
    setUploading(true)
    setMessage('')
    try {
      const uploaded = await api.uploadImage(token, file)
      const result: UploadResult = { path: uploaded.path, url: signedFileUrl(uploaded.url) }
      if (successMessage) setMessage(successMessage)
      onSuccess?.(result)
      return result
    } catch (error) {
      setMessage(error instanceof Error ? error.message : failMessage)
      return null
    } finally {
      setUploading(false)
    }
  }, [token, onSuccess, successMessage, failMessage])

  const clear = useCallback(() => {
    setMessage('')
  }, [])

  return { uploading, message, upload, clear, setMessage }
}
