<template>
  <div class="message-list" ref="listRef">
    <template v-for="msg in visibleMessages" :key="msg.id">
      <div
        :class="['message-item', msg.role, { pending: msg.pending }]"
      >
        <div class="bubble" :class="{ 'bubble--thinking': shouldShowThinking(msg) }">
          <div v-if="msg.thinking" class="thinking-block">
            <div class="thinking-header" @click="msg._thinkingExpanded = !msg._thinkingExpanded">
              <span class="thinking-icon">💭</span>
              <span class="thinking-label">思考中...</span>
              <span class="thinking-toggle">{{ msg._thinkingExpanded === false ? '展开' : '收起' }}</span>
            </div>
            <div v-if="msg._thinkingExpanded !== false" class="thinking-content">
              {{ msg.thinking }}
              <span v-if="msg.isStreaming" class="typing-cursor"></span>
            </div>
          </div>
          <div v-if="msg.content || (msg.media && (msg.media.images.length > 0 || msg.media.pdfs.length > 0))" class="text" :class="{ markdown: msg.role === 'assistant' }">
            <!-- 文本内容：优先用 media.text（已清理图片 URL），为空则 fallback 到原始 content，避免链接/文本被误过滤后整栏空白 -->
            <span v-if="getMsgRenderText(msg).trim()" v-html="msg.role === 'assistant' ? (msg._renderedCache || renderMarkdown(getMsgRenderText(msg))) : formatText(getMsgRenderText(msg))"></span>
            <span v-if="msg.role === 'assistant' && loading && isStreamingAssistant(msg)" class="typing-cursor"></span>
            <!-- 图片预览（放在文本下方） -->
            <div v-if="msg.media && msg.media.images.length > 0" class="media-images">
              <img
                v-for="(imgUrl, imgIdx) in msg.media.images"
                :key="imgIdx"
                :src="imgUrl"
                class="media-img"
                @click="previewImage(imgUrl, msg.media.images)"
                loading="lazy"
                @error="handleImgError($event)"
              />
            </div>
            <!-- PDF / 文件链接（带下载按钮，放在文本下方） -->
            <div v-if="msg.media && msg.media.pdfs.length > 0" class="media-pdfs">
              <div
                v-for="(pdfUrl, pdfIdx) in msg.media.pdfs"
                :key="pdfIdx"
                class="pdf-card"
              >
                <a
                  :href="pdfUrl"
                  target="_blank"
                  rel="noopener"
                  class="pdf-card-link"
                >
                  <span class="pdf-icon">📄</span>
                  <span class="pdf-name">{{ pdfFileName(pdfUrl) }}</span>
                  <span class="pdf-action">查看</span>
                </a>
                <button
                  type="button"
                  class="pdf-download-btn"
                  @click="downloadMediaUrl(pdfUrl)"
                  title="下载"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <div v-else-if="shouldShowThinking(msg)" class="thinking">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <!-- 文件下载卡片 -->
          <div v-if="msg.role === 'assistant' && msg.files && msg.files.length > 0" class="file-cards">
            <div
              v-for="(file, idx) in msg.files"
              :key="file.url"
              class="file-card"
              @click="handleDownload(file)"
            >
              <span class="file-card-icon">{{ fileIcon(file.content_type) }}</span>
              <div class="file-card-info">
                <span class="file-card-name">{{ file.filename }}</span>
                <span class="file-card-size">{{ formatFileSize(file.size) }}</span>
              </div>
              <svg class="file-card-dl" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </div>
          </div>
          <!-- ACP 日志面板 -->
          <AcpLogPanel
            v-if="props.currentAgentId === 'dev' && msg.role === 'assistant' && ((msg.acpLogs && msg.acpLogs.length > 0) || msg.isStreaming)"
            :logs="msg.acpLogs || []"
            :is-running="isAcpRunning(msg)"
            :acp-status="msg.acpStatus || ''"
          />
          <div v-if="msg.pending" class="pending-indicator">
            <span class="pending-spinner"></span>
            <span class="pending-text">发送中…</span>
          </div>
          <div v-if="msg.content && !msg.pending" class="bubble-actions">
            <button
              class="bubble-expand-btn"
              type="button"
              @click.stop="openFullscreen(msg)"
              title="全屏查看"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
            </button>
            <button
              class="bubble-copy-btn"
              type="button"
              @click.stop="handleBubbleCopy($event, msg)"
              title="复制"
            >
              <svg class="copy-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <svg class="check-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>

  <Teleport to="body">
    <Transition name="msg-fs">
      <div
        v-if="fullscreenMsg"
        class="msg-fs"
        @click.self="closeFullscreen"
      >
        <div class="msg-fs-card">
          <div class="msg-fs-header">
            <span class="msg-fs-tag">{{ fullscreenMsg.role === 'assistant' ? '🤖 AI 助手' : '🧑 我' }}</span>
            <div class="msg-fs-actions">
              <button
                type="button"
                class="msg-fs-btn"
                :class="{ copied: fullscreenCopied }"
                @click="copyFullscreen"
                title="复制全部"
              >
                <svg class="copy-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <svg class="check-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <span class="msg-fs-btn-label">{{ fullscreenCopied ? '已复制' : '复制' }}</span>
              </button>
              <button
                type="button"
                class="msg-fs-btn msg-fs-btn--close"
                @click="closeFullscreen"
                title="关闭 (Esc)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
          <div
            class="msg-fs-body text"
            :class="{ markdown: fullscreenMsg.role === 'assistant' }"
            @click="onFullscreenClick"
          >
            <span v-if="fullscreenHasText" v-html="fullscreenHtml"></span>
            <div
              v-if="fullscreenMsg.media && fullscreenMsg.media.images && fullscreenMsg.media.images.length > 0"
              class="msg-fs-images"
            >
              <img
                v-for="(imgUrl, imgIdx) in fullscreenMsg.media.images"
                :key="imgIdx"
                :src="imgUrl"
                class="msg-fs-img"
                @click="previewImage(imgUrl, fullscreenMsg.media.images)"
                loading="lazy"
                @error="handleImgError"
              />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { formatText, renderMarkdown, previewImage } from '../utils/format.js'
import { downloadFile } from '../utils/download.js'
import { showNotify } from 'vant'
import AcpLogPanel from './AcpLogPanel.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  formatFileSize: { type: Function, default: () => '' },
  fileIcon: { type: Function, default: () => '📄' },
  acpLogs: { type: Array, default: () => [] },
  acpStatus: { type: String, default: '' },
  currentAgentId: { type: String, default: 'user' },
})

const emit = defineEmits(['load-more'])

const listRef = ref(null)
const BOTTOM_THRESHOLD = 100
const RENDER_WINDOW = 40
const visibleMessages = computed(() => {
  const msgs = props.messages
  if (msgs.length <= RENDER_WINDOW) return msgs
  return msgs.slice(-RENDER_WINDOW)
})

function getMsgRenderText(msg) {
  if (msg.media && msg.media.text !== undefined) {
    return msg.media.text || msg.content || ''
  }
  return msg.content || ''
}

function isStreamingAssistant(msg) {
  if (msg.role !== 'assistant') return false
  if (msg.isStreaming) return true
  const last = props.messages[props.messages.length - 1]
  return last && last.id === msg.id && last.isStreaming
}

function shouldShowThinking(msg) {
  return msg.role === 'assistant' && props.loading && isStreamingAssistant(msg) && !msg.content
}

function handleImgError(e) {
  e.target.style.display = 'none'
}

function pdfFileName(url) {
  try {
    const parts = url.split('/')
    return decodeURIComponent(parts[parts.length - 1]) || 'document.pdf'
  } catch {
    return 'document.pdf'
  }
}

function handleDownload(file) {
  downloadFile(file)
}

function downloadMediaUrl(url) {
  const filename = pdfFileName(url)
  downloadFile({ url, filename })
}

function handleBubbleCopy(e, msg) {
  const text = getMsgRenderText(msg) || msg.content || ''
  navigator.clipboard.writeText(text).then(() => {
    const btn = e.currentTarget
    btn.classList.add('copied')
    showNotify({ type: 'success', message: '已复制到剪贴板', duration: 1500 })
    setTimeout(() => btn.classList.remove('copied'), 2000)
  }).catch(() => {})
}

function handleCodeCopy(e) {
  const btn = e.target.closest('.code-copy')
  if (!btn) return
  const block = btn.closest('.code-block')
  if (!block) return
  const code = block.querySelector('code')
  if (!code) return
  navigator.clipboard.writeText(code.textContent).then(() => {
    btn.textContent = '已复制'
    btn.classList.add('copied')
    setTimeout(() => {
      btn.textContent = '复制'
      btn.classList.remove('copied')
    }, 2000)
  }).catch(() => {})
}

function scrollToBottom() {
  const el = listRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

function handleScroll() {
  const el = listRef.value
  if (!el) return
  if (el.scrollTop < 60) {
    emit('load-more')
  }
}

// Auto-scroll on new messages
watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      const el = listRef.value
      if (!el) return
      const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      if (distanceToBottom < BOTTOM_THRESHOLD * 2) {
        scrollToBottom()
      }
    })
  }
)

onMounted(() => {
  listRef.value?.addEventListener('scroll', handleScroll, { passive: true })
  listRef.value?.addEventListener('click', handleCodeCopy)
  scrollToBottom()
})

// ── Fullscreen message view ──
const fullscreenMsg = ref(null)
const fullscreenCopied = ref(false)

const fullscreenHtml = computed(() => {
  const msg = fullscreenMsg.value
  if (!msg) return ''
  const text = getMsgRenderText(msg)
  if (!text) return ''
  return msg.role === 'assistant' ? (msg._renderedCache || renderMarkdown(text)) : formatText(text)
})

const fullscreenHasText = computed(() => {
  const msg = fullscreenMsg.value
  if (!msg) return false
  return getMsgRenderText(msg).trim().length > 0
})

function openFullscreen(msg) {
  fullscreenMsg.value = msg
  fullscreenCopied.value = false
}

function closeFullscreen() {
  fullscreenMsg.value = null
}

function copyFullscreen() {
  const msg = fullscreenMsg.value
  if (!msg) return
  const text = getMsgRenderText(msg) || msg.content || ''
  navigator.clipboard.writeText(text).then(() => {
    fullscreenCopied.value = true
    showNotify({ type: 'success', message: '已复制到剪贴板', duration: 1500 })
    setTimeout(() => { fullscreenCopied.value = false }, 2000)
  }).catch(() => {})
}

function onFullscreenClick(e) {
  handleCodeCopy(e)
  const img = e.target.closest('img')
  if (img && img.src) {
    const imgs = fullscreenMsg.value?.media?.images
    previewImage(img.src, imgs && imgs.length ? imgs : [img.src])
  }
}

function handleEsc(e) {
  if (e.key === 'Escape' && fullscreenMsg.value) closeFullscreen()
}

watch(fullscreenMsg, (val) => {
  if (typeof document === 'undefined') return
  if (val) {
    document.addEventListener('keydown', handleEsc)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', handleEsc)
    document.body.style.overflow = ''
  }
})

onBeforeUnmount(() => {
  listRef.value?.removeEventListener('scroll', handleScroll)
  listRef.value?.removeEventListener('click', handleCodeCopy)
  document.removeEventListener('keydown', handleEsc)
  if (document.body) document.body.style.overflow = ''
})

defineExpose({ scrollToBottom })
</script>

<style>
/* ── Message List ── */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px 104px;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}

/* ── Message Item ── */
.message-item {
  display: flex;
  margin-bottom: 12px;
  max-width: 85%;
  animation: fadeInUp 0.35s ease;
}
.message-item.user {
  margin-left: auto;
  flex-direction: row-reverse;
}
.message-item.assistant {
  margin-right: auto;
  max-width: 100%;
}

/* ── Bubble ── */
.bubble {
  padding: 10px 14px;
  border-radius: 18px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
  overflow-wrap: anywhere;
  min-width: 40px;
  max-width: calc(100vw - 32px);
  position: relative;
}
.message-item.user .bubble {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(139, 92, 246, 0.08));
  color: var(--color-text);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 18px;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.06);
  max-width: 80%;
}
@media (min-width: 1200px) {
  .message-item.user .bubble {
    max-width: 600px;
  }
}
.message-item.assistant .bubble {
  background: var(--color-bg-secondary);
  color: var(--color-text);
  border-radius: 18px;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  width: 100%;
  max-width: 100%;
  flex: 1 1 auto;
  box-sizing: border-box;
}
.message-item.assistant .bubble--thinking {
  width: auto;
  flex: 0 0 auto;
}
.text { min-height: 8px; }

/* ── Pending (sending) state ── */
.message-item.pending .bubble {
  opacity: 0.65;
}
.message-item.user.pending .bubble {
  background: var(--color-bg-glass, #eef0f3);
  border: 1px dashed rgba(99, 102, 241, 0.35);
  box-shadow: none;
}
.pending-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}
.pending-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--color-primary, #6366f1);
  border-radius: 50%;
  animation: pending-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes pending-spin {
  to { transform: rotate(360deg); }
}

/* ── Bubble Actions (复制 / 全屏，独立成行避免与短文本重叠) ── */
.bubble-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.bubble:hover .bubble-actions {
  opacity: 1;
}
@media (hover: none) {
  .bubble-actions {
    opacity: 0.4;
  }
}

/* ── Bubble Expand (fullscreen) Button ── */
.bubble-expand-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(99, 102, 241, 0.06);
  color: var(--color-text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease, color 0.2s ease;
}
.bubble-expand-btn:hover {
  background: rgba(99, 102, 241, 0.12);
  color: var(--color-primary);
}
.bubble-expand-btn:active {
  transform: scale(0.9);
}

.bubble-copy-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(99, 102, 241, 0.06);
  color: var(--color-text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease, color 0.2s ease;
}
.bubble-copy-btn:hover {
  background: rgba(99, 102, 241, 0.12);
  color: var(--color-primary);
}
.bubble-copy-btn:active {
  transform: scale(0.9);
}
.bubble-copy-btn .check-icon {
  display: none;
}
.bubble-copy-btn.copied .copy-icon {
  display: none;
}
.bubble-copy-btn.copied .check-icon {
  display: block;
  color: var(--color-success);
}
.bubble-copy-btn.copied {
  opacity: 1;
}

/* ── Typing Cursor ── */
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--color-primary);
  border-radius: 1px;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink-cursor 0.8s ease-in-out infinite;
}
@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── Markdown Styles ── */
.text.markdown {
  font-size: 14px;
  line-height: 1.7;
}
.text.markdown p { margin: 0 0 8px; }
.text.markdown p:last-child { margin-bottom: 0; }
.text.markdown h1, .text.markdown h2, .text.markdown h3 {
  margin: 12px 0 6px;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 600;
  color: var(--color-text);
}
.text.markdown h1 { font-size: 18px; }
.text.markdown h2 { font-size: 16px; }
.text.markdown h3 { font-size: 15px; }
.text.markdown ul, .text.markdown ol {
  padding-left: 20px;
  margin: 6px 0;
}
.text.markdown li { margin: 3px 0; }
.text.markdown a {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px dashed var(--color-primary);
}
.text.markdown a:hover { border-bottom-style: solid; }
.text.markdown strong { font-weight: 600; }
.text.markdown em { font-style: italic; }
.text.markdown blockquote {
  margin: 8px 0;
  padding: 6px 12px;
  border-left: 3px solid var(--color-primary);
  background: rgba(99, 102, 241, 0.04);
  border-radius: 0 8px 8px 0;
  color: var(--color-text-secondary);
}
.text.markdown table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
}
.text.markdown th, .text.markdown td {
  border: 1px solid var(--color-border);
  padding: 6px 10px;
  text-align: left;
}
.text.markdown th {
  background: rgba(99, 102, 241, 0.04);
  font-weight: 600;
}
.text.markdown code:not(.hljs) {
  background: rgba(99, 102, 241, 0.06);
  color: var(--color-primary);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.text.markdown img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  display: block;
  margin: 6px 0;
  cursor: pointer;
}

/* === Media Preview Styles === */
.media-images {
  margin-bottom: 8px;
}
.media-img {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
  cursor: pointer;
  object-fit: contain;
  display: block;
  margin: 4px 0;
  transition: opacity 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.media-img:hover {
  opacity: 0.85;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}
.media-pdfs {
  margin-bottom: 8px;
}
.pdf-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 8px;
  color: var(--color-text);
  text-decoration: none;
  margin: 4px 0;
  transition: background 0.2s, border-color 0.2s;
}
.pdf-card:hover {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.15);
}
.pdf-icon {
  font-size: 20px;
}
.pdf-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pdf-action {
  font-size: 12px;
  color: var(--color-primary);
  white-space: nowrap;
}
.pdf-card-link {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  color: inherit;
  text-decoration: none;
}
.pdf-download-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: rgba(99, 102, 241, 0.06);
  color: var(--color-primary);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}
.pdf-download-btn:active {
  transform: scale(0.92);
  background: rgba(99, 102, 241, 0.12);
}

/* ── Code Block ── */
.code-block {
  margin: 8px 0;
  border-radius: 10px;
  overflow: hidden;
  background: #1e1e2e;
  border: 1px solid rgba(255,255,255,0.08);
}
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.code-lang {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.code-copy {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  background: none;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.code-copy:hover {
  color: #fff;
  border-color: rgba(255,255,255,0.4);
}
.code-block pre {
  margin: 0;
  padding: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.code-block code {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #e2e8f0;
}
.code-block code .hljs-keyword { color: #c792ea; }
.code-block code .hljs-string { color: #c3e88d; }
.code-block code .hljs-number { color: #f78c6c; }
.code-block code .hljs-comment { color: #637777; font-style: italic; }
.code-block code .hljs-built_in { color: #82aaff; }
.code-block code .hljs-function { color: #82aaff; }
.code-block code .hljs-title { color: #82aaff; }
.code-block code .hljs-params { color: #e2e8f0; }
.code-block code .hljs-attr { color: #ffcb6b; }
.code-block code .hljs-variable { color: #f07178; }
.code-block code .hljs-selector_tag { color: #89ddff; }
.code-block code .hljs-type { color: #ffcb6b; }

/* ── Thinking Block ── */
.thinking-block {
  margin-bottom: 8px;
  border-left: 3px solid rgba(99, 102, 241, 0.15);
  border-radius: 0 6px 6px 0;
  background: rgba(99, 102, 241, 0.03);
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  cursor: pointer;
  user-select: none;
}
.thinking-icon {
  font-size: 14px;
}
.thinking-label {
  font-size: 12px;
  color: var(--color-text-muted);
  flex: 1;
}
.thinking-toggle {
  font-size: 11px;
  color: var(--color-primary);
  opacity: 0.7;
}
.thinking-content {
  padding: 0 10px 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

/* ── Thinking Animation ── */
.thinking {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 0;
}
.sse-count {
  font-size: 12px;
  color: var(--color-text-muted);
  animation: pulse 1s infinite;
}
.dot {
  width: 7px;
  height: 7px;
  background: var(--color-primary);
  border-radius: 50%;
  opacity: 0.7;
  animation: bounce 1.2s ease-in-out infinite;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-8px); opacity: 1; }
}

/* ── Animations ── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── File Download Cards ── */
.file-cards {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.file-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 12px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
  animation: fadeInUp 0.3s ease;
}
.file-card:hover {
  background: rgba(99, 102, 241, 0.08);
  border-color: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.08);
}
.file-card:active {
  transform: scale(0.98);
}
.file-card-icon {
  font-size: 28px;
  flex-shrink: 0;
}
.file-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.file-card-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.file-card-size {
  font-size: 11px;
  color: var(--color-text-muted);
}
.file-card-dl {
  flex-shrink: 0;
  color: var(--color-primary);
  opacity: 0.6;
  transition: opacity 0.2s ease;
}
.file-card:hover .file-card-dl {
  opacity: 1;
}

/* ── Fullscreen Message Overlay ── */
.msg-fs {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}
.msg-fs-card {
  width: 100%;
  max-width: 920px;
  height: 100%;
  max-height: 100%;
  background: var(--color-bg, #ffffff);
  border-radius: 16px;
  border: 1px solid var(--color-border);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.msg-fs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.msg-fs-tag {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.msg-fs-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.msg-fs-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: rgba(99, 102, 241, 0.06);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.msg-fs-btn:hover {
  background: rgba(99, 102, 241, 0.12);
  color: var(--color-primary);
  border-color: rgba(99, 102, 241, 0.3);
}
.msg-fs-btn:active {
  transform: scale(0.96);
}
.msg-fs-btn--close {
  padding: 0;
  width: 34px;
  justify-content: center;
}
.msg-fs-btn .check-icon { display: none; }
.msg-fs-btn.copied .copy-icon { display: none; }
.msg-fs-btn.copied .check-icon {
  display: inline-block;
  color: var(--color-success, #10b981);
}
.msg-fs-btn-label { line-height: 1; }

.msg-fs-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 24px 28px 40px;
  font-size: 15px;
  line-height: 1.75;
  color: var(--color-text);
  word-break: break-word;
  overflow-wrap: anywhere;
}
/* 放大版 Markdown 排版（继承全局 .text.markdown 基础样式后覆盖尺寸） */
.msg-fs-body.markdown { font-size: 15px; line-height: 1.8; }
.msg-fs-body.markdown p { margin: 0 0 12px; }
.msg-fs-body.markdown h1 { font-size: 22px; margin: 20px 0 10px; }
.msg-fs-body.markdown h2 { font-size: 19px; margin: 18px 0 8px; }
.msg-fs-body.markdown h3 { font-size: 16px; margin: 14px 0 6px; }
.msg-fs-body.markdown ul,
.msg-fs-body.markdown ol { padding-left: 24px; margin: 8px 0 12px; }
.msg-fs-body.markdown li { margin: 4px 0; }
.msg-fs-body.markdown blockquote { margin: 12px 0; padding: 8px 14px; }
.msg-fs-body.markdown table { font-size: 13.5px; }
.msg-fs-body.markdown .code-block pre { font-size: 13.5px; }

.msg-fs-images {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg-fs-img {
  max-width: 100%;
  border-radius: 10px;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

/* 进入/离开过渡 */
.msg-fs-enter-active,
.msg-fs-leave-active {
  transition: opacity 0.25s ease;
}
.msg-fs-enter-from,
.msg-fs-leave-to {
  opacity: 0;
}
.msg-fs-enter-active .msg-fs-card,
.msg-fs-leave-active .msg-fs-card {
  transition: transform 0.25s ease;
}
.msg-fs-enter-from .msg-fs-card,
.msg-fs-leave-to .msg-fs-card {
  transform: scale(0.96);
}

/* 移动端适配：全屏铺满 */
@media (max-width: 600px) {
  .msg-fs { padding: 0; }
  .msg-fs-card { border-radius: 0; max-width: 100%; }
  .msg-fs-header { padding: 12px 14px; }
  .msg-fs-body { padding: 16px 16px 32px; }
  .msg-fs-btn-label { display: none; }
}
</style>
