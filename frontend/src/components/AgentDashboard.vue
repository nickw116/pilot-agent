<template>
  <van-popup
    v-model:show="visible"
    position="right"
    :style="{ width: '78%', maxWidth: '360px', height: '100%' }"
    class="agent-dashboard-drawer"
  >
    <div class="dashboard-panel">
      <!-- Header -->
      <div class="dashboard-header">
        <h3 class="dashboard-title">Agent 看板</h3>
        <span class="dashboard-summary">
          <span v-for="(s, id) in agentStates" :key="id" class="summary-dot" :class="`dot-${s.status}`" :title="s.agentName"></span>
          <span class="summary-text">{{ workingCount }}/{{ totalAgents }} 运行中</span>
        </span>
      </div>

      <!-- Agent cards -->
      <div class="dashboard-body">
        <div
          v-for="agent in sortedAgents"
          :key="agent.agentId"
          :class="['agent-card', `card-${agent.agentId}`, { 'card-working': agent.status === 'working' }]"
        >
          <!-- Card header -->
          <div class="card-header">
            <span :class="['card-icon', `icon-${agent.agentId}`]">{{ agentIcon(agent.agentId) }}</span>
            <div class="card-info">
              <span class="card-name">{{ agent.agentName }}</span>
              <span :class="['card-status', `status-${agent.status}`]">
                <span class="status-dot"></span>
                {{ statusLabel(agent.status) }}
              </span>
            </div>
            <span v-if="agent.status === 'working' && agent.startTime" class="card-timer">
              {{ elapsed(agent.startTime) }}
            </span>
          </div>

          <!-- Current task -->
          <div v-if="agent.currentTask" class="card-task">
            {{ truncate(agent.currentTask, 120) }}
          </div>

          <!-- Expandable logs -->
          <div v-if="agent.logs && agent.logs.length > 0" class="card-logs-section">
            <div class="logs-toggle" @click="toggleLogs(agent.agentId)">
              <span>{{ expandedLogs[agent.agentId] ? '收起' : '展开' }}日志</span>
              <span class="logs-count">{{ agent.logs.length }}</span>
            </div>
            <div v-if="expandedLogs[agent.agentId]" class="logs-body" :ref="(el) => { if (el) logRefs[agent.agentId] = el }">
              <div v-for="(log, idx) in agent.logs" :key="idx" :class="['log-line', `log-${log.type}`]">
                <span class="log-prefix">{{ logPrefix(log) }}</span>
                <span class="log-text">{{ truncate(log.text, 100) }}</span>
                <span v-if="log.durationMs" class="log-dur">{{ log.durationMs }}ms</span>
              </div>
            </div>
          </div>

          <!-- Recent history -->
          <div v-if="agent.history && agent.history.length > 0" class="card-history">
            <div class="history-title">最近任务</div>
            <div v-for="(h, idx) in agent.history.slice(-3)" :key="idx" class="history-item">
              <span :class="['history-status', `h-${h.status}`]">
                {{ h.status === 'completed' ? '✓' : '✗' }}
              </span>
              <span class="history-task">{{ truncate(h.task, 50) }}</span>
              <span class="history-dur">{{ formatDuration(h.durationMs) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed, watch, reactive, onBeforeUnmount } from 'vue'
import { API_BASE } from '../constants/index.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  token: { type: String, default: '' },
  sessionKey: { type: String, default: '' },
})

const emit = defineEmits(['update:show'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const agentStates = ref({})
const expandedLogs = reactive({})
const logRefs = reactive({})

// Timer refresh
let timerInterval = null
const timerTick = ref(Date.now())

const totalAgents = computed(() => Object.keys(agentStates.value).length)
const workingCount = computed(() => Object.values(agentStates.value).filter(s => s.status === 'working').length)

const sortedAgents = computed(() => {
  return Object.entries(agentStates.value)
    .map(([agentId, state]) => ({
      agentId,
      ...state,
    }))
    .sort((a, b) => {
      const order = { working: 0, error: 1, completed: 2, idle: 3 }
      return (order[a.status] ?? 4) - (order[b.status] ?? 4)
    })
})

function agentIcon(id) {
  const icons = { user: '👤' }
  return icons[id] || '🤖'
}

function statusLabel(status) {
  const labels = { idle: '空闲', working: '运行中', error: '错误', completed: '已完成' }
  return labels[status] || status
}

function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '…' : text
}

function elapsed(startTime) {
  if (!startTime) return ''
  const diff = timerTick.value - startTime
  const sec = Math.floor(diff / 1000)
  const min = Math.floor(sec / 60)
  const s = sec % 60
  return min > 0 ? `${min}m${s}s` : `${s}s`
}

function formatDuration(ms) {
  if (!ms) return ''
  const sec = Math.floor(ms / 1000)
  const min = Math.floor(sec / 60)
  const s = sec % 60
  return min > 0 ? `${min}m${s}s` : `${s}s`
}

function logPrefix(log) {
  const prefixes = { tool_start: '⚡', tool_end: '✓', step_start: '▶', step_finish: '■', reasoning: '💭' }
  return prefixes[log.type] || '•'
}

function toggleLogs(agentId) {
  expandedLogs[agentId] = !expandedLogs[agentId]
}

function handleWorkEvent(event) {
  const kind = event.kind
  const payload = event.payload || {}

  // Handle snapshot: bulk-set all agents
  if (kind === 'agent.work.snapshot') {
    const agents = payload.agents || {}
    for (const [id, agentData] of Object.entries(agents)) {
      agentStates.value[id] = {
        agentName: agentData.agentName || id,
        status: agentData.status || 'idle',
        currentTask: agentData.currentTask || '',
        logs: agentData.logs || [],
        history: agentData.history || [],
        startTime: agentData.startTime || null,
      }
    }
    return
  }

  const agentId = payload.agentId || 'user'

  if (!agentStates.value[agentId]) {
    agentStates.value[agentId] = {
      agentName: payload.agentName || agentId,
      status: 'idle',
      currentTask: '',
      logs: [],
      history: [],
      startTime: null,
    }
  }

  const state = agentStates.value[agentId]

  if (kind === 'agent.work.start') {
    state.status = 'working'
    state.currentTask = payload.task || ''
    state.startTime = Date.now()
    state.logs = []
  } else if (kind === 'agent.work.done') {
    state.status = 'completed'
    state.currentTask = ''
    state.startTime = null
    if (payload.task) {
      state.history.push({
        task: payload.task,
        status: 'completed',
        durationMs: payload.durationMs,
      })
      if (state.history.length > 5) state.history.shift()
    }
  } else if (kind === 'agent.work.error') {
    state.status = 'error'
    state.currentTask = ''
    state.startTime = null
    if (payload.task) {
      state.history.push({
        task: payload.task,
        status: 'error',
        durationMs: payload.durationMs,
      })
    }
  } else if (kind === 'agent.work.log') {
    state.logs.push({
      type: payload.type || 'info',
      text: payload.text || '',
      durationMs: payload.durationMs,
    })
    if (state.logs.length > 50) state.logs.shift()
    // Auto-scroll
    nextTick(() => {
      const el = logRefs[agentId]
      if (el) el.scrollTop = el.scrollHeight
    })
  }
}

defineExpose({ handleWorkEvent })

// Start timer
watch(() => props.show, (v) => {
  if (v) {
    timerInterval = setInterval(() => { timerTick.value = Date.now() }, 1000)
  } else {
    clearInterval(timerInterval)
    timerInterval = null
  }
}, { immediate: true })

onBeforeUnmount(() => {
  clearInterval(timerInterval)
})
</script>

<style scoped>
.agent-dashboard-drawer.van-popup {
  background: var(--color-bg-secondary);
}

.dashboard-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.dashboard-header {
  padding: 20px 18px 14px;
  border-bottom: 1px solid var(--color-border);
}

.dashboard-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px;
}

.dashboard-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.summary-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-idle { background: var(--color-text-muted); }
.dot-working { background: var(--color-success); animation: pulse-dot 1.5s ease-in-out infinite; }
.dot-error { background: var(--color-danger); }
.dot-completed { background: var(--color-primary); }

.summary-text {
  margin-left: 4px;
}

.dashboard-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-card {
  background: var(--color-bg-glass);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 12px;
  transition: all 0.2s ease;
}

.agent-card:hover {
  border-color: var(--color-border-glow);
}

.agent-card.card-working {
  border-color: var(--color-success);
  box-shadow: 0 0 15px rgba(0, 229, 160, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.icon-main { background: rgba(99, 102, 241, 0.08); }
.icon-dev { background: rgba(0, 229, 160, 0.1); }
.icon-design { background: rgba(139, 92, 246, 0.08); }
.icon-user { background: rgba(139, 139, 158, 0.1); }

.card-info {
  flex: 1;
  min-width: 0;
}

.card-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.card-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  margin-top: 2px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.status-idle { color: var(--color-text-muted); }
.status-idle .status-dot { background: var(--color-text-muted); }

.status-working { color: var(--color-success); }
.status-working .status-dot { background: var(--color-success); animation: pulse-dot 1.5s ease-in-out infinite; }

.status-error { color: var(--color-danger); }
.status-error .status-dot { background: var(--color-danger); }

.status-completed { color: var(--color-primary); }
.status-completed .status-dot { background: var(--color-primary); }

.card-timer {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-success);
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  flex-shrink: 0;
}

/* ── Current Task ── */
.card-task {
  margin-top: 8px;
  padding: 6px 10px;
  background: rgba(0, 229, 160, 0.06);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  word-break: break-all;
}

/* ── Logs ── */
.card-logs-section {
  margin-top: 8px;
}

.logs-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
  color: var(--color-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.logs-toggle:active { opacity: 0.7; }

.logs-count {
  font-size: 10px;
  background: rgba(99, 102, 241, 0.08);
  color: var(--color-primary);
  padding: 1px 6px;
  border-radius: 10px;
}

.logs-body {
  max-height: 200px;
  overflow-y: auto;
  margin-top: 4px;
  padding: 6px 0;
  background: var(--color-bg-tertiary);
  border-radius: 8px;
  font-family: 'SF Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 11px;
  line-height: 1.5;
  -webkit-overflow-scrolling: touch;
}

.log-line {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 1px 8px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.log-prefix {
  flex-shrink: 0;
  width: 14px;
  text-align: center;
  font-weight: 600;
}

.log-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #8b949e;
}

.log-dur {
  color: #6b7280;
  font-size: 10px;
  flex-shrink: 0;
}

.log-tool_start .log-prefix { color: #58a6ff; }
.log-tool_start .log-text { color: #79c0ff; }
.log-tool_end .log-prefix { color: #3fb950; }
.log-tool_end .log-text { color: #8b949e; }
.log-step_start .log-prefix { color: #58a6ff; }
.log-step_finish .log-prefix { color: #3fb950; }
.log-reasoning .log-prefix { color: #d2a8ff; }
.log-reasoning .log-text { color: #bc8cff; }

/* ── History ── */
.card-history {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.history-title {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  font-size: 12px;
}

.history-status {
  flex-shrink: 0;
  font-size: 11px;
}

.history-status.h-completed { color: var(--color-success); }
.history-status.h-error { color: var(--color-danger); }

.history-task {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.history-dur {
  font-size: 10px;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
