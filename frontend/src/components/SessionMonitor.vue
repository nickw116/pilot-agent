<template>
  <van-popup v-model:show="visible" position="left" :style="{ width: '78%', maxWidth: '360px', height: '100%' }" class="session-drawer">
    <div class="session-panel">
      <!-- Header -->
      <div class="session-header">
        <h3>全部会话</h3>
        <div class="session-header-actions">
          <van-button size="small" class="new-session-btn" @click="handleNew">
            <span class="new-session-btn__content">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              <span>新建</span>
            </span>
          </van-button>
          <van-button size="small" class="refresh-btn" @click="loadAllSessions">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"/>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
        </van-button>
        </div>
      </div>

      <!-- Agent Filter -->
      <div class="agent-filter">
        <div
          v-for="opt in agentOptions"
          :key="opt.id"
          :class="['agent-filter-item', { active: selectedAgentId === opt.id }]"
          @click="selectedAgentId = opt.id"
        >{{ opt.name }}</div>
      </div>

      <!-- Session List -->
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.sessionKey"
          :class="['session-item', { active: s.sessionKey === activeKey }]"
          @click="handleView(s)"
        >
          <div :class="['session-icon', `agent-${s.agentId}`]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="session-info">
            <div class="session-name">
              <span class="user-badge">{{ s.displayName || s.username }}</span>
              <span :class="['agent-badge', `agent-${s.agentId}`]">{{ getAgentName(s) }}</span>
            </div>
            <div class="session-meta">
              <span v-if="s.title" class="session-title">{{ s.title }}</span>
              <span class="session-time">{{ formatTime(s) }}</span>
              <span v-if="s.status === 'generating'" class="status-generating">生成中</span>
            </div>
            <div class="session-key-row">
              <span class="session-key" @click.stop="copyKey(s.sessionKey)" :title="s.sessionKey">{{ s.sessionKey }}</span>
            </div>
          </div>
          <div class="session-actions">
            <div v-if="s.sessionKey === activeKey" class="session-active-badge">当前</div>
            <button v-if="s.username === props.currentUsername" @click.stop="handleDelete(s)" class="session-delete-btn">删除</button>
          </div>
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
import { API_BASE, API_ADMIN_SESSIONS } from '../constants/index.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  token: { type: String, default: '' },
  agents: { type: Array, default: () => [] },
  currentSessionKey: { type: String, default: '' },
  currentUsername: { type: String, default: '' },
  monitorSessionKey: { type: String, default: '' },
})

const activeKey = computed(() => props.monitorSessionKey || props.currentSessionKey)

const emit = defineEmits(['update:show', 'view-session', 'new', 'delete'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const sessions = ref([])
const loading = ref(false)
const selectedAgentId = ref('')

const agentOptions = computed(() => {
  const list = [{ id: '', name: '全部' }]
  for (const a of props.agents) {
    list.push({ id: a.id, name: a.name || a.id })
  }
  return list
})

watch(() => props.show, (v) => {
  if (v) loadAllSessions()
})

async function loadAllSessions() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (selectedAgentId.value) params.set('agent_id', selectedAgentId.value)
    params.set('all', '1')
    const r = await fetch(`${API_BASE}${API_ADMIN_SESSIONS}?${params}`, {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    if (r.ok) {
      const data = await r.json()
      sessions.value = data.sessions || []
    }
  } catch (err) {
    console.error('[SessionMonitor] load failed:', err)
  } finally {
    loading.value = false
  }
}

function handleView(s) {
  emit('view-session', s)
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
      message: '确定要删除这个会话吗？此操作不可恢复。',
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
    console.error('[SessionMonitor] delete failed:', err)
  }
}

function copyKey(key) {
  navigator.clipboard.writeText(key).catch(() => {})
}

function getAgentName(s) {
  const agentId = s.agentId || ''
  return props.agents.find(a => a.id === agentId)?.name || agentId || '会话'
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
.session-header-actions {
  display: flex;
  gap: 8px;
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
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
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
.refresh-btn {
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}
.refresh-btn.van-button {
  background: var(--color-bg-glass);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 0 10px;
  height: 32px;
}
.refresh-btn:active { transform: scale(0.95); }

/* ── Agent Filter ── */
.agent-filter {
  display: flex;
  gap: 6px;
  padding: 10px 14px;
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
}
.agent-filter-item {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-glass);
  border: 1.5px solid var(--color-border);
  cursor: pointer;
  transition: all 0.2s ease;
}
.agent-filter-item.active {
  color: white;
  background: var(--color-accent);
  border-color: var(--color-primary);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
}

/* ── Session list ── */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  -webkit-overflow-scrolling: touch;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 14px;
  border-radius: 14px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-bg-glass);
  border: 1.5px solid transparent;
}
.session-item:hover {
  background: var(--color-bg-glass-hover);
  border-color: var(--color-border-glow);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.06);
}
.session-item:active {
  transform: scale(0.98);
  background: rgba(99, 102, 241, 0.03);
}
.session-item.active {
  background: rgba(99, 102, 241, 0.04);
  border-color: var(--color-primary);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.08);
}
.session-item.active .session-icon {
  background: var(--color-accent);
  color: white;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
}
.session-item.active .user-badge {
  color: var(--color-primary);
}

/* Session icon */
.session-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.session-icon.agent-main {
  background: rgba(99, 102, 241, 0.08);
  color: var(--color-primary);
}
.session-icon.agent-dev {
  background: rgba(0, 229, 160, 0.1);
  color: var(--color-success);
}
.session-icon.agent-user {
  background: rgba(139, 139, 158, 0.1);
  color: var(--color-text-secondary);
}

/* Session info */
.session-info {
  flex: 1;
  min-width: 0;
}
.session-name {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.3;
}
.user-badge {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.agent-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.agent-badge.agent-main { background: rgba(99, 102, 241, 0.08); color: var(--color-primary); }
.agent-badge.agent-dev { background: rgba(0, 229, 160, 0.1); color: var(--color-success); }
.agent-badge.agent-user { background: rgba(139, 139, 158, 0.1); color: var(--color-text-secondary); }

.session-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}
.session-title {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}
.session-time {
  font-size: 12px;
  color: var(--color-text-muted);
}
.session-key-row {
  margin-top: 3px;
}
.session-key {
  font-size: 10px;
  color: var(--color-text-muted);
  opacity: 0.6;
  font-family: 'SF Mono', 'Menlo', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  cursor: pointer;
}
.session-key:hover {
  opacity: 1;
  color: var(--color-primary);
}

/* Generating status */
.status-generating {
  font-size: 10px;
  color: var(--color-warning);
  font-weight: 600;
  animation: pulse-opacity 1.5s ease-in-out infinite;
}
@keyframes pulse-opacity {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* View button & Active badge — shared alignment */
.session-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.session-view-btn,
.session-active-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  line-height: 20px;
  padding: 2px 10px;
  border-radius: 6px;
  white-space: nowrap;
  align-self: center;
}
.session-view-btn {
  color: var(--color-primary);
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.1);
  transition: all 0.2s ease;
}
.session-item:hover .session-view-btn {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.15);
}
.session-active-badge {
  color: var(--color-primary);
  background: rgba(99, 102, 241, 0.06);
}
.session-delete-btn {
  flex-shrink: 0;
  padding: 3px 8px;
  border: none;
  border-radius: 5px;
  background: rgba(255, 71, 87, 0.07);
  color: var(--color-danger);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  line-height: 1.4;
}
.session-delete-btn:active {
  background: rgba(255, 71, 87, 0.2);
  transform: scale(0.92);
}

/* Empty state */
.session-empty {
  text-align: center;
  color: var(--color-text-muted);
  font-size: 14px;
  padding: 40px 0;
}
</style>
