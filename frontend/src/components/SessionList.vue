<template>
  <van-popup v-model:show="visible" position="left" :style="{ width: '78%', maxWidth: '360px', height: '100%' }" class="session-drawer">
    <div class="session-panel">
      <!-- Header -->
      <div class="session-header">
        <h3>会话列表</h3>
        <van-button size="small" class="new-session-btn" @click="handleNew">
          <span class="new-session-btn__content">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            <span>新建</span>
          </span>
        </van-button>
      </div>

      <!-- Session List -->
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.sessionKey"
          :class="['session-item', { active: s.active }]"
          @click="handleSwitch(s)"
        >
          <div class="session-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="session-info">
            <div class="session-name">{{ getAgentName(s) }}</div>
            <div class="session-time">{{ formatTime(s) }}</div>
            <div class="session-key" @click.stop="copyKey(s.sessionKey)" :title="s.sessionKey">{{ s.sessionKey }}</div>
          </div>
          <div v-if="s.active" class="session-active-badge">当前</div>
          <button v-if="!s.active" @click.stop="handleDelete(s)" class="session-delete-btn">删除</button>
        </div>

        <div v-if="sessions.length === 0 && !loading" class="session-empty">
          暂无会话
        </div>
        <div v-if="loading" class="session-empty">加载中...</div>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { showConfirmDialog } from 'vant'
import { API_BASE, API_SESSIONS, API_SESSION_NEW } from '../constants/index.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  token: { type: String, default: '' },
  currentSessionKey: { type: String, default: '' },
  currentAgentId: { type: String, default: 'main' },
  agents: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:show', 'switch', 'new', 'delete'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const sessions = ref([])
const loading = ref(false)

// Refresh session list when drawer opens or agent changes
watch([() => props.show, () => props.currentAgentId], ([v]) => {
  if (v) loadSessions()
})

async function loadSessions() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (props.currentAgentId) params.set('agent_id', props.currentAgentId)
    const r = await fetch(`${API_BASE}${API_SESSIONS}?${params}`, {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    if (r.ok) {
      const data = await r.json()
      sessions.value = data.sessions || []
    }
  } catch (err) {
    console.error('[SessionList] load failed:', err)
  } finally {
    loading.value = false
  }
}

function handleSwitch(s) {
  if (s.active) {
    visible.value = false
    return
  }
  emit('switch', s.sessionKey)
  sessions.value.forEach(item => { item.active = false })
  const target = sessions.value.find(item => item.sessionKey === s.sessionKey)
  if (target) target.active = true
  visible.value = false
}

async function handleNew() {
  emit('new')
  visible.value = false
}

async function handleDelete(s) {
  try {
    await showConfirmDialog({
      title: '删除会话',
      message: '确定要删除这个会话吗？',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonColor: '#FF4757',
    })
  } catch {
    return
  }
  try {
    const r = await fetch(`${API_BASE}/session/${encodeURIComponent(s.sessionKey)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${props.token}` },
    })
    if (r.ok) {
      sessions.value = sessions.value.filter(x => x.sessionKey !== s.sessionKey)
      emit('delete', s.sessionKey)
    }
  } catch (err) {
    console.error('[SessionList] delete failed:', err)
  }
}

function getAgentName(s) {
  const agentId = s.agentId || ''
  return props.agents.find(a => a.id === agentId)?.name || agentId || '会话'
}

function copyKey(key) {
  navigator.clipboard.writeText(key).catch(() => {})
}

function formatTime(s) {
  const ts = s.createdAt
  if (!ts) return ''
  const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}/${dd} ${hh}:${mi}`
}
</script>

<style scoped>
.session-drawer.van-popup {
  background: var(--color-bg-secondary);
}
.session-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 18px 14px;
  border-bottom: 1px solid var(--color-border);
}
.session-header h3 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}
.new-session-btn {
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}
.new-session-btn.van-button {
  background: var(--color-accent);
  border: none;
  color: white;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
  padding: 0 12px;
  height: 32px;
}
.new-session-btn .van-button__content {
  display: flex;
  align-items: center;
  justify-content: center;
}
.new-session-btn__content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  line-height: 1;
}
.new-session-btn:active { transform: scale(0.95); }

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  -webkit-overflow-scrolling: touch;
}
.session-list .van-swipe-cell {
  margin-bottom: 6px;
  border-radius: 14px;
  overflow: hidden;
}
.session-delete-btn {
  flex-shrink: 0;
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: rgba(255, 71, 87, 0.1);
  color: var(--color-danger);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.session-delete-btn:active {
  background: rgba(255, 71, 87, 0.2);
  transform: scale(0.92);
}
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-bg-glass);
  border: 1.5px solid transparent;
  border-radius: 12px;
  margin-bottom: 8px;
}
.session-item:hover {
  background: var(--color-bg-glass-hover);
}
.session-item:active {
  transform: scale(0.98);
}
.session-item.active {
  background: rgba(99, 102, 241, 0.06);
  border-color: var(--color-primary);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.06);
}

.session-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.08);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.session-item.active .session-icon {
  background: var(--color-primary);
  color: var(--color-bg);
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.15);
}

.session-info {
  flex: 1;
  min-width: 0;
}
.session-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}
.session-time {
  font-size: 12px;
  color: var(--color-text-muted);
  line-height: 1.3;
  margin-top: 2px;
}
.session-key {
  font-size: 10px;
  color: var(--color-text-muted);
  opacity: 0.6;
  font-family: 'SF Mono', 'Menlo', monospace;
  word-break: break-all;
  line-height: 1.4;
  margin-top: 2px;
  cursor: pointer;
}
.session-key:hover {
  opacity: 1;
  color: var(--color-primary);
}
.session-item.active .session-name {
  color: var(--color-primary);
  font-weight: 600;
}

.delete-btn {
  height: 100% !important;
  border: none !important;
  border-radius: 0 !important;
  font-size: 14px !important;
  font-weight: 600 !important;
}

.session-active-badge {
  font-size: 11px;
  color: var(--color-primary);
  font-weight: 600;
  flex-shrink: 0;
  padding: 2px 8px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 6px;
}

.session-empty {
  text-align: center;
  color: var(--color-text-muted);
  font-size: 14px;
  padding: 40px 0;
}
</style>
