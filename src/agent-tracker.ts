import { publish } from "./sse.js";
import { agentConfigs } from "./agent.js";

// --- Types ---

export type AgentWorkStatus = "idle" | "working" | "completed" | "error";

export interface AgentWorkLog {
  ts: number;
  type: string;
  tool?: string;
  text: string;
  durationMs?: number;
}

export interface TaskHistoryEntry {
  task: string;
  status: AgentWorkStatus;
  durationMs: number;
  completedAt: number;
}

export interface AgentWorkState {
  agentId: string;
  agentName: string;
  status: AgentWorkStatus;
  currentTask: string;
  startTime: number | null;
  logs: AgentWorkLog[];
  history: TaskHistoryEntry[];
}

// --- Storage ---

const MAX_LOGS = 500;
const MAX_HISTORY = 10;

// sessionKey → agentId → AgentWorkState
const trackers = new Map<string, Map<string, AgentWorkState>>();

function getOrCreateSessionTracker(sessionKey: string): Map<string, AgentWorkState> {
  let sessionTracker = trackers.get(sessionKey);
  if (!sessionTracker) {
    sessionTracker = new Map();
    trackers.set(sessionKey, sessionTracker);
    // Initialize all known agents as idle
    for (const [id, ac] of agentConfigs) {
      sessionTracker.set(id, {
        agentId: id,
        agentName: ac.name,
        status: "idle",
        currentTask: "",
        startTime: null,
        logs: [],
        history: [],
      });
    }
  }
  return sessionTracker;
}

function getAgentState(sessionKey: string, agentId: string): AgentWorkState | null {
  return trackers.get(sessionKey)?.get(agentId) || null;
}

function ensureAgentState(sessionKey: string, agentId: string): AgentWorkState {
  const sessionTracker = getOrCreateSessionTracker(sessionKey);
  let state = sessionTracker.get(agentId);
  if (!state) {
    const ac = agentConfigs.get(agentId);
    state = {
      agentId,
      agentName: ac?.name || agentId,
      status: "idle",
      currentTask: "",
      startTime: null,
      logs: [],
      history: [],
    };
    sessionTracker.set(agentId, state);
  }
  return state;
}

// --- Public API ---

export function startAgentWork(sessionKey: string, agentId: string, task: string): void {
  const state = ensureAgentState(sessionKey, agentId);
  state.status = "working";
  state.currentTask = task;
  state.startTime = Date.now();
  state.logs = [];

  publish(sessionKey, {
    eventId: "",
    kind: "agent.work.start",
    payload: {
      agentId,
      agentName: state.agentName,
      task,
      startTime: state.startTime,
    },
  });
}

export function logAgentWork(sessionKey: string, agentId: string, logEntry: Omit<AgentWorkLog, "ts">): void {
  const state = getAgentState(sessionKey, agentId);
  if (!state) return;

  const entry: AgentWorkLog = { ts: Date.now(), ...logEntry };
  state.logs.push(entry);
  if (state.logs.length > MAX_LOGS) {
    state.logs = state.logs.slice(-MAX_LOGS);
  }

  publish(sessionKey, {
    eventId: "",
    kind: "agent.work.log",
    payload: {
      agentId,
      log: entry,
    },
  });
}

export function endAgentWork(sessionKey: string, agentId: string, finalStatus: "completed" | "error", errorMsg?: string): void {
  const state = getAgentState(sessionKey, agentId);
  if (!state) return;

  const durationMs = state.startTime ? Date.now() - state.startTime : 0;

  // Add to history
  state.history.push({
    task: state.currentTask,
    status: finalStatus,
    durationMs,
    completedAt: Date.now(),
  });
  if (state.history.length > MAX_HISTORY) {
    state.history = state.history.slice(-MAX_HISTORY);
  }

  state.status = finalStatus === "error" ? "error" : "idle";
  state.currentTask = "";
  state.startTime = null;

  publish(sessionKey, {
    eventId: "",
    kind: "agent.work.end",
    payload: {
      agentId,
      status: state.status,
      durationMs,
      errorMsg: errorMsg || null,
    },
  });
}

export function getAgentWorkSnapshot(sessionKey: string): Record<string, AgentWorkState> {
  const sessionTracker = trackers.get(sessionKey);
  if (!sessionTracker) {
    // Return all agents as idle
    const result: Record<string, AgentWorkState> = {};
    for (const [id, ac] of agentConfigs) {
      result[id] = {
        agentId: id,
        agentName: ac.name,
        status: "idle",
        currentTask: "",
        startTime: null,
        logs: [],
        history: [],
      };
    }
    return result;
  }

  const result: Record<string, AgentWorkState> = {};
  for (const [id, state] of sessionTracker) {
    result[id] = { ...state, logs: state.logs.slice(-50), history: state.history.slice(-5) };
  }
  return result;
}

export function cleanupSessionTracker(sessionKey: string): void {
  trackers.delete(sessionKey);
}
