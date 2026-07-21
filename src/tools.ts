import { exec } from "child_process";
import fs from "fs";
import path from "path";
import { Type, type Static, type TSchema } from "@mariozechner/pi-ai";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";
import { loadSkillContent } from "./skills/index.js";
import {
  appendToLongTermMemory,
  appendDailyNote,
  searchMemory as searchMemoryFiles,
} from "./memory.js";
import { ensureBootstrapFiles } from "./bootstrap.js";

const DEFAULT_WORKSPACE = path.resolve(
  process.env.WORKSPACE_DIR ||
    path.join(process.cwd(), "data", "workspace")
);

const DANGEROUS_COMMANDS = [
  /\brm\s+(-\w*r\w*f|--force)\s+\/(\s|$)/i,
  /\brm\s+(-\w*r\w*f|--force)\s+~(\s|$)/i,
  /\brm\s+(-\w*r\w*f|--force)\s+\*(\s|$)/,
  /\bmkfs\b/i,
  /\bdd\s+(if|of)=\/dev\//i,
  /:\(\)\{.*:\|.*&.*\}/,
  /\bchmod\s+(777|-R\s+777)\s+\//i,
  /\bchown\s+-R\s+root\s+\//i,
  /\b(wget|curl)\b.*\|\s*(ba)?sh/i,
  /\bshutdown\b/i,
  /\breboot\b/i,
  /\binit\s+[06]\b/,
  /\bsystemctl\s+(stop|disable|restart|reload)\s+/i,
  /\bservice\s+\w+\s+(stop|restart|reload)\s*/i,
  />\/dev\/sd/i,
];

function checkBashSafety(command: string): string | null {
  for (const pattern of DANGEROUS_COMMANDS) {
    if (pattern.test(command)) {
      return `该命令被安全策略拦截: ${pattern.source}`;
    }
  }
  return null;
}

function ensureWorkspace(workspaceRoot: string): void {
  ensureBootstrapFiles(workspaceRoot);
  ensureClaudeSettings(workspaceRoot);
}

function ensureClaudeSettings(workspaceRoot: string): void {
  const claudeDir = path.join(workspaceRoot, ".claude");
  const settingsFile = path.join(claudeDir, "settings.json");
  if (fs.existsSync(settingsFile)) return;
  fs.mkdirSync(claudeDir, { recursive: true });
  const settings = {
    hooks: {
      PreToolUse: [
        {
          matcher: "Bash",
          hooks: [
            {
              type: "command",
              command: "bash /home/ubuntu/pilot-agent/tools/check-self-restart.sh",
            },
          ],
        },
      ],
    },
  };
  fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2), "utf-8");
}

function makeResolve(workspaceRoot: string) {
  return (p: string): string => {
    const abs = path.resolve(workspaceRoot, p);
    if (!abs.startsWith(workspaceRoot)) throw new Error(`Path escapes workspace: ${p}`);
    return abs;
  };
}

export function createUserTools(workspaceRoot: string, allowedTools?: string[], currentAgentId?: string): { tools: AgentTool<TSchema, string | Record<string, unknown>>[]; dispose: () => Promise<void> } {
  ensureWorkspace(workspaceRoot);
  const resolve = makeResolve(workspaceRoot);

  const ReadParams = Type.Object({
    paths: Type.Array(Type.String({ description: "File or directory paths" })),
    startLine: Type.Optional(Type.Number({ description: "Start line (1-indexed)" })),
    endLine: Type.Optional(Type.Number({ description: "End line" })),
  });

  function doRead(params: Static<typeof ReadParams>): AgentToolResult<string> {
    const results: string[] = [];
    for (const raw of params.paths) {
      const p = resolve(raw);
      if (!fs.existsSync(p)) {
        results.push(`${raw}: not found`);
        continue;
      }
      const stat = fs.statSync(p);
      if (stat.isDirectory()) {
        const entries = fs.readdirSync(p);
        results.push(`${raw}/\n${entries.map((e) => `  ${e}`).join("\n")}`);
      } else {
        let content = fs.readFileSync(p, "utf-8");
        const lines = content.split("\n");
        const start = (params.startLine ?? 1) - 1;
        const end = params.endLine ?? lines.length;
        const sliced = lines.slice(start, end);
        results.push(
          sliced.map((line, i) => `${String(start + i + 1).padStart(4)}\t${line}`).join("\n")
        );
      }
    }
    const text = results.join("\n\n");
    return { content: [{ type: "text", text }], details: text };
  }

  const WriteParams = Type.Object({
    path: Type.String({ description: "File path" }),
    content: Type.String({ description: "File content" }),
  });

  function doWrite(params: Static<typeof WriteParams>): AgentToolResult<string> {
    const p = resolve(params.path);
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, params.content, "utf-8");
    const msg = `Wrote ${Buffer.byteLength(params.content)} bytes to ${p}`;
    return { content: [{ type: "text", text: msg }], details: msg };
  }

  const EditParams = Type.Object({
    path: Type.String({ description: "File path" }),
    edits: Type.Array(
      Type.Object({
        old_string: Type.String({ description: "Text to find" }),
        new_string: Type.String({ description: "Replacement text" }),
      })
    ),
  });

  function doEdit(params: Static<typeof EditParams>): AgentToolResult<string> {
    const p = resolve(params.path);
    let content = fs.readFileSync(p, "utf-8");
    const diffs: string[] = [];
    for (const edit of params.edits) {
      const idx = content.indexOf(edit.old_string);
      if (idx === -1) {
        return {
          content: [{ type: "text", text: `edit failed: string not found in ${params.path}` }],
          details: "string not found",
        };
      }
      const after = content.replace(edit.old_string, edit.new_string);
      if (after === content) {
        return {
          content: [{ type: "text", text: `edit failed: replacement is identical` }],
          details: "no change",
        };
      }
      content = after;
      diffs.push(
        `--- ${edit.old_string.slice(0, 60)}\n+++ ${edit.new_string.slice(0, 60)}`
      );
    }
    fs.writeFileSync(p, content, "utf-8");
    const msg = `Edited ${params.path} (${diffs.length} change${diffs.length > 1 ? "s" : ""})\n${diffs.join("\n")}`;
    return { content: [{ type: "text", text: msg }], details: msg };
  }

  const BashParams = Type.Object({
    command: Type.String({ description: "Shell command" }),
    timeout: Type.Optional(Type.Number({ description: "Timeout ms", default: 30000 })),
  });

  function doBash(
    params: Static<typeof BashParams>,
    signal?: AbortSignal
  ): Promise<AgentToolResult<string>> {
    return new Promise((resolve_) => {
      const blockReason = checkBashSafety(params.command);
      if (blockReason) {
        return resolve_({
          content: [{ type: "text", text: `⛔ ${blockReason}` }],
          details: "blocked",
        });
      }
      const timeout = params.timeout ?? 30000;
      exec(
        params.command,
        { cwd: workspaceRoot, timeout, maxBuffer: 1024 * 1024 },
        (error, stdout, stderr) => {
          let text = "";
          if (stdout) text += stdout;
          if (stderr) text += (text ? "\n" : "") + stderr;
          if (error && !text) text = `Exit code ${error.code ?? "null"}: ${error.message}`;
          resolve_({
            content: [{ type: "text", text }],
            details: text,
          });
        }
      );
      signal?.addEventListener("abort", () => {
        resolve_({
          content: [{ type: "text", text: "Command aborted" }],
          details: "aborted",
        });
      });
    });
  }

  const SkillParams = Type.Object({
    id: Type.String({ description: "Skill ID to load (e.g. 'github', 'stock-chart-analysis', 'frontend-spec')" }),
  });

  function doSkill(params: Static<typeof SkillParams>): AgentToolResult<string> {
    const content = loadSkillContent(params.id, currentAgentId);
    return { content: [{ type: "text", text: content }], details: content };
  }

  const tools: AgentTool<TSchema, string | Record<string, unknown>>[] = [
    {
      name: "read",
      description: "Read file contents or list directory contents",
      parameters: ReadParams,
      label: "Read",
      execute: (_id, params) => Promise.resolve(doRead(params as Static<typeof ReadParams>)),
    },
    {
      name: "write",
      description: "Create or overwrite a file",
      parameters: WriteParams,
      label: "Write",
      execute: (_id, params) => Promise.resolve(doWrite(params as Static<typeof WriteParams>)),
    },
    {
      name: "edit",
      description: "Replace text in a file",
      parameters: EditParams,
      label: "Edit",
      execute: (_id, params) => Promise.resolve(doEdit(params as Static<typeof EditParams>)),
    },
    {
      name: "bash",
      description: "Execute a bash command",
      parameters: BashParams,
      label: "Bash",
      execute: (_id, params, signal) => doBash(params as Static<typeof BashParams>, signal),
    },
    {
      name: "skill",
      description: "Load a skill's full knowledge and reference docs. Use this to get detailed instructions before executing skill-related tasks. Available skill IDs are listed in your system prompt under '可用 Skills'.",
      parameters: SkillParams,
      label: "Skill",
      execute: (_id, params) => Promise.resolve(doSkill(params as Static<typeof SkillParams>)),
    },
  ];

  // --- Memory tools (always available, not filtered) ---

  const MemorySaveParams = Type.Object({
    content: Type.String({ description: "Content to save to memory" }),
    type: Type.Union([
      Type.Literal("long_term"),
      Type.Literal("daily"),
    ], { description: "'long_term' = durable facts/preferences (MEMORY.md), 'daily' = today's note" }),
  });

  function doMemorySave(params: Static<typeof MemorySaveParams>): AgentToolResult<string> {
    if (params.type === "long_term") {
      appendToLongTermMemory(workspaceRoot, params.content);
      return { content: [{ type: "text", text: "已保存到长期记忆 (MEMORY.md)" }], details: "saved to MEMORY.md" };
    } else {
      appendDailyNote(workspaceRoot, params.content);
      return { content: [{ type: "text", text: "已保存到今日笔记" }], details: "saved to daily note" };
    }
  }

  const MemorySearchParams = Type.Object({
    query: Type.String({ description: "Search query to find relevant memories" }),
  });

  function doMemorySearch(params: Static<typeof MemorySearchParams>): AgentToolResult<string> {
    const results = searchMemoryFiles(workspaceRoot, params.query);
    if (results.length === 0) {
      return { content: [{ type: "text", text: "未找到相关记忆" }], details: "no results" };
    }
    const text = results.join("\n---\n");
    return { content: [{ type: "text", text }], details: text };
  }

  const memoryTools: AgentTool<TSchema, string | Record<string, unknown>>[] = [
    {
      name: "memory_save",
      description: "Save important information to persistent memory. Use 'long_term' for durable facts, user preferences, and standing decisions. Use 'daily' for observations and session summaries.",
      parameters: MemorySaveParams,
      label: "Memory Save",
      execute: (_id, params) => Promise.resolve(doMemorySave(params as Static<typeof MemorySaveParams>)),
    },
    {
      name: "memory_search",
      description: "Search across all memory files (MEMORY.md and daily notes) for relevant information. Use this before answering questions to check if relevant context was previously saved.",
      parameters: MemorySearchParams,
      label: "Memory Search",
      execute: (_id, params) => Promise.resolve(doMemorySearch(params as Static<typeof MemorySearchParams>)),
    },
  ];

  const filtered = allowedTools
    ? tools.filter((t) => allowedTools.includes(t.name))
    : tools;

  // Memory tools are always available regardless of agent tool restrictions
  filtered.push(...memoryTools);

  async function dispose(): Promise<void> {
    // Nothing to clean up in the single-agent, non-ACP architecture.
  }

  return { tools: filtered, dispose };
}

export function getAgentDir(agentId?: string): string {
  const resolvedAgent = agentId || "user";
  return path.join(DEFAULT_WORKSPACE, resolvedAgent);
}

// Migrate old flat structure (user-<id>/[agentId]/) to new agent-first structure (<agentId>/user-<id>/)
const migratedKeys = new Set<string>();
function migrateOldWorkspace(userId: number, agentId: string): void {
  const key = `${agentId}:${userId}`;
  if (migratedKeys.has(key)) return;
  migratedKeys.add(key);

  const newDir = path.join(DEFAULT_WORKSPACE, agentId, `user-${userId}`);
  if (fs.existsSync(newDir)) return; // already migrated

  // Old paths
  const oldDirs = agentId === "main"
    ? [path.join(DEFAULT_WORKSPACE, `user-${userId}`)]
    : [path.join(DEFAULT_WORKSPACE, `user-${userId}`, agentId)];

  const SKIP_ENTRIES = new Set(["AGENTS.md", "SOUL.md", "IDENTITY.md", "TOOLS.md", "USER.md", "dev", "user"]);

  for (const oldDir of oldDirs) {
    if (!fs.existsSync(oldDir)) continue;
    const hasContent = fs.readdirSync(oldDir).some(f => !SKIP_ENTRIES.has(f));
    if (!hasContent) continue;

    fs.mkdirSync(path.dirname(newDir), { recursive: true });
    try {
      fs.cpSync(oldDir, newDir, { recursive: true, filter: (src) => {
        const base = path.basename(src);
        if (src === oldDir) return true;
        return !SKIP_ENTRIES.has(base);
      }});
      console.log(`[workspace] migrated ${oldDir} → ${newDir}`);
    } catch (err) {
      console.error(`[workspace] migration failed for ${oldDir}:`, err);
    }
    return;
  }
}

export function getUserWorkspaceDir(userId: number, agentId?: string): string {
  const resolvedAgent = agentId || "user";
  migrateOldWorkspace(userId, resolvedAgent);
  return path.join(DEFAULT_WORKSPACE, resolvedAgent, `user-${userId}`);
}
