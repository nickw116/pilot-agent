import { Marked } from 'marked'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import { showImagePreview } from 'vant'
import { API_BASE, TOKEN_KEY } from '../constants/index.js'

/**
 * 检测文本中的媒体 URL（图片、PDF 和可下载文件）
 * 支持 markdown 图片语法 ![alt](url) 和裸 URL / 本地路径
 * 返回 { text: 清理后的文本, images: [url], pdfs: [url], files: [{url, name}] }
 */
const LOCAL_PATH_PREFIXES = ['/tmp/', '/root/', '/home/', '/var/']
const IMAGE_EXTS = /\.(jpe?g|png|gif|webp|svg|bmp|ico)(\?.*)?$/i

function isLocalPath(url) {
  return LOCAL_PATH_PREFIXES.some(p => url.startsWith(p))
}

function toProxyUrl(path, token) {
  const qs = token ? `&token=${encodeURIComponent(token)}` : ''
  return `/api/local-file?path=${encodeURIComponent(path)}${qs}`
}

function toDownloadUrl(path, token) {
  return toProxyUrl(path, token) + '&download=true'
}

// Resolve an `attachment://<filename>` reference (agent sometimes emits this
// pseudo-protocol instead of a real path) via the backend attachment lookup.
function toAttachmentUrl(name, token) {
  const qs = token ? `&token=${encodeURIComponent(token)}` : ''
  return `/api/resolve-attachment?name=${encodeURIComponent(name)}${qs}`
}

function pathBasename(p) {
  try { return decodeURIComponent(p.split('/').pop()) || 'file' } catch { return 'file' }
}

export function detectMediaUrls(text, token = '') {
  if (!text) return { text, images: [], pdfs: [], files: [] }

  const images = []
  const pdfs = []
  const files = []

  // 1. 处理 markdown 图片 ![alt](url)：保留语法在文本中，仅把本地路径 / attachment:// 替换为 proxy URL
  const mdImgRegex = /!\[([^\]]*)\]\(([^)\s]+)\)/g
  let cleaned = text.replace(mdImgRegex, (_match, alt, url) => {
    if (isLocalPath(url)) {
      return `![${alt}](${toProxyUrl(url, token)})`
    }
    // attachment://<filename> → backend lookup
    const att = url.match(/^attachment:\/\/(.+)$/i)
    if (att) {
      return `![${alt}](${toAttachmentUrl(att[1], token)})`
    }
    return _match
  })

  // 1b. 裸 attachment://<filename>（未包裹在 markdown 图片语法中）→ 提取为图片
  const bareAttRegex = /(?:^|(?<![\w/.\-]))attachment:\/\/([^\s)]+\.(?:jpe?g|png|gif|webp|svg|bmp|ico|pdf))/gi
  cleaned = cleaned.replace(bareAttRegex, (_match, name) => {
    if (/\.pdf$/i.test(name)) {
      pdfs.push(toAttachmentUrl(name, token))
    } else {
      images.push(toAttachmentUrl(name, token))
    }
    return ''
  })

  // 2. 本地路径优先处理（避免后续 HTTP 正则改变周边字符导致匹配失败）
  // 2a. MEDIA: 前缀图片
  const localImgRegex = /(?:MEDIA|media):\s*(\/\S+\.(jpe?g|png|gif|webp|svg|bmp|ico))/gi
  cleaned = cleaned.replace(localImgRegex, (_match, path) => {
    images.push(toProxyUrl(path, token))
    return ''
  })

  // 2b. MEDIA: 前缀 PDF
  const localPdfRegex = /(?:MEDIA|media):\s*(\/\S+\.pdf)/gi
  cleaned = cleaned.replace(localPdfRegex, (_match, path) => {
    pdfs.push(toProxyUrl(path, token))
    return ''
  })

  // 2c. 裸本地文件路径（扩展为匹配任意扩展名）
  const localPathRegex = /(?:^|(?<![\w/.\-]))((?:\/tmp\/|\/root\/|\/home\/|\/var\/)[\w/.\-]+\.[a-zA-Z0-9]+)(?=$|(?![\w/\-]))/gi
  cleaned = cleaned.replace(localPathRegex, (_match, path) => {
    if (/\.(jpe?g|png|gif|webp|svg|bmp|ico)$/i.test(path)) {
      images.push(toProxyUrl(path, token))
    } else if (/\.pdf$/i.test(path)) {
      pdfs.push(toProxyUrl(path, token))
    } else {
      files.push({ url: toDownloadUrl(path, token), name: pathBasename(path) })
    }
    return ''
  })

  // 3. 匹配裸图片 URL（排除 markdown 链接/图片语法中的 URL）
  const imgUrlRegex = /(?<!!?\[.*?\]\()https?:\/\/[^\s<>"]+\.(jpe?g|png|gif|webp|svg|bmp|ico)(\?[^\s<>"\)]*)?/gi
  cleaned = cleaned.replace(imgUrlRegex, (url) => {
    images.push(url)
    return ''
  })

  // 4. 匹配裸 PDF URL（排除 markdown 链接中的 URL）
  const pdfUrlRegex = /(?<!!?\[.*?\]\()https?:\/\/[^\s<>"]+\.pdf(\?[^\s<>"\)]*)?/gi
  cleaned = cleaned.replace(pdfUrlRegex, (url) => {
    pdfs.push(url)
    return ''
  })

  // 5. 匹配裸文本/CSV URL（排除 markdown 链接中的 URL，作为可下载文件处理）
  const fileUrlRegex = /(?<!!?\[.*?\]\()https?:\/\/[^\s<>"]+\.(txt|csv)(\?[^\s<>"\)]*)?/gi
  cleaned = cleaned.replace(fileUrlRegex, (url) => {
    pdfs.push(url)
    return ''
  })

  return { text: cleaned.trim(), images, pdfs, files }
}

/**
 * 判断 URL 是否为图片
 */
export function isImageUrl(url) {
  return /\.(jpe?g|png|gif|webp|svg|bmp|ico)(\?.*)?$/i.test(url)
}

/**
 * 判断 URL 是否为 PDF
 */
export function isPdfUrl(url) {
  return /\.pdf(\?.*)?$/i.test(url)
}

/**
 * 图片点击全屏预览
 */
export function previewImage(url, allImages = []) {
  showImagePreview({
    images: allImages.length > 0 ? allImages : [url],
    startPosition: allImages.indexOf(url),
    closeable: true,
  })
}

// ── 文件预览类型判定 ──
const PREVIEW_IMAGE_RE = /\.(jpe?g|png|gif|webp|svg|bmp|ico)(\?.*)?$/i
const PREVIEW_PDF_RE = /\.pdf(\?.*)?$/i
const PREVIEW_TEXT_RE = /\.(txt|md|markdown|csv|json|log|ya?ml|xml|html?|css|js|ts|sh|py|java|c|cc|cpp|h|hpp|rs|go|rb|php|sql|ini|conf|toml)(\?.*)?$/i
const PREVIEW_OFFICE_RE = /\.(docx?|pptx?|xlsx?|odt|odp|ods|rtf)(\?.*)?$/i

/**
 * 从任意来源（URL 字符串 或 文件对象）提取文件路径。
 * 支持 /api/local-file?path= 、/api/download?path= 、/api/resolve-attachment?name= 、裸路径、http URL
 */
function extractFilePath(input) {
  if (!input) return ''
  const url = typeof input === 'string' ? input : (input.url || input.path || '')
  try {
    // 已经是 URL 形式，尝试解析 query
    const u = new URL(url, 'http://dummy')
    const p = u.searchParams.get('path')
    if (p) return p
    const n = u.searchParams.get('name')
    if (n) return n
    // 无 query 的 path（可能是裸路径）
    if (u.pathname && u.pathname !== '/' && !u.host.includes('dummy')) return u.pathname
  } catch {
    // 不是 URL，当作裸路径
    return url
  }
  return url
}

function fileExt(name) {
  const m = /\.([a-zA-Z0-9]+)(\?|$)/.exec(name || '')
  return m ? ('.' + m[1].toLowerCase()) : ''
}

/**
 * 判定一个文件的可预览性，返回预览描述对象。
 * @param {string|object} input  URL 字符串 或 { url, filename/name }
 * @param {string} token         当前 token（用于构建带鉴权的预览 URL）
 * @returns {{ previewType: 'image'|'pdf'|'text'|'office'|'other', filename, previewUrl, downloadUrl, rawUrl }}
 */
export function getPreviewInfo(input, token = '') {
  const rawUrl = typeof input === 'string' ? input : (input?.url || '')
  const explicitName = typeof input === 'object' ? (input?.filename || input?.name) : ''
  const filePath = extractFilePath(input)
  const name = explicitName || pathBasename(filePath) || rawUrl
  const ext = fileExt(name) || fileExt(filePath)

  let previewType = 'other'
  if (PREVIEW_IMAGE_RE.test(name) || PREVIEW_IMAGE_RE.test(filePath)) previewType = 'image'
  else if (PREVIEW_PDF_RE.test(name) || PREVIEW_PDF_RE.test(filePath)) previewType = 'pdf'
  else if (PREVIEW_TEXT_RE.test(name) || PREVIEW_TEXT_RE.test(filePath)) previewType = 'text'
  else if (PREVIEW_OFFICE_RE.test(name) || PREVIEW_OFFICE_RE.test(filePath)) previewType = 'office'

  // 构建带 token 的 inline 预览 URL（指向后端 /api/preview，用 API_BASE 前缀以兼容生产部署）
  const qs = token ? `&token=${encodeURIComponent(token)}` : ''
  const previewUrl = filePath ? `${API_BASE}/preview?path=${encodeURIComponent(filePath)}${qs}` : rawUrl

  // 下载 URL：优先复用原始 URL，否则用 preview path + download
  const downloadUrl = rawUrl || (filePath ? `${previewUrl}&download=true` : '')

  return { previewType, filename: name || '文件', previewUrl, downloadUrl, rawUrl }
}

// Configure marked with highlight.js
const marked = new Marked({
  breaks: true,
  gfm: true,
  renderer: {
    link({ href, title, text }) {
      return `<a href="${href}" target="_blank" rel="noopener noreferrer"${title ? ` title="${title}"` : ""}>${text}</a>`
    },
    image({ href, title, text }) {
      return `<img src="${href}" alt="${text || ''}" style="max-width:100%;height:auto;border-radius:8px;cursor:pointer">`
    },
    code({ text, lang }) {
      const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
      // 容错：空内容直接展示占位提示
      const codeText = (text || '').trim()
      if (!codeText) {
        return `<div class="code-block"><div class="code-header"><span class="code-lang">${language}</span><button class="code-copy">复制</button></div><pre><code class="hljs language-${language}"> </code></pre></div>`
      }
      try {
        const highlighted = hljs.highlight(codeText, { language }).value
        return `<div class="code-block"><div class="code-header"><span class="code-lang">${language}</span><button class="code-copy" data-copy-code>复制</button></div><pre><code class="hljs language-${language}">${highlighted}</code></pre></div>`
      } catch {
        // highlight 失败时降级为纯文本
        const escaped = codeText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        return `<div class="code-block"><div class="code-header"><span class="code-lang">${language}</span><button class="code-copy">复制</button></div><pre><code class="hljs language-${language}">${escaped}</code></pre></div>`
      }
    }
  }
})

/**
 * 修复流式 Markdown 中未闭合的代码块
 * 流式输出过程中，``` 开了但还没闭合会导致 marked 把后续内容全部吞掉
 */
function fixUnclosedCodeBlocks(text) {
  // 统计 ``` 出现次数（排除行内 ` 包裹的情况）
  const matches = text.match(/^```/gm)
  const count = matches ? matches.length : 0
  // 奇数个 => 有未闭合的代码块，补上闭合
  if (count % 2 !== 0) {
    return text + '\n```'
  }
  return text
}

/**
 * Render Markdown text to HTML (for AI messages)
 * 流式安全：自动修复未闭合代码块
 */
export function renderMarkdown(text) {
  if (!text) return ''
  const safeText = fixUnclosedCodeBlocks(text)
  const rawHtml = marked.parse(safeText)
  const purified = DOMPurify.sanitize(rawHtml, {
    ADD_TAGS: ['img'],
    ADD_ATTR: ['src', 'alt', 'style', 'target', 'rel'],
  })
  return purified
}

/**
 * Format plain text for HTML rendering (escape + line breaks, for user messages)
 */
export function formatText(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

/**
 * Extract text content from a history entry.
 * Handles string content, array of parts, and fallback to .text field.
 */
export function extractText(entry) {
  if (!entry) return ''
  if (typeof entry === 'string') return entry

  const unwrap = entry.message || entry.item || entry.data || entry.payload || entry
  const content = unwrap.content ?? unwrap.text ?? unwrap.value
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content
      .map((p) => {
        if (typeof p === 'string') return p
        if (!p || typeof p !== 'object') return ''
        if (typeof p.text === 'string') return p.text
        if (typeof p.content === 'string') return p.content
        if (Array.isArray(p.content)) return extractText({ content: p.content })
        if (typeof p.value === 'string') return p.value
        return ''
      })
      .filter(Boolean)
      .join('')
  }
  if (content && typeof content === 'object') return extractText(content)
  return unwrap.text || entry.text || ''
}
