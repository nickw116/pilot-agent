<template>
  <div class="message-list" ref="listRef">
    <template v-for="msg in visibleMessages" :key="msg.id">
      <div
        :class="['message-item', msg.role]"
      >
        <div class="bubble">
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
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { formatText, renderMarkdown, previewImage } from '../utils/format.js'
import { downloadFile } from '../utils/download.js'
import AcpLogPanel from './AcpLogPanel.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  formatFileSize: { type: Function, default: () => '' },
  fileIcon: { type: Function, default: () => '📄' },
  acpLogs: { type: Array, default: () => [] },
  acpStatus: { type: String, default: '' },
  currentAgentId: { type: String, default: 'main' },
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
  scrollToBottom()
})

onBeforeUnmount(() => {
  listRef.value?.removeEventListener('scroll', handleScroll)
})

defineExpose({ scrollToBottom })
</script>

<style>
/* ── Message List ── */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
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
  background: var(--color-bg-glass);
  backdrop-filter: blur(8px);
  color: var(--color-text);
  border-radius: 18px;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  max-width: 85%;
}
@media (min-width: 1200px) {
  .message-item.assistant .bubble {
    max-width: 800px;
  }
}
.text { min-height: 8px; }

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
</style>
