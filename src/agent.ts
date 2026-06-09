import { Agent } from "@mariozechner/pi-agent-core";
import {
  streamSimpleOpenAICompletions,
  registerApiProvider,
  type Model,
  type ImageContent,
} from "@mariozechner/pi-ai";
import fs from "fs";
import path from "path";
import { createUserTools, getUserWorkspaceDir, getAgentDir, setAcpSseContext, clearAcpSseContext } from "./tools.js";
import { describeImages, describeVideo, transcribeAudio } from "./media-provider.js";
import { publish } from "./sse.js";
import { bridgeAndPublish } from "./event-bridge.js";
import { loadContext, appendContext, updateSessionTitle, setSessionStatus, type ContextMessage } from "./session.js";
import { compactIfNeeded } from "./compaction.js";
import { appendAuditLog } from "./audit.js";

import { buildSkillSummary } from "./skills/index.js";
import { buildMemoryContext, appendDailyNote } from "./memory.js";
import { loadAgentBootstrap, loadUserBootstrap, ensureAgentBootstrapFiles, ensureUserBootstrapFiles } from "./bootstrap.js";
import { startAgentWork, endAgentWork, cleanupSessionTracker } from "./agent-tracker.js";
import { execSync } from "child_process";

const RESTART_FLAG_FILE = "/tmp/pilot-agent-restart-requested";

function checkDelayedRestart(): void {
  if (!fs.existsSync(RESTART_FLAG_FILE)) return;
  try {
    fs.unlinkSync(RESTART_FLAG_FILE);
    console.log("[agent] delayed restart requested, scheduling in 1s...");
    execSync("nohup bash -c 'sleep 1 && sudo systemctl restart pilot-agent' >/dev/null 2>&1 &", {
      stdio: "ignore",
    });
  } catch (err) {
    console.error("[agent] failed to schedule restart:", err);
  }
}

const STREAM_TIMEOUT_MS = parseInt(process.env.STREAM_TIMEOUT_MS || "120000", 10);

const FALLBACK_MODEL: Model<any> = {
  id: "deepseek-v4-flash",
  name: "DeepSeek V4 Flash",
  api: "openai-completions",
  provider: "deepseek",
  baseUrl: "https://api.deepseek.com/v1",
  reasoning: false,
  input: ["text"],
  cost: { input: 0.1, output: 0.4, cacheRead: 0.01, cacheWrite: 0 },
  contextWindow: 128000,
  maxTokens: 8192,
};

function isTimeoutError(err: any): boolean {
  return err?.name === "TimeoutError" || /timeout/i.test(err?.message || "");
}

function streamWithFallback(model: any, context: any, options: any) {
  const timeoutSignal = AbortSignal.timeout(STREAM_TIMEOUT_MS);
  const combinedSignal = options?.signal
    ? AbortSignal.any([options.signal, timeoutSignal])
    : timeoutSignal;
  return streamSimpleOpenAICompletions(model, context, { ...options, signal: combinedSignal });
}

registerApiProvider({
  api: "openai-completions",
  stream: streamWithFallback as any,
  streamSimple: streamWithFallback as any,
}, "xiaomi-openai");

// --- Load config: models from agents.json, agent configs from src/agents/*/config.json ---

interface AgentConfig {
  id: string;
  name: string;
  model: string;
  tools?: string[];
  subAgents?: string[];
  hidden?: boolean;
}

interface ModelsConfig {
  models: Record<string, {
    provider: string;
    api: string;
    baseUrl: string;
    reasoning: boolean;
    contextWindow: number;
    maxTokens: number;
    modalities?: { input: string[]; output: string[] };
  }>;
}

let modelsConfig: ModelsConfig = { models: {} };
const modelsConfigPath = path.join(process.cwd(), "agents.json");
if (fs.existsSync(modelsConfigPath)) {
  try {
    modelsConfig = JSON.parse(fs.readFileSync(modelsConfigPath, "utf-8"));
    console.log(`[config] loaded model definitions from agents.json`);
  } catch (err) {
    console.error("[config] failed to parse agents.json:", err);
  }
}

export const agentConfigs = new Map<string, AgentConfig>();
const agentsSourceDir = path.join(process.cwd(), "src", "agents");
if (fs.existsSync(agentsSourceDir)) {
  const entries = fs.readdirSync(agentsSourceDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const configFilePath = path.join(agentsSourceDir, entry.name, "config.json");
    if (!fs.existsSync(configFilePath)) continue;
    try {
      const raw = JSON.parse(fs.readFileSync(configFilePath, "utf-8"));
      agentConfigs.set(entry.name, { ...raw, id: entry.name });
    } catch (err) {
      console.error(`[config] failed to load agent config ${configFilePath}:`, err);
    }
  }
  console.log(`[config] discovered ${agentConfigs.size} agent(s) from src/agents/*/config.json`);
}

const mimoModel: Model<any> = {
  id: "mimo-v2.5",
  name: "MiMo V2.5",
  api: "openai-completions",
  provider: "xiaomi",
  baseUrl: "https://token-plan-cn.xiaomimimo.com/v1",
  reasoning: true,
  input: ["text", "image"],
  cost: { input: 0.7, output: 2.1, cacheRead: 0.14, cacheWrite: 0 },
  contextWindow: 1000000,
  maxTokens: 131072,
  compat: {
    thinkingFormat: "deepseek",
    requiresReasoningContentOnAssistantMessages: true,
    supportsDeveloperRole: false,
    supportsStore: false,
    supportsReasoningEffort: false,
  },
};

const mimoProModel: Model<any> = {
  id: "mimo-v2.5-pro",
  name: "MiMo V2.5 Pro",
  api: "openai-completions",
  provider: "xiaomi",
  baseUrl: "https://token-plan-cn.xiaomimimo.com/v1",
  reasoning: true,
  input: ["text"],
  cost: { input: 1.4, output: 4.2, cacheRead: 0.28, cacheWrite: 0 },
  contextWindow: 1000000,
  maxTokens: 131072,
  compat: {
    thinkingFormat: "deepseek",
    requiresReasoningContentOnAssistantMessages: true,
    supportsDeveloperRole: false,
    supportsStore: false,
    supportsReasoningEffort: false,
  },
};

const deepseekModel: Model<any> = {
  id: "deepseek-v4-flash",
  name: "DeepSeek V4 Flash",
  api: "openai-completions",
  provider: "deepseek",
  baseUrl: "https://api.deepseek.com/v1",
  reasoning: false,
  input: ["text"],
  cost: { input: 0.1, output: 0.4, cacheRead: 0.01, cacheWrite: 0 },
  contextWindow: 128000,
  maxTokens: 8192,
};

const minimaxModel: Model<any> = {
  id: "MiniMax-M3",
  name: "MiniMax M3",
  api: "openai-completions",
  provider: "minimax",
  baseUrl: "https://api.minimaxi.com/v1",
  reasoning: true,
  input: ["text"],
  cost: { input: 1.0, output: 4.0, cacheRead: 0.1, cacheWrite: 0 },
  contextWindow: 1000000,
  maxTokens: 131072,
};


// --- SessionLane: per-session serial queue ---

class SessionLane {
  private queue: Array<() => Promise<void>> = [];
  private running = false;

  enqueue<T>(task: () => Promise<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      this.queue.push(async () => {
        try { resolve(await task()); }
        catch (e) { reject(e); }
      });
      this.dequeue();
    });
  }

  private async dequeue() {
    if (this.running || this.queue.length === 0) return;
    this.running = true;
    const task = this.queue.shift()!;
    await task();
    this.running = false;
    this.dequeue();
  }
}

const lanes = new Map<string, SessionLane>();

function getOrCreateLane(sessionKey: string): SessionLane {
  let lane = lanes.get(sessionKey);
  if (!lane) {
    lane = new SessionLane();
    lanes.set(sessionKey, lane);
  }
  return lane;
}

// --- Agent pool ---

interface AgentEntry {
  agent: Agent;
  modelId: string;
  agentId: string;
  userId: number;
  lastActivityAt: number;
  disposeTools: () => Promise<void>;
}

const agents = new Map<string, AgentEntry>();
const currentImages = new Map<string, ImageContent[]>();

function getAgent(sessionKey: string, userId: number, modelId?: string, agentId?: string): Agent {
  const existing = agents.get(sessionKey);
  if (existing) {
    existing.lastActivityAt = Date.now();
    return existing.agent;
  }

  const ac = agentConfigs.get(agentId || "main");
  const resolvedModelId = modelId || ac?.model || "xiaomi/mimo-v2.5-pro";
  const model = resolveModel(resolvedModelId);
  if (!model) throw new Error(`Unknown model: ${resolvedModelId}`);

  const resolvedAgentId = agentId || "main";
  const sk = sessionKey;
  const delegateFn: DelegateFn | undefined = (ac?.subAgents && ac.subAgents.length > 0)
    ? async (agentId2: string, task2: string, context2?: string) => {
        return runSubAgent(agentId2, task2, context2, sk, userId);
      }
    : undefined;

  // Two-level workspace: agent-level (shared) + user-level (per-user)
  const agentDir = getAgentDir(resolvedAgentId);
  const userDir = getUserWorkspaceDir(userId, resolvedAgentId);
  ensureAgentBootstrapFiles(agentDir, resolvedAgentId);
  ensureUserBootstrapFiles(userDir);

  const { tools: userTools, dispose: disposeTools } = createUserTools(
    userDir,
    ac?.tools,
    () => currentImages.get(sk),
    delegateFn,
    ac?.subAgents,
    resolvedAgentId,
  );

  const skillSummary = buildSkillSummary(resolvedAgentId);

  // Agent-level bootstrap (AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md)
  const agentBootstrap = loadAgentBootstrap(agentDir, resolvedAgentId);
  // User-level bootstrap (USER.md)
  const userBootstrap = loadUserBootstrap(userDir);
  const userSection = userBootstrap ? `\n\n${userBootstrap}` : "";

  const memoryContext = buildMemoryContext(userDir);
  const memorySection = memoryContext
    ? `\n\n# 记忆系统\n以下是你的持久化记忆，跨会话保留。回答前先检查记忆中是否有相关信息：\n\n${memoryContext}`
    : "";

  const fullSystemPrompt = agentBootstrap + userSection + skillSummary + memorySection;

  const agent = new Agent({
    initialState: {
      systemPrompt: fullSystemPrompt,
      model,
      tools: userTools,
      thinkingLevel: (resolvedModelId.includes("mimo") || resolvedModelId.includes("minimax")) ? "medium" : "off",
    },
    streamFn: streamWithFallback as any,
    onPayload: (payload) => {
      (payload as any).max_tokens = model.maxTokens;
      return payload;
    },
    getApiKey: (provider: string) => {
      if (provider === "xiaomi") return process.env.XIAOMI_API_KEY;
      if (provider === "deepseek") return process.env.DEEPSEEK_API_KEY;
      if (provider === "minimax") return process.env.MINIMAX_API_KEY;
      return undefined;
    },
    convertToLlm: (messages) => messages as any[],
    transformContext: (messages) => compactIfNeeded(messages, (oldMessages) => {
      try {
        const noteLines: string[] = ["[compaction 前 memory flush]"];
        for (const msg of oldMessages) {
          const role = msg.role === "user" ? "用户" : "助手";
          let text = "";
          if (typeof msg.content === "string") {
            text = msg.content;
          } else if (Array.isArray(msg.content)) {
            text = (msg.content as any[])
              .filter((b: any) => b.type === "text")
              .map((b: any) => b.text)
              .join("");
          }
          if (text) {
            noteLines.push(`${role}: ${text.length > 300 ? text.slice(0, 300) + "..." : text}`);
          }
        }
        appendDailyNote(userDir, noteLines.join("\n"));
        console.log(`[memory] flushed ${oldMessages.length} old messages to daily note before compaction`);
      } catch (err) {
        console.error("[memory] compaction flush failed:", err);
      }
    }),
    toolExecution: "sequential",
  });

  const history = loadContext(sessionKey);
  if (history.length > 0) {
    const recent = history.slice(-10);
    const lines = recent.map((m) => {
      const label = m.role === "user" ? "User" : "Assistant";
      return `${label}: ${m.content || ""}`;
    });
    const contextMsg = {
      role: "user" as const,
      content: `[以下是之前对话的摘要，共${history.length}条，请在此基础上继续对话]\n${lines.join("\n")}`,
      timestamp: Date.now(),
    };
    agent.state.messages = [contextMsg];
    console.log(`[agent] restored ${history.length} messages as context summary for session ${sessionKey}`);
  }

  agent.subscribe((event) => {
    const runId = currentRunIds.get(sessionKey);
    if (runId) bridgeAndPublish(event, runId, sessionKey);
  });

  agents.set(sessionKey, { agent, modelId: resolvedModelId, agentId: agentId || "main", userId, lastActivityAt: Date.now(), disposeTools });
  return agent;
}

function resolveModel(modelId: string): Model<any> | null {
  if (modelId === "xiaomi/mimo-v2.5" || modelId === "mimo-v2.5") {
    const cfg = modelsConfig.models?.["xiaomi/mimo-v2.5-pro"];
    const inputModalities = (cfg?.modalities?.input || ["text"]) as ("text" | "image")[];
    return { ...mimoModel, input: inputModalities };
  }
  if (modelId === "xiaomi/mimo-v2.5-pro" || modelId === "mimo-v2.5-pro") {
    const cfg = modelsConfig.models?.["xiaomi/mimo-v2.5-pro"];
    const inputModalities = (cfg?.modalities?.input || ["text"]) as ("text" | "image")[];
    return { ...mimoProModel, input: inputModalities };
  }
  if (modelId === "deepseek/deepseek-v4-flash" || modelId === "deepseek-v4-flash") {
    return deepseekModel;
  }
  if (modelId === "minimax/m3" || modelId === "MiniMax-M3") {
    return minimaxModel;
  }
  return null;
}

function getApiKeyForProvider(provider: string): string | undefined {
  if (provider === "xiaomi") return process.env.XIAOMI_API_KEY;
  if (provider === "deepseek") return process.env.DEEPSEEK_API_KEY;
  if (provider === "minimax") return process.env.MINIMAX_API_KEY;
  return undefined;
}

const currentRunIds = new Map<string, string>();

async function doRunPromptWithRunId(runId: string, message: string, sessionKey: string, userId: number, agentId?: string, images?: ImageContent[], videos?: Array<{ data: string; mimeType: string }>, audios?: Array<{ data: string; mimeType: string }>): Promise<string> {
  const entry = agents.get(sessionKey);
  const ac = agentConfigs.get(agentId || "main");
  const modelId = entry?.modelId || ac?.model || "xiaomi/mimo-v2.5-pro";
  const agent = getAgent(sessionKey, userId, modelId, agentId);
  currentRunIds.set(sessionKey, runId);
  const startTime = Date.now();
  let errorMsg = "";

  const model = resolveModel(modelId);
  const apiKey = model ? getApiKeyForProvider(model.provider) : undefined;
  if (model && !apiKey) {
    const errMsg = `模型 ${modelId} 的 API Key 未配置`;
    console.error(`[agent] ${errMsg}`);
    publish(sessionKey, {
      eventId: "",
      kind: "run.error",
      runId,
      sessionKey,
      payload: { error: errMsg },
    });
    publish(sessionKey, {
      eventId: "",
      kind: "run.end",
      runId,
      sessionKey,
    });
    currentRunIds.delete(sessionKey);
    return runId;
  }

  console.log(`[agent] doRun: model=${modelId} hasImages=${!!images} imageCount=${images?.length || 0} hasVideos=${!!videos} videoCount=${videos?.length || 0} hasAudios=${!!audios} audioCount=${audios?.length || 0}`);

  let effectiveMessage = message;
  let effectiveImages = images;

  if (images && images.length > 0) {
    currentImages.set(sessionKey, images);
    if (model && !model.input.includes("image")) {
      console.log(`[agent] model ${modelId} does not support images, invoking media understanding layer`);
      const description = await describeImages(images);
      const label = images.length === 1 ? "[图片描述]" : `[${images.length}张图片描述]`;
      effectiveMessage = `${effectiveMessage}\n\n${label}\n${description}`;
      effectiveImages = undefined;
    }
  }

  if (videos && videos.length > 0) {
    console.log(`[agent] processing ${videos.length} video(s) via media provider`);
    const videoDescriptions = await Promise.all(
      videos.map((v, i) => describeVideo(v.data, v.mimeType).then((d) => `[第${i + 1}个视频描述]\n${d}`).catch((e) => `[第${i + 1}个视频描述失败: ${e.message}]`)),
    );
    effectiveMessage = `${effectiveMessage}\n\n${videoDescriptions.join("\n\n")}`;
  }

  if (audios && audios.length > 0) {
    console.log(`[agent] processing ${audios.length} audio(s) via media provider`);
    const audioTranscripts = await Promise.all(
      audios.map((a, i) => {
        const format = a.mimeType.split("/")[1]?.replace(/^x-/, "") || "wav";
        return transcribeAudio(a.data, format)
          .then((t) => `[第${i + 1}段音频转录]\n${t}`)
          .catch((e) => `[第${i + 1}段音频转录失败: ${e.message}]`);
      }),
    );
    effectiveMessage = `${effectiveMessage}\n\n${audioTranscripts.join("\n\n")}`;
  }

  setSessionStatus(sessionKey, "generating", { runId });
  startAgentWork(sessionKey, agentId || "main", message.slice(0, 200));

  setAcpSseContext(sessionKey, runId);

  // Persist user message immediately so it survives page refresh mid-run
  appendContext(sessionKey, [{ role: "user", content: message }], runId);

  // Normal flow: main agent processes the message
  try {
    await agent.prompt(effectiveMessage, effectiveImages);
    setSessionStatus(sessionKey, "completed", { runId });
    endAgentWork(sessionKey, agentId || "main", "completed");
  } catch (err: any) {
    const errMsg = err?.message || "";
    console.error(`[agent] prompt failed: ${errMsg}`, err?.stack || "");
    publish(sessionKey, {
      eventId: "",
      kind: "run.error",
      runId,
      sessionKey,
      payload: { error: errMsg || "Agent error" },
    });
    publish(sessionKey, {
      eventId: "",
      kind: "run.end",
      runId,
      sessionKey,
    });
    errorMsg = errMsg || "Agent error";
    setSessionStatus(sessionKey, "error", { runId, error: errorMsg });
    endAgentWork(sessionKey, agentId || "main", "error", errMsg);
  } finally {
    clearAcpSseContext();
    currentRunIds.delete(sessionKey);
    currentImages.delete(sessionKey);
    const e = agents.get(sessionKey);
    if (e) e.lastActivityAt = Date.now();
  }

  const activeAgent = agents.get(sessionKey)?.agent || agent;

  const lastAssistant = activeAgent.state.messages
    ?.filter((m: any) => m.role === "assistant")
    .pop();
  const toSave: ContextMessage[] = [];
  const resolvedModelName = model?.name || modelId;
  if (lastAssistant) {
    const text = typeof lastAssistant.content === "string"
      ? lastAssistant.content
      : (lastAssistant.content as any[])?.filter((b: any) => b.type === "text").map((b: any) => b.text).join("") || "";
    if (text) toSave.push({ role: "assistant", content: text, model: resolvedModelName });
  }
  if (toSave.length > 0) {
    appendContext(sessionKey, toSave, runId);
  }

  const assistantMsg = toSave.find((m) => m.role === "assistant");
  if (assistantMsg) {
    updateSessionTitle(sessionKey, assistantMsg.content.slice(0, 50).replace(/\n/g, " "));
  }

  appendAuditLog({
    timestamp: Date.now(),
    userId,
    username: "",
    sessionKey,
    model: modelId,
    durationMs: Date.now() - startTime,
    error: errorMsg || undefined,
  });

  checkDelayedRestart();

  return runId;
}

export function runPrompt(message: string, sessionKey: string, userId: number, agentId?: string, images?: ImageContent[], videos?: Array<{ data: string; mimeType: string }>, audios?: Array<{ data: string; mimeType: string }>): Promise<string> {
  const runId = crypto.randomUUID();
  const lane = getOrCreateLane(sessionKey);
  lane.enqueue(() => doRunPromptWithRunId(runId, message, sessionKey, userId, agentId, images, videos, audios)).catch((err) => {
    console.error("[agent] runPrompt unhandled:", err.message);
    publish(sessionKey, {
      eventId: "",
      kind: "run.error",
      runId,
      sessionKey,
      payload: { error: err.message || "Unknown error" },
    });
    publish(sessionKey, {
      eventId: "",
      kind: "run.end",
      runId,
      sessionKey,
    });
  });
  return Promise.resolve(runId);
}

export function steerMessage(sessionKey: string, message: string): boolean {
  const entry = agents.get(sessionKey);
  if (!entry) return false;
  if (!currentRunIds.has(sessionKey)) return false;
  entry.agent.steer({ role: "user", content: message, timestamp: Date.now() });
  console.log(`[steer] appended message to active run: ${message.slice(0, 80)}...`);
  return true;
}

export function abort(sessionKey: string): void {
  const entry = agents.get(sessionKey);
  if (!entry) return;
  entry.agent.abort();
  const runId = currentRunIds.get(sessionKey);
  if (runId) {
    publish(sessionKey, {
      eventId: "",
      kind: "run.end",
      runId,
      sessionKey,
    });
  }
  currentRunIds.delete(sessionKey);
}

export function destroyAgent(sessionKey: string): void {
  const entry = agents.get(sessionKey);
  if (entry) entry.disposeTools().catch(() => {});
  agents.delete(sessionKey);
  currentRunIds.delete(sessionKey);
  lanes.delete(sessionKey);
  cleanupSessionTracker(sessionKey);
}

// --- Sub-agent execution ---

export type DelegateFn = (agentId: string, task: string, context?: string) => Promise<string>;

export async function runSubAgent(
  agentId: string,
  task: string,
  context: string | undefined,
  parentSessionKey: string,
  userId: number,
): Promise<string> {
  const ac = agentConfigs.get(agentId);
  if (!ac) throw new Error(`Unknown sub-agent: ${agentId}`);

  // dev agent: handled by delegate tool via claude_code ACP, not here
  if (agentId === "dev") {
    throw new Error("dev agent should be handled by the delegate tool's claude_code ACP path, not runSubAgent");
  }

  const agentDir = getAgentDir(agentId);
  const userDir = getUserWorkspaceDir(userId, agentId);
  ensureAgentBootstrapFiles(agentDir, agentId);
  ensureUserBootstrapFiles(userDir);
  const modelId = ac.model || "xiaomi/mimo-v2.5-pro";
  const model = resolveModel(modelId);
  if (!model) throw new Error(`Cannot resolve model for sub-agent ${agentId}`);

  const { tools: subTools, dispose: disposeSubTools } = createUserTools(
    userDir,
    ac.tools,
    undefined,
    undefined,
    undefined,
    agentId,
  );

  const skillSummary = buildSkillSummary(agentId);
  const memoryContext = buildMemoryContext(userDir);
  const memorySection = memoryContext
    ? `\n\n# 记忆系统\n以下是你的持久化记忆，跨会话保留。\n\n${memoryContext}`
    : "";

  const subBootstrap = loadAgentBootstrap(agentDir, agentId);

  const fullSystemPrompt = subBootstrap + skillSummary + memorySection;
  const effectiveTask = context ? `${task}\n\n## 附加上下文\n${context}` : task;

  const subAgent = new Agent({
    initialState: {
      systemPrompt: fullSystemPrompt,
      model,
      tools: subTools,
      thinkingLevel: (modelId.includes("mimo") || modelId.includes("minimax")) ? "medium" : "off",
    },
    streamFn: streamWithFallback as any,
    onPayload: (payload) => {
      (payload as any).max_tokens = model.maxTokens;
      return payload;
    },
    getApiKey: (provider: string) => {
      if (provider === "xiaomi") return process.env.XIAOMI_API_KEY;
      if (provider === "deepseek") return process.env.DEEPSEEK_API_KEY;
      if (provider === "minimax") return process.env.MINIMAX_API_KEY;
      return undefined;
    },
    convertToLlm: (messages) => messages as any[],
    toolExecution: "sequential",
  });

  console.log(`[sub-agent] starting ${agentId} for task: ${task.slice(0, 100)}...`);

  const subRunId = `sub-${agentId}-${Date.now()}`;
  setAcpSseContext(parentSessionKey, subRunId);
  startAgentWork(parentSessionKey, agentId, task.slice(0, 200));

  try {
    await subAgent.prompt(effectiveTask);

    const lastAssistant = subAgent.state.messages
      ?.filter((m: any) => m.role === "assistant")
      .pop();

    if (!lastAssistant) return "(子 agent 完成但没有输出)";

    const text = typeof lastAssistant.content === "string"
      ? lastAssistant.content
      : (lastAssistant.content as any[])
          ?.filter((b: any) => b.type === "text")
          .map((b: any) => b.text)
          .join("") || "";

    console.log(`[sub-agent] ${agentId} completed, output length: ${text.length}`);
    endAgentWork(parentSessionKey, agentId, "completed");
    return text || "(子 agent 完成但没有文本输出)";
  } catch (err: any) {
    endAgentWork(parentSessionKey, agentId, "error", err?.message || String(err));
    throw err;
  } finally {
    await disposeSubTools();
    clearAcpSseContext();
  }
}

// --- Model switching ---

const modelRegistry: Record<string, { name: string; alias: string }> = {
  "xiaomi/mimo-v2.5-pro": { name: "MiMo V2.5 Pro", alias: "MiMo" },
  "deepseek/deepseek-v4-flash": { name: "DeepSeek V4 Flash", alias: "DeepSeek" },
  "minimax/m3": { name: "MiniMax M3", alias: "MiniMax" },
};

export function getAgentList(allowedIds?: string[]) {
  const all = Array.from(agentConfigs.values())
    .filter((ac) => !ac.hidden)
    .map((ac) => ({
      id: ac.id,
      name: ac.name,
      tools: ac.tools || [],
    }));
  if (!allowedIds) return all;
  return all.filter((a) => allowedIds.includes(a.id));
}

export function getModelList() {
  return Object.entries(modelRegistry).map(([id, info]) => ({
    id,
    name: info.name,
    alias: info.alias,
  }));
}

export function getCurrentModel(sessionKey: string): string | null {
  const entry = agents.get(sessionKey);
  return entry?.modelId || null;
}

export function switchModel(sessionKey: string, modelId: string, userId: number): boolean {
  if (!modelRegistry[modelId]) return false;

  const model = resolveModel(modelId);
  if (!model) return false;

  const old = agents.get(sessionKey);
  if (old) old.disposeTools().catch(() => {});
  agents.delete(sessionKey);
  getAgent(sessionKey, userId, modelId);
  console.log(`[agent] switched session ${sessionKey} to model ${modelId}`);
  return true;
}

// --- Session lifecycle: evict idle agents ---

const IDLE_TIMEOUT_MS = (parseInt(process.env.SESSION_IDLE_TIMEOUT || "86400", 10)) * 1000;

setInterval(() => {
  const now = Date.now();
  for (const [sk, entry] of agents) {
    if (now - entry.lastActivityAt > IDLE_TIMEOUT_MS) {
      console.log(`[lifecycle] evicting idle agent for session ${sk} (idle ${Math.round((now - entry.lastActivityAt) / 60000)}min)`);
      entry.disposeTools().catch(() => {});
      agents.delete(sk);
      lanes.delete(sk);
    }
  }
}, 5 * 60 * 1000);
