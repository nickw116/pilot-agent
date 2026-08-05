<template>
  <div class="input-area">
    <!-- 可选 banner 插槽（如 monitor 模式） -->
    <slot name="banner"></slot>

    <!-- Steer 悬挂消息：AI 回复时插入的消息先浮在输入框上方，确认后再落入消息流 -->
    <div class="steer-preview" v-if="pendingSteerMessages.length > 0">
      <div
        v-for="msg in pendingSteerMessages"
        :key="msg.id"
        class="steer-bubble"
      >
        <span class="steer-bubble__text">{{ msg.content }}</span>
        <span class="steer-bubble__status">
          <span class="steer-bubble__dot"></span>
          插入中…
        </span>
      </div>
    </div>

    <!-- 附件预览 -->
    <div class="attachment-preview" v-if="attachments.length > 0">
      <div
        v-for="(att, idx) in attachments"
        :key="att.url"
        class="attachment-item"
      >
        <div class="attachment-thumb" v-if="att.type && att.type.startsWith('image/')" @click="previewAttachment(att)">
          <img :src="att.preview || att.url" alt="" />
        </div>
        <div class="attachment-thumb attachment-file" v-else>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
        </div>
        <button class="attachment-remove" @click="$emit('remove-attachment', idx)">×</button>
      </div>
    </div>

    <div class="input-container">
      <input type="file" ref="fileInputRef" accept="image/*,video/*,audio/*,application/*,text/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.zip,.rar,.7z,.csv,.json,.xml,.html,.css,.js,.py,.java,.md" style="display: none" @change="handleFileSelect" />

      <!-- 文本区 + 发送 -->
      <div class="input-row">
        <van-field
          :model-value="modelValue"
          :placeholder="voiceProcessing ? '正在识别语音...' : (uploading ? `上传中 ${uploadProgress}%...` : (attachments.length ? '添加文字说明（可选）...' : '发消息...'))"
          :border="false"
          type="textarea"
          rows="1"
          :autosize="{ maxHeight: 160, minHeight: 24 }"
          class="input-field"
          :disabled="uploading"
          @update:model-value="$emit('update:modelValue', $event)"
          @keydown.enter.exact="onSend"
          @keydown.enter.ctrl.prevent="insertNewline"
          @paste="handlePaste"
          @drop="handleDrop"
        />
        <button
          type="button"
          class="send-btn"
          @click="onSend"
          :disabled="(!modelValue.trim() && !attachments.length) || uploading"
          title="发送"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="19" x2="12" y2="5"/>
            <polyline points="5 12 12 5 19 12"/>
          </svg>
        </button>
      </div>

      <!-- 底部操作行：附件 + 模型选择 + 麦克风 -->
      <div class="action-row">
        <div class="action-row__left">
          <button
            type="button"
            class="attach-btn"
            @click="fileInputRef?.click()"
            :disabled="uploading || loading"
            title="附件"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <slot name="action-extra"></slot>
        </div>
        <button
          type="button"
          :class="['mic-btn', { 'mic-btn--active': voiceRecording, 'mic-btn--processing': voiceProcessing }]"
          @click="toggleVoice"
          :disabled="loading || voiceProcessing"
          :title="voiceRecording ? '点击停止录音' : (voiceProcessing ? '正在识别...' : '语音输入')"
        >
          <svg v-if="!voiceProcessing" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="voice-spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
          </svg>
          <span v-if="voiceRecording" class="mic-dot"></span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'
import { showImagePreview, showNotify } from 'vant'
import { API_BASE, TOKEN_KEY } from '../constants/index.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  uploading: { type: Boolean, default: false },
  uploadProgress: { type: Number, default: 0 },
  attachments: { type: Array, default: () => [] },
  pendingSteerMessages: { type: Array, default: () => [] },
})

const emit = defineEmits([
  'update:modelValue',
  'send',
  'abort',
  'upload',
  'remove-attachment',
])

const fileInputRef = ref(null)
const voiceRecording = ref(false)
const voiceProcessing = ref(false)
let mediaRecorder = null
let audioChunks = []

function toggleVoice() {
  if (voiceProcessing.value) return
  if (voiceRecording.value) {
    stopVoice()
    return
  }
  startVoice()
}

async function startVoice() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []

    const options = {}
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      options.mimeType = 'audio/webm;codecs=opus'
    } else if (MediaRecorder.isTypeSupported('audio/webm')) {
      options.mimeType = 'audio/webm'
    } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
      options.mimeType = 'audio/ogg;codecs=opus'
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      options.mimeType = 'audio/mp4'
    }

    mediaRecorder = new MediaRecorder(stream, options)
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data)
    }
    mediaRecorder.onerror = (e) => {
      console.error('[voice] recorder error:', e)
      stream.getTracks().forEach(t => t.stop())
      voiceRecording.value = false
      showNotify({ type: 'warning', message: '录音出错，请重试' })
    }
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop())
      voiceRecording.value = false
      if (audioChunks.length > 0) {
        sendVoiceToServer()
      } else {
        showNotify({ type: 'warning', message: '未录到音频，请重试' })
      }
    }
    mediaRecorder.start(1000)
    voiceRecording.value = true
  } catch (e) {
    console.error('[voice] start failed:', e)
    const msg = e?.name === 'NotAllowedError' ? '请允许麦克风权限后重试'
      : e?.name === 'NotFoundError' ? '未找到麦克风设备'
      : `录音启动失败: ${e?.message || e}`
    showNotify({ type: 'warning', message: msg })
  }
}

function stopVoice() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
}

async function sendVoiceToServer() {
  const mimeType = mediaRecorder?.mimeType || audioChunks[0]?.type || 'audio/webm'
  const blob = new Blob(audioChunks, { type: mimeType })
  audioChunks = []

  console.log('[voice] sending audio:', blob.size, 'bytes, type:', mimeType)

  if (blob.size < 100) {
    showNotify({ type: 'warning', message: '录音时间太短，请重试' })
    return
  }

  voiceProcessing.value = true
  try {
    const formData = new FormData()
    const ext = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('mp4') ? 'mp4' : 'webm'
    formData.append('audio', blob, `voice_${Date.now()}.${ext}`)

    const token = sessionStorage.getItem(TOKEN_KEY)
    const resp = await fetch(`${API_BASE}/stt`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })
    if (!resp.ok) {
      const err = await resp.text()
      console.error('[voice] stt HTTP error:', resp.status, err)
      throw new Error(`HTTP ${resp.status}`)
    }
    const data = await resp.json()
    const text = data.text || ''
    if (text) {
      const current = props.modelValue
      emit('update:modelValue', current ? current + '\n' + text : text)
    } else {
      showNotify({ type: 'warning', message: '未能识别语音内容' })
    }
  } catch (e) {
    console.error('[voice] stt failed:', e)
    showNotify({ type: 'warning', message: '语音识别失败，请重试' })
  } finally {
    voiceProcessing.value = false
  }
}

onUnmounted(() => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
})

function previewAttachment(att) {
  const src = att.preview || att.url
  if (!src) return
  showImagePreview({
    images: [src],
    closeable: true,
  })
}

function renameFile(file) {
  const ts = Date.now().toString().slice(-8)
  const dotIdx = file.name.lastIndexOf('.')
  const base = dotIdx > 0 ? file.name.slice(0, dotIdx) : file.name
  const ext = dotIdx > 0 ? file.name.slice(dotIdx) : ''
  return new File([file], `${ts}_${base}${ext}`, { type: file.type })
}

function insertNewline(e) {
  const ta = e.target
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const value = props.modelValue || ''
  const newValue = value.slice(0, start) + '\n' + value.slice(end)
  emit('update:modelValue', newValue)
  nextTick(() => {
    ta.focus()
    ta.selectionStart = ta.selectionEnd = start + 1
  })
}

function onSend(e) {
  if (props.uploading) {
    e?.preventDefault?.()
    return
  }
  emit('send', e)
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  emit('upload', renameFile(file))
  // reset input so same file can be re-selected
  e.target.value = ''
}

/**
 * 监听输入框的 paste 事件，自动提取剪贴板中的文件并上传
 */
function handlePaste(e) {
  const items = e.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (item.kind === 'file') {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) emit('upload', renameFile(file))
      return // 只处理第一个文件
    }
  }
}

/**
 * 监听输入框的 drop 事件，支持拖放文件
 */
function handleDrop(e) {
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return

  e.preventDefault()
  emit('upload', renameFile(files[0]))
}
</script>

<style>
/* ── Input Area (truly floating: absolute over content, fully transparent) ── */
.input-area {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 20;
  background: transparent;
  padding: 10px 0 max(8px, env(safe-area-inset-bottom));
  pointer-events: none;
}

/* ── Input Container (floating centered rounded white pill) ── */
.input-container {
  width: auto;
  max-width: 720px;
  margin: 0 auto;
  background: #FFFFFF;
  border: 1px solid var(--color-border);
  border-radius: 22px;
  box-shadow: var(--shadow-lg);
  padding: 8px 10px 8px 14px;
  pointer-events: auto;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.input-container:focus-within {
  border-color: rgba(var(--color-primary-rgb), 0.35);
  box-shadow: 0 4px 16px rgba(var(--color-primary-rgb), 0.08);
}

/* ── Input Row (text area + mic) ── */
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
}
.input-field.van-cell {
  flex: 1;
  background: transparent;
  border-radius: 0;
  border: none;
  box-shadow: none;
  padding: 6px 0;
  font-size: 15px;
  line-height: 1.5;
}
.input-field .van-field__control {
  color: var(--color-text);
}
.input-field .van-field__control::placeholder {
  color: var(--color-text-muted);
}

/* ── Mic Button (inside input, right) ── */
.mic-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  position: relative;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.mic-btn:active { transform: scale(0.92); }
.mic-btn:hover:not(:disabled) { background: var(--color-bg-secondary); }
.mic-btn:disabled { opacity: 0.4; }
.mic-btn--active {
  background: var(--color-danger);
  color: #FFFFFF;
  animation: voice-pulse 1.2s ease-in-out infinite;
}
.mic-dot {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger);
  animation: dot-blink 0.8s ease-in-out infinite;
}
@keyframes voice-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
}
@keyframes dot-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.mic-btn--processing {
  color: var(--color-primary);
}
.voice-spin {
  animation: voice-spin-anim 1s linear infinite;
}
@keyframes voice-spin-anim {
  to { transform: rotate(360deg); }
}

/* ── Action Row (attach + send, bottom of container) ── */
.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 4px;
}
.action-row__left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

/* ── Attach Button (Doubao "+" style) ── */
.attach-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.attach-btn:active { transform: scale(0.92); }
.attach-btn:hover:not(:disabled) { background: var(--color-bg-secondary); color: var(--color-text); }
.attach-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Send Button (Doubao style: filled circle on right) ── */
.send-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-primary);
  border: none;
  color: #FFFFFF;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.25);
  transition: transform var(--transition-fast), opacity var(--transition-fast), background var(--transition-fast);
}
.send-btn:active { transform: scale(0.92); }
.send-btn:disabled {
  background: var(--color-bg-tertiary);
  color: var(--color-text-muted);
  box-shadow: none;
  cursor: not-allowed;
}

/* ── Attachment Preview ── */
.attachment-preview {
  display: flex;
  gap: 8px;
  padding: 8px 14px 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  pointer-events: auto;
  max-width: 720px;
  margin: 0 auto;
}

/* ── Steer Pending Preview (悬挂在输入框上方的待插入消息) ── */
.steer-preview {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  padding: 6px 14px 0;
  max-width: 720px;
  margin: 0 auto;
  pointer-events: auto;
  animation: fadeInUp 0.25s ease;
}
.steer-bubble {
  max-width: 80%;
  padding: 8px 12px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(139, 92, 246, 0.06));
  border: 1px dashed rgba(99, 102, 241, 0.45);
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: anywhere;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.06);
}
.steer-bubble__text {
  white-space: pre-wrap;
  opacity: 0.85;
}
.steer-bubble__status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-primary);
  font-weight: 500;
}
.steer-bubble__dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: steer-blink 0.9s ease-in-out infinite;
}
@keyframes steer-blink {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.1); }
}
.attachment-item {
  position: relative;
  flex-shrink: 0;
  animation: fadeInUp 0.25s ease;
}
.attachment-thumb {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid var(--color-border);
  background: #FFFFFF;
  cursor: pointer;
}
.attachment-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.attachment-file {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
}
.attachment-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-danger);
  color: white;
  border: 2px solid var(--color-bg);
  font-size: 13px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  box-shadow: 0 2px 6px rgba(239, 68, 68, 0.4);
}
.attachment-remove:active {
  transform: scale(0.85);
}

/* ── Responsive: 手机端输入框保持悬浮居中，留出两侧边距 ── */
@media (max-width: 768px) {
  .input-container {
    width: auto;
    margin: 0 12px;
  }
}

</style>
