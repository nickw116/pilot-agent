import { Agent } from "@mariozechner/pi-agent-core";
import {
  streamSimpleOpenAICompletions,
  registerApiProvider,
  type Model,
} from "@mariozechner/pi-ai";
import { tools } from "./tools.js";
import { publish } from "./sse.js";
import { bridgeAndPublish } from "./event-bridge.js";

const SESSION_KEY = "pilot:h5-mvp";

// Register xiaomi's OpenAI-compatible endpoint (not the anthropic one)
registerApiProvider({
  api: "openai-completions",
  stream: streamSimpleOpenAICompletions as any,
  streamSimple: streamSimpleOpenAICompletions as any,
}, "xiaomi-openai");

const mimoModel: Model = {
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

let agent: Agent | null = null;

function getAgent(): Agent {
  if (agent) return agent;

  agent = new Agent({
    initialState: {
      systemPrompt:
        "你是 Pilot Code，一个智能编程助手。你可以读写文件、执行命令来帮助用户。请用中文回答。修改文件前先读取，使用 edit 做精确修改。",
      model: mimoModel,
      tools,
    },
    streamFn: streamSimpleOpenAICompletions as any,
    getApiKey: (provider: string) => {
      if (provider === "xiaomi") return process.env.XIAOMI_API_KEY;
      return undefined;
    },
    convertToLlm: (messages) => messages as any[],
    toolExecution: "sequential",
  });

  // Subscribe to all agent events and bridge to SSE
  agent.subscribe((event) => {
    const runId = currentRunId;
    if (runId) bridgeAndPublish(event, runId, SESSION_KEY);
  });

  return agent;
}

let currentRunId: string | null = null;

export async function runPrompt(message: string): Promise<string> {
  const a = getAgent();
  const runId = crypto.randomUUID();
  currentRunId = runId;

  try {
    await a.prompt(message);
  } catch (err: any) {
    publish(SESSION_KEY, {
      eventId: "",
      kind: "run.error",
      runId,
      sessionKey: SESSION_KEY,
      payload: { error: err.message || "Agent error" },
    });
  } finally {
    currentRunId = null;
  }

  return runId;
}

export function abort(): void {
  if (agent) {
    agent.abort();
    if (currentRunId) {
      publish(SESSION_KEY, {
        eventId: "",
        kind: "run.end",
        runId: currentRunId,
        sessionKey: SESSION_KEY,
      });
    }
    currentRunId = null;
  }
}
