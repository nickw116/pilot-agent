import { API_BASE, TOKEN_KEY } from '../constants/index.js'

const API_DOWNLOAD = `${API_BASE}/download`

/**
 * Trigger a reliable file download.
 *
 * For /api/local-file proxy URLs, appends &download=true and fetches directly.
 * For HTTP(S) URLs we proxy through the bridge so mobile browsers
 * honour the filename.  Local paths are also sent through the proxy.
 * Falls back to opening the original URL in a new tab if anything fails.
 */
export async function downloadFile(file) {
  const url = file?.url || ''
  const filename = file?.filename || file?.name || 'download'

  if (!url) {
    console.warn('[download] empty url')
    return
  }

  const token = sessionStorage.getItem(TOKEN_KEY)

  let downloadUrl
  if (url.includes('/api/local-file')) {
    const sep = url.includes('?') ? '&' : '?'
    downloadUrl = url.includes('download=true') ? url : `${url}${sep}download=true`
  } else {
    const isHttpUrl = /^https?:\/\//i.test(url)
    downloadUrl = isHttpUrl
      ? `${API_DOWNLOAD}?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(filename)}`
      : `${API_DOWNLOAD}?path=${encodeURIComponent(url)}&filename=${encodeURIComponent(filename)}`
  }

  try {
    const headers = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    const resp = await fetch(downloadUrl, { headers })

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`)
    }

    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } catch (err) {
    console.error('[download] failed:', err)
    window.open(url, '_blank')
  }
}
