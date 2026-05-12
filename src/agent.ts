import { Agent } from "@mariozechner/pi-agent-core";
import {
  streamSimpleOpenAICompletions,
  registerApiProvider,
  type Model,
} from "@mariozechner/pi-ai";
import { tools } from "./tools.js";
import { publish } from "./sse.js";
import { bridgeAndPublish } from "./event-bridge.js";
import { loadContext, appendContext, type ContextMessage } from "./session.js";
import { compactIfNeeded } from "./compaction.js";

registerApiProvider({
  api: "openai-completions",
  stream: streamSimpleOpenAICompletions as any,
  streamSimple: streamSimpleOpenAICompletions as any,
}, "xiaomi-openai");

const mimoModel: Model<any> = {
  id: "mimo-v2.5-pro",
  name: "MiMo V2.5 Pro",
  api: "openai-completions",
  provider: "xiaomi",
  baseUrl: "https://token-plan-cn.xiaomimimo.com/v1",
  reasoning: true,
  input: ["text"],
  cost: { input: 0.7, output: 2.1, cacheRead: 0.14, cacheWrite: 0 },
  contextWindow: 1000000,
  maxTokens: 131072,
};

const SYSTEM_PROMPT =
  "你是 Pilot Code，一个智能编程助手。你可以读写文件、执行命令来帮助用户。请用中文回答。修改文件前先读取，使用 edit 做精确修改。";

const agents = new Map<string, Agent>();

function getAgent(sessionKey: string): Agent {
  const existing = agents.get(sessionKey);
  if (existing) return existing;

  const agent = new Agent({
    initialState: {
      systemPrompt: SYSTEM_PROMPT,
      model: mimoModel,
      tools,
    },
    streamFn: streamSimpleOpenAICompletions as any,
    getApiKey: (provider: string) => {
      if (provider === "xiaomi") return process.env.XIAOMI_API_KEY;
      return undefined;
    },
    convertToLlm: (messages) => messages as any[],
    transformContext: compactIfNeeded,
    toolExecution: "sequential",
  });

  agent.subscribe((event) => {
    const runId = currentRunIds.get(sessionKey);
    if (runId) bridgeAndPublish(event, runId, sessionKey);
  });

  agents.set(sessionKey, agent);
  return agent;
}

const currentRunIds = new Map<string, string>();

export async function runPrompt(message: string, sessionKey: string): Promise<string> {
  const agent = getAgent(sessionKey);
  const runId = crypto.randomUUID();
  currentRunIds.set(sessionKey, runId);

  // Load history and append new user message
  const history = loadContext(sessionKey);
  history.push({ role: "user", content: message });

  try {
    // Feed history to agent state
    // Pi Agent's prompt() handles the conversation — we append context after
    await agent.prompt(message);
  } catch (err: any) {
    publish(sessionKey, {
      eventId: "",
      kind: "run.error",
      runId,
      sessionKey,
      payload: { error: err.message || "Agent error" },
    });
  } finally {
    currentRunIds.delete(sessionKey);
  }

  // Persist user + assistant messages
  const lastAssistant = agent.state.messages
    ?.filter((m: any) => m.role === "assistant")
    .pop();
  const toSave: ContextMessage[] = [{ role: "user", content: message }];
  if (lastAssistant) {
    const text = typeof lastAssistant.content === "string"
      ? lastAssistant.content
      : (lastAssistant.content as any[])?.filter((b: any) => b.type === "text").map((b: any) => b.text).join("") || "";
    if (text) toSave.push({ role: "assistant", content: text, model: mimoModel.name });
  }
  appendContext(sessionKey, toSave);

  return runId;
}

export function abort(sessionKey: string): void {
  const agent = agents.get(sessionKey);
  if (!agent) return;
  agent.abort();
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

/** Remove agent from memory (e.g. when session is deleted) */
export function destroyAgent(sessionKey: string): void {
  agents.delete(sessionKey);
  currentRunIds.delete(sessionKey);
}
