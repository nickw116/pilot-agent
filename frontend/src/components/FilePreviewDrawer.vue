<template>
  <van-popup
    v-model:show="visible"
    position="right"
    :style="{ width: '88%', maxWidth: '520px', height: '100%' }"
    class="file-preview-drawer"
  >
    <div class="preview-panel">
      <!-- Header -->
      <div class="preview-header">
        <div class="preview-title-wrap">
          <span class="preview-file-icon">{{ typeIcon }}</span>
          <span class="preview-filename" :title="file?.filename">{{ file?.filename || '预览' }}</span>
        </div>
        <div class="preview-actions">
          <button
            v-if="file?.downloadUrl"
            type="button"
            class="preview-action-btn"
            title="下载"
            @click="handleDownload"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </button>
          <button
            type="button"
            class="preview-action-btn preview-action-close"
            title="关闭 (Esc)"
            @click="visible = false"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Body -->
      <div class="preview-body">
        <!-- Loading (office conversion) -->
        <div v-if="loading" class="preview-status">
          <span class="preview-spinner"></span>
          <span class="preview-status-text">正在转换为预览格式…</span>
          <span class="preview-status-hint">Office 文件首次预览需转换，请稍候</span>
        </div>

        <!-- Error -->
        <div v-else-if="loadError" class="preview-status preview-status-error">
          <span class="preview-status-emoji">😕</span>
          <span class="preview-status-text">{{ loadError }}</span>
          <button v-if="file?.downloadUrl" class="preview-fallback-btn" @click="handleDownload">
            下载文件
          </button>
        </div>

        <!-- Image -->
        <div v-else-if="file?.previewType === 'image'" class="preview-image-wrap">
          <img
            :src="file.previewUrl"
            class="preview-img"
            @click="openImageFullscreen"
            @error="onMediaError"
          />
        </div>

        <!-- PDF / Office(converted to PDF) -->
        <iframe
          v-else-if="file && (file.previewType === 'pdf' || file.previewType === 'office')"
          ref="iframeRef"
          :src="file.previewUrl"
          class="preview-iframe"
          @load="onIframeLoad"
        ></iframe>

        <!-- Text -->
        <div v-else-if="file?.previewType === 'text'" class="preview-text-wrap">
          <pre class="preview-text">{{ textContent }}</pre>
        </div>

        <!-- Unsupported -->
        <div v-else-if="file" class="preview-status">
          <span class="preview-status-emoji">📎</span>
          <span class="preview-status-text">该格式暂不支持在线预览</span>
          <button v-if="file?.downloadUrl" class="preview-fallback-btn" @click="handleDownload">
            下载文件
          </button>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { showImagePreview } from 'vant'
import { downloadFile } from '../utils/download.js'
import { TOKEN_KEY } from '../constants/index.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  file: { type: Object, default: null },
})

const emit = defineEmits(['update:show', 'download'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const loading = ref(false)
const loadError = ref('')
const textContent = ref('')
const iframeRef = ref(null)

const typeIcon = computed(() => {
  const t = props.file?.previewType
  const icons = { image: '🖼️', pdf: '📄', office: '📊', text: '📝' }
  return icons[t] || '📎'
})

// Reset state when the previewed file changes or drawer opens.
watch(
  () => [props.show, props.file?.previewUrl],
  ([open]) => {
    if (!open) return
    loading.value = props.file?.previewType === 'office'
    loadError.value = ''
    textContent.value = ''
    if (props.file?.previewType === 'text') {
      loadText()
    }
  },
  { immediate: true }
)

async function loadText() {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY) || ''
    const resp = await fetch(props.file.previewUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    textContent.value = await resp.text()
  } catch (e) {
    loadError.value = '文本加载失败'
  }
}

function onIframeLoad() {
  // Office files: iframe loaded => conversion done.
  loading.value = false
}

function onMediaError() {
  loadError.value = '文件加载失败，可能已损坏或被移动'
  loading.value = false
}

function openImageFullscreen() {
  if (props.file?.previewUrl) {
    showImagePreview({ images: [props.file.previewUrl], closeable: true })
  }
}

function handleDownload() {
  if (props.file?.downloadUrl) {
    downloadFile({ url: props.file.downloadUrl, filename: props.file.filename })
    emit('download', props.file)
  }
}
</script>

<style scoped>
.file-preview-drawer.van-popup {
  background: var(--color-bg-secondary);
}

.preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 14px;
  border-bottom: 1px solid var(--color-border);
  gap: 10px;
}

.preview-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.preview-file-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.preview-filename {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.preview-action-btn {
  width: 34px;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.preview-action-btn:active {
  background: var(--color-bg-tertiary);
}

.preview-action-close:active {
  color: var(--color-danger);
}

.preview-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-tertiary);
}

/* ── iframe (PDF / office) ── */
.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

/* ── image ── */
.preview-image-wrap {
  flex: 1;
  overflow-y: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 16px;
}

.preview-img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  cursor: zoom-in;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

/* ── text ── */
.preview-text-wrap {
  flex: 1;
  overflow: auto;
  padding: 14px;
}

.preview-text {
  margin: 0;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-bg-glass);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px;
}

/* ── status (loading / error / unsupported) ── */
.preview-status {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 24px;
  text-align: center;
}

.preview-status-emoji {
  font-size: 42px;
}

.preview-status-text {
  font-size: 15px;
  color: var(--color-text-secondary);
}

.preview-status-hint {
  font-size: 12px;
  color: var(--color-text-muted);
}

.preview-status-error .preview-status-text {
  color: var(--color-danger);
}

.preview-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: preview-spin 0.8s linear infinite;
}

@keyframes preview-spin {
  to { transform: rotate(360deg); }
}

.preview-fallback-btn {
  margin-top: 8px;
  padding: 9px 22px;
  border: 1px solid var(--color-primary);
  background: var(--color-primary);
  color: #fff;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.preview-fallback-btn:active {
  opacity: 0.85;
}
</style>
