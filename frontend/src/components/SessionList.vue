<template>
  <van-popup v-model:show="visible" position="left" :style="{ width: '78%', maxWidth: '360px', height: '100%' }" class="session-drawer">
    <div class="session-panel">
      <!-- Header -->
      <div class="session-header">
        <h3>{{ multiSelect ? `已选 ${selectedKeys.length} 个会话` : '会话列表' }}</h3>
        <div class="session-header__actions">
          <van-button v-if="!multiSelect" size="small" class="new-session-btn" @click="handleNew">
            <span class="new-session-btn__content">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              <span>新建</span>
            </span>
          </van-button>
          <van-button v-if="!multiSelect" size="small" class="multi-select-btn" @click="enterMultiSelect">多选</van-button>
          <van-button v-else size="small" class="multi-select-btn" @click="exitMultiSelect">取消</van-button>
        </div>
      </div>

      <!-- Search -->
      <div class="session-search">
        <svg class="session-search__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          class="session-search__input"
          placeholder="搜索会话..."
        >
        <button
          v-if="searchQuery"
          class="session-search__clear"
          @click="searchQuery = ''"
          aria-label="清除"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Session List -->
      <div class="session-list">
        <div
          v-for="s in filteredSessions"
          :key="s.sessionKey"
          :class="['session-item', { active: s.active, selected: multiSelect && selectedKeys.includes(s.sessionKey) }]"
          @click="handleItemClick(s)"
        >
          <van-checkbox
            v-if="multiSelect"
            class="session-check"
            :model-value="selectedKeys.includes(s.sessionKey)"
            :disabled="s.active"
            @click.stop="toggleSelect(s)"
          />
          <div v-else class="session-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="session-info">
            <div class="session-name">{{ s.title || getSessionLabel(s) }}</div>
            <div class="session-time">{{ formatTime(s) }}</div>
          </div>
          <div v-if="s.active" class="session-active-badge">当前</div>
          <button v-if="!multiSelect && !s.active" @click.stop="handleDelete(s)" class="session-delete-btn">删除</button>
        </div>

        <div v-if="sessions.length === 0 && !loading" class="session-empty">
          暂无会话
        </div>
        <div v-else-if="filteredSessions.length === 0 && !loading" class="session-empty">
          未找到匹配的会话
        </div>
        <div v-if="loading" class="session-empty">加载中...</div>
      </div>

      <div v-if="multiSelect" class="session-batch-bar">
        <button class="batch-select-all" @click="toggleSelectAll">
          {{ allSelected ? '取消全选' : '全选' }}
        </button>
        <button
          class="batch-delete-btn"
          :disabled="selectedKeys.length === 0 || batchDeleting"
          @click="handleBatchDelete"
        >
          {{ batchDeleting ? '删除中...' : `删除(${selectedKeys.length})` }}
        </button>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { showConfirmDialog, showNotify } from 'vant'
import { API_BASE, API_SESSIONS, API_SESSION_NEW } from '../constants/index.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  token: { type: String, default: '' },
  currentSessionKey: { type: String, default: '' },
  currentAgentId: { type: String, default: 'user' },
  agents: { type: Array, default: () => [] },
  agentTypes: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:show', 'switch', 'new', 'delete'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const sessions = ref([])
const loading = ref(false)
const searchQuery = ref('')

const multiSelect = ref(false)
const selectedKeys = ref([])
const batchDeleting = ref(false)

const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sessions.value
  return sessions.value.filter((s) => {
    const title = (s.title || '').toLowerCase()
    const label = getSessionLabel(s).toLowerCase()
    const agentName = getAgentName(s).toLowerCase()
    return (
      title.includes(q) ||
      label.includes(q) ||
      agentName.includes(q)
    )
  })
})

const selectableSessions = computed(() => filteredSessions.value.filter(s => !s.active))
const allSelected = computed(() =>
  selectableSessions.value.length > 0 &&
  selectableSessions.value.every(s => selectedKeys.value.includes(s.sessionKey))
)

// Clear search when drawer closes
watch(visible, (v) => {
  if (!v) {
    searchQuery.value = ''
    exitMultiSelect()
  }
})

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
    } else {
      const data = await r.json().catch(() => null)
      showNotify({ type: 'danger', message: `删除失败: ${data?.detail || `错误码 ${r.status}`}` })
    }
  } catch (err) {
    console.error('[SessionList] delete failed:', err)
    showNotify({ type: 'danger', message: '删除失败，请检查网络后重试' })
  }
}

function enterMultiSelect() {
  multiSelect.value = true
  selectedKeys.value = []
}

function exitMultiSelect() {
  multiSelect.value = false
  selectedKeys.value = []
}

function handleItemClick(s) {
  if (multiSelect.value) {
    toggleSelect(s)
  } else {
    handleSwitch(s)
  }
}

function toggleSelect(s) {
  if (s.active) return
  const i = selectedKeys.value.indexOf(s.sessionKey)
  if (i >= 0) selectedKeys.value.splice(i, 1)
  else selectedKeys.value.push(s.sessionKey)
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedKeys.value = []
  } else {
    selectedKeys.value = selectableSessions.value.map(s => s.sessionKey)
  }
}

async function handleBatchDelete() {
  if (selectedKeys.value.length === 0 || batchDeleting.value) return
  try {
    await showConfirmDialog({
      title: '批量删除会话',
      message: `确定要删除选中的 ${selectedKeys.value.length} 个会话吗？此操作不可恢复。`,
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonColor: '#FF4757',
    })
  } catch {
    return
  }
  batchDeleting.value = true
  let okCount = 0
  const failKeys = []
  for (const key of [...selectedKeys.value]) {
    try {
      const r = await fetch(`${API_BASE}/session/${encodeURIComponent(key)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${props.token}` },
      })
      if (r.ok) {
        okCount++
        sessions.value = sessions.value.filter(x => x.sessionKey !== key)
        emit('delete', key)
      } else {
        failKeys.push(key)
      }
    } catch (err) {
      console.error('[SessionList] batch delete failed:', key, err)
      failKeys.push(key)
    }
  }
  batchDeleting.value = false
  if (failKeys.length === 0) {
    showNotify({ type: 'success', message: `已删除 ${okCount} 个会话` })
    exitMultiSelect()
  } else {
    selectedKeys.value = failKeys
    showNotify({ type: 'danger', message: `已删除 ${okCount} 个，${failKeys.length} 个失败` })
  }
}

function getAgentName(s) {
  const agentId = s.agentId || ''
  return props.agents.find(a => a.id === agentId)?.name || agentId || '会话'
}

function getSessionLabel(s) {
  const atype = s.agentType
  const typeMeta = props.agentTypes.find((t) => t.id === atype)
  if (typeMeta) return `${typeMeta.icon} ${typeMeta.name}`
  return getAgentName(s)
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

.session-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.multi-select-btn.van-button {
  background: transparent;
  border: 1.5px solid var(--color-border);
  color: var(--color-text-secondary);
  padding: 0 12px;
  height: 32px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}
.multi-select-btn.van-button:active { transform: scale(0.95); }

.session-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 12px 4px;
  padding: 8px 12px;
  background: var(--color-bg-glass);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.session-search:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}
.session-search__icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}
.session-search__input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.4;
}
.session-search__input::placeholder {
  color: var(--color-text-muted);
}
.session-search__clear {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--color-text-muted);
  color: var(--color-bg);
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
}
.session-search__clear:hover {
  background: var(--color-text-secondary);
}
.session-search__clear:active {
  transform: scale(0.85);
}

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
.session-item.active .session-name {
  color: var(--color-primary);
  font-weight: 600;
}

.session-item.selected {
  background: rgba(99, 102, 241, 0.06);
  border-color: var(--color-primary);
}
.session-check {
  flex-shrink: 0;
}

.session-batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}
.batch-select-all {
  flex-shrink: 0;
  border: 1.5px solid var(--color-border);
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s;
}
.batch-select-all:active { transform: scale(0.95); }
.batch-delete-btn {
  flex: 1;
  border: none;
  background: var(--color-danger);
  color: white;
  border-radius: 10px;
  padding: 9px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.15s;
}
.batch-delete-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.batch-delete-btn:not(:disabled):active { transform: scale(0.97); }

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
