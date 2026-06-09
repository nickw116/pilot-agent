<template>
  <div class="chat-page">
    <van-nav-bar fixed placeholder class="nav-bar">
      <template #left>
        <div class="nav-left-actions">
          <div
            class="nav-btn-wrapper nav-monitor-btn"
            @click="$emit('open-sessions')"
            title="会话列表"
          >
            <van-icon name="bars" class="nav-action-icon" />
          </div>
        </div>
      </template>
      <template #title>
        <div class="nav-title-wrap">
          <span v-if="props.monitorMode" class="nav-title nav-title--monitor">MONITOR</span>
          <div class="nav-sub-row">
            <button
              v-if="props.currentModel"
              class="nav-model-btn"
              @click="openModelPicker"
              :disabled="props.loading"
            >
              <span class="nav-model-text">{{ props.currentModel }}</span>
              <van-icon name="arrow-down" class="nav-model-arrow" />
            </button>
          </div>
        </div>
      </template>
      <template #right>
        <div class="nav-right-actions">
          <div v-if="props.canAccessMonitor" class="nav-btn-wrapper" @click="$emit('open-dashboard')" title="Agent 看板">
            <van-icon name="cluster-o" class="nav-action-icon nav-action-icon--dashboard" />
          </div>
          <div class="nav-btn-wrapper" @click="reloadPage" :class="{ 'is-loading': refreshing }">
            <van-icon :name="refreshing ? '' : 'replay'" class="nav-action-icon nav-action-icon--refresh">
              <template v-if="refreshing"><van-loading type="spinner" size="18" color="currentColor" /></template>
            </van-icon>
          </div>
          <div class="nav-btn-wrapper" @click="$emit('open-settings')">
            <van-icon name="setting-o" class="nav-action-icon nav-action-icon--setting" />
          </div>
        </div>
      </template>
    </van-nav-bar>

    <!-- 服务状态提示条 -->
    <transition name="banner-slide">
      <div v-if="serviceStatus === 'down'" class="service-banner service-banner--down">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>服务正在重启，请稍候…</span>
      </div>
      <div v-else-if="serviceStatus === 'recovered'" class="service-banner service-banner--recovered">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        <span>服务已恢复</span>
      </div>
    </transition>

    <!-- 历史消息加载中 -->
    <div v-if="(props.monitorMode ? props.monitorHistoryLoading : props.historyLoading) && (props.monitorMode ? props.monitorMessages : props.messages).length === 0" class="history-loading">
      <div class="history-loading__spinner">
        <div class="history-loading__ring"></div>
      </div>
      <div class="history-loading__text">加载历史消息…</div>
    </div>

    <!-- Monitor mode read-only banner -->
    <div v-else-if="props.monitorMode && props.monitorMessages.length === 0" class="empty-state">
      <div class="empty-greeting">暂无消息</div>
    </div>

    <!-- 空会话引导区 -->
    <div v-else-if="!props.monitorMode && props.messages.length === 0" class="empty-state">
      <div class="empty-greeting">有什么我能帮你的吗？</div>
      <div class="empty-cards">
        <button
          v-for="(card, idx) in suggestionCards"
          :key="idx"
          class="empty-card"
          @click="fillSuggestion(card.text)"
        >
          <span class="empty-card-icon">{{ card.icon }}</span>
          <span class="empty-card-text">{{ card.text }}</span>
        </button>
      </div>
    </div>

    <MessageList
      v-else
      ref="messageListRef"
      :messages="props.monitorMode ? props.monitorMessages : props.messages"
      :loading="props.monitorMode ? false : props.loading"
      :format-file-size="props.formatFileSize"
      :file-icon="props.fileIcon"
      :acp-logs="props.acpLogs"
      :acp-status="props.acpStatus"
      :current-agent-id="props.currentAgentId"
      @load-more="emit('load-more')"
    />

    <!-- Monitor mode: interactive banner + input -->
    <template v-if="props.monitorMode">
      <div class="monitor-banner monitor-banner--interactive">
        <span class="monitor-banner__info">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          代入会话: {{ props.monitorUserInfo }}
        </span>
        <button class="monitor-exit-btn" @click="emit('exit-monitor')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <MessageInput
        v-model="monitorInputText"
        :loading="monitorLoading"
        :uploading="false"
        :upload-progress="0"
        :attachments="[]"
        @send="monitorSend"
        @abort="monitorAbort"
        @upload="() => {}"
        @remove-attachment="() => {}"
      />
    </template>

    <!-- Normal mode: message input -->
    <MessageInput
      v-else
      v-model="inputText"
      :loading="loading"
      :uploading="uploading"
      :upload-progress="uploadProgress"
      :attachments="attachments"
      @send="send"
      @abort="abort"
      @upload="(file) => $emit('upload', file)"
      @remove-attachment="(idx) => $emit('remove-attachment', idx)"
    />

    <!-- 模型选择器 -->
    <van-action-sheet
      v-model:show="modelPickerVisible"
      :actions="modelActions"
      cancel-text="取消"
      description="选择模型"
      close-on-click-action
      @select="onModelSelect"
    />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, computed } from 'vue'
import { API_BASE, TOKEN_KEY } from '../constants/index.js'
import MessageInput from '../components/MessageInput.vue'
import MessageList from '../components/MessageList.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  inputText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  historyLoading: { type: Boolean, default: false },
  uploading: { type: Boolean, default: false },
  uploadProgress: { type: Number, default: 0 },
  attachments: { type: Array, default: () => [] },
  formatFileSize: { type: Function, default: () => '' },
  fileIcon: { type: Function, default: () => '📄' },
  serviceStatus: { type: String, default: 'up' },  // 'up' | 'down' | 'recovered'
  currentModel: { type: String, default: '' },
  sseConnected: { type: Boolean, default: false },
  sseReconnecting: { type: Boolean, default: false },
  acpStatus: { type: Object, default: () => ({ count: 0, runs: [] }) },
  acpLogs: { type: Array, default: () => [] },
  acpBridge: { type: Object, default: () => null },
  models: { type: Array, default: () => [] },
  sessionKey: { type: String, default: '' },
  currentAgentId: { type: String, default: 'main' },
  monitorMode: { type: Boolean, default: false },
  monitorMessages: { type: Array, default: () => [] },
  monitorHistoryLoading: { type: Boolean, default: false },
  monitorUserInfo: { type: String, default: '' },
  monitorLoading: { type: Boolean, default: false },
  canAccessMonitor: { type: Boolean, default: false },
})

const emit = defineEmits(['update:inputText', 'send', 'abort', 'upload', 'remove-attachment', 'open-settings', 'hot-refresh', 'switch-model', 'load-more', 'open-sessions', 'open-monitor', 'open-dashboard', 'monitor-send', 'monitor-abort', 'exit-monitor'])

// ── 模型选择器 ──
const modelPickerVisible = ref(false)

const modelActions = computed(() => {
  // 兜底：如果后端 models 为空但 currentModel 有值，至少把当前模型放进去
  const list = props.models.length > 0
    ? props.models
    : (props.currentModel ? [props.currentModel] : [])
  return list.map((m) => {
    const isObj = m && typeof m === 'object'
    const name = isObj ? (m.name || m.id || m.model || String(m)) : String(m)
    const value = isObj ? (m.id || m.model || m.name || String(m)) : String(m)
    return {
      name,
      value,
      color: value === props.currentModel ? 'var(--color-primary)' : undefined,
    }
  })
})

function openModelPicker() {
  if (props.loading) return
  modelPickerVisible.value = true
}

function onModelSelect(action) {
  const value = action.value || action.name
  if (value && value !== props.currentModel) {
    emit('switch-model', value)
  }
}

const messageListRef = ref(null)

onMounted(() => {
  // placeholder for any mount-time setup
})

const inputText = ref(props.inputText)
watch(() => props.inputText, (v) => { inputText.value = v })
watch(inputText, (v) => { emit('update:inputText', v) })

function send(e) {
  if (props.uploading) {
    e?.preventDefault?.()
    return
  }
  nextTick(() => messageListRef.value?.scrollToBottom())
  emit('send', e)
}

function abort() {
  emit('abort')
}

const refreshing = ref(false)

function reloadPage() {
  if (refreshing.value) return
  refreshing.value = true
  emit('hot-refresh')
  setTimeout(() => { refreshing.value = false }, 1500)
}

const suggestionCards = [
  { icon: '💡', text: '帮我写一段Python爬虫代码' },
  { icon: '📝', text: '帮我写一封工作周报' },
  { icon: '🔍', text: '解释一下什么是RAG技术' },
  { icon: '🛠️', text: '如何优化React应用性能' },
  { icon: '📊', text: '帮我分析一组销售数据' },
  { icon: '🌐', text: '把这段话翻译成英文' },
]

function fillSuggestion(text) {
  inputText.value = text
}

// ── Monitor mode input ──
const monitorInputText = ref('')

function monitorSend(e) {
  const text = monitorInputText.value.trim()
  if (!text) return
  monitorInputText.value = ''
  emit('monitor-send', text)
}

function monitorAbort() {
  emit('monitor-abort')
}
</script>

<style>
/* ── Chat Page ── */
.chat-page {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}

/* ── Nav Bar ── */
.nav-bar {
  background: var(--color-bg-secondary) !important;
  border-bottom: 1px solid var(--color-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.nav-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--color-text);
}
.nav-title-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  line-height: 1.2;
  max-width: 100%;
  overflow: hidden;
}
.nav-model {
  font-size: 11px;
  color: var(--color-text-muted);
  font-weight: 400;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-model-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border-glow);
  font-size: 11px;
  color: var(--color-primary);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  outline: none;
  max-width: 160px;
}
.nav-model-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.nav-model-btn:active:not(:disabled) {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.2);
  transform: scale(0.96);
  box-shadow: var(--shadow-glow);
}
.nav-model-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-model-arrow {
  font-size: 10px;
  color: var(--color-primary);
  flex-shrink: 0;
  transition: transform var(--transition-normal);
}
.nav-model-btn:active:not(:disabled) .nav-model-arrow {
  transform: rotate(180deg);
}
.nav-sub-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 1px;
  max-width: 100%;
  overflow: hidden;
}
.nav-bar .van-nav-bar__title {
  color: var(--color-text);
  margin: 0 auto;
  max-width: calc(100% - 140px);
  padding: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-bar .van-nav-bar__arrow { color: var(--color-text); }

.nav-bar .van-nav-bar__right.van-haptics-feedback:active,
.nav-bar .van-nav-bar__left.van-haptics-feedback:active {
  opacity: 1 !important;
}

.nav-bar .van-nav-bar__right,
.nav-bar .van-nav-bar__left,
.nav-bar .van-nav-bar__content,
.nav-right-actions {
  -webkit-tap-highlight-color: transparent !important;
  tap-highlight-color: transparent !important;
}

.nav-right-actions {
  display: flex;
  align-items: center;
  gap: 0;
  margin-right: -12px;
}
.nav-btn-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  position: relative;
  isolation: isolate;
  -webkit-tap-highlight-color: transparent;
  tap-highlight-color: transparent;
  touch-action: manipulation;
  outline: none;
  -webkit-user-select: none;
  user-select: none;
  cursor: pointer;
  border-radius: 8px;
  transition: background var(--transition-fast);
}
.nav-btn-wrapper:active {
  background: rgba(99, 102, 241, 0.08);
}
.nav-action-icon {
  font-size: 20px;
  color: var(--color-text-secondary);
  pointer-events: none;
  transition: transform 0.35s ease, color 0.2s ease;
}
@media (hover: hover) {
  .nav-btn-wrapper:hover .nav-action-icon {
    color: var(--color-primary);
  }
  .nav-btn-wrapper:hover {
    background: rgba(99, 102, 241, 0.06);
  }
  .nav-btn-wrapper:hover .nav-action-icon--refresh {
    transform: rotate(-120deg);
  }
  .nav-btn-wrapper:hover .nav-action-icon--setting {
    transform: rotate(90deg);
  }
}
.nav-btn-wrapper:active .nav-action-icon--refresh {
  transform: scale(0.9) rotate(-60deg);
  color: var(--color-primary);
}
.nav-btn-wrapper.is-loading .nav-action-icon--refresh {
  animation: spin 0.8s linear infinite;
  pointer-events: none;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.nav-btn-wrapper:active .nav-action-icon--setting {
  transform: scale(0.9) rotate(45deg);
  color: var(--color-primary);
}
.nav-btn-wrapper:active .nav-action-icon--dashboard {
  transform: scale(0.9);
  color: var(--color-primary);
}

.nav-menu-icon {
  font-size: 22px;
  color: var(--color-text);
  cursor: pointer;
  padding: 8px;
  margin: -8px;
  transition: transform 0.3s ease;
}
.nav-menu-icon:active { transform: scale(0.9); }

.nav-left-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* ── Service Status Banner ── */
.service-banner {
  position: fixed;
  top: 46px;
  left: 0;
  right: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.service-banner--down {
  background: rgba(255, 184, 0, 0.1);
  color: var(--color-warning);
  border-bottom: 1px solid rgba(255, 184, 0, 0.2);
}
.service-banner--recovered {
  background: rgba(0, 229, 160, 0.1);
  color: var(--color-success);
  border-bottom: 1px solid rgba(0, 229, 160, 0.2);
}

/* ── Banner Transition ── */
.banner-slide-enter-active,
.banner-slide-leave-active {
  transition: all 0.35s ease;
}
.banner-slide-enter-from,
.banner-slide-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

/* ── History Loading ── */
.history-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
}
.history-loading__spinner {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.history-loading__ring {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(99, 102, 241, 0.1);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: history-spin 0.8s linear infinite;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.1);
}
.history-loading__text {
  font-size: 14px;
  color: var(--color-text-secondary);
  animation: history-fade 1.5s ease-in-out infinite;
}
@keyframes history-spin {
  to { transform: rotate(360deg); }
}
@keyframes history-fade {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

/* ── Empty State ── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
}
.empty-greeting {
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text);
  text-align: center;
  margin-bottom: 24px;
}
.empty-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  max-width: 400px;
}
.empty-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--color-bg-glass);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border);
  border-radius: 24px;
  cursor: pointer;
  text-align: left;
  font-size: 14px;
  color: var(--color-text);
  transition: all var(--transition-normal);
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}
.empty-card:active {
  background: var(--color-bg-glass-hover);
  border-color: var(--color-border-glow);
  box-shadow: var(--shadow-glow);
}
@media (hover: hover) {
  .empty-card:hover {
    background: var(--color-bg-glass-hover);
    border-color: var(--color-border-glow);
    box-shadow: var(--shadow-glow);
  }
}
.empty-card-icon {
  font-size: 18px;
  flex-shrink: 0;
}
.empty-card-text {
  flex: 1;
}

/* ── Monitor Nav Button ── */
.nav-monitor-btn {
  margin-left: 2px;
}
.nav-monitor-btn:active svg {
  color: var(--color-primary);
  transform: scale(0.9);
}
.nav-title--monitor {
  color: var(--color-warning);
  letter-spacing: 1px;
}

/* ── Monitor Interactive Banner ── */
.monitor-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  border-top: 1px solid rgba(99, 102, 241, 0.15);
  gap: 10px;
}
.monitor-banner--interactive {
  background: rgba(99, 102, 241, 0.06);
}
.monitor-banner__info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
.monitor-exit-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: rgba(99, 102, 241, 0.08);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.monitor-exit-btn:active {
  background: rgba(99, 102, 241, 0.2);
  transform: scale(0.9);
}
</style>
