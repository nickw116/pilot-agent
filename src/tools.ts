import { exec } from "child_process";
import fs from "fs";
import path from "path";
import { Type, type Static, type TSchema } from "@mariozechner/pi-ai";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";

const WORKSPACE = path.resolve(
  process.env.WORKSPACE_DIR ||
    path.join(import.meta.dirname, "..", "data", "workspace")
);

function resolve(p: string): string {
  const abs = path.resolve(WORKSPACE, p);
  if (!abs.startsWith(WORKSPACE)) throw new Error(`Path escapes workspace: ${p}`);
  return abs;
}

// --- read ---
const ReadParams = Type.Object({
  paths: Type.Array(Type.String(), { description: "File or directory paths" }),
  startLine: Type.Optional(Type.Number({ description: "Start line (1-indexed)" })),
  endLine: Type.Optional(Type.Number({ description: "End line" })),
});

function doRead(
  params: Static<typeof ReadParams>
): AgentToolResult<string> {
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

// --- write ---
const WriteParams = Type.Object({
  path: Type.String({ description: "File path" }),
  content: Type.String({ description: "File content" }),
});

function doWrite(
  params: Static<typeof WriteParams>
): AgentToolResult<string> {
  const p = resolve(params.path);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, params.content, "utf-8");
  const msg = `Wrote ${Buffer.byteLength(params.content)} bytes to ${params.path}`;
  return { content: [{ type: "text", text: msg }], details: msg };
}

// --- edit ---
const EditParams = Type.Object({
  path: Type.String({ description: "File path" }),
  edits: Type.Array(
    Type.Object({
      old_string: Type.String({ description: "Text to find" }),
      new_string: Type.String({ description: "Replacement text" }),
    })
  ),
});

function doEdit(
  params: Static<typeof EditParams>
): AgentToolResult<string> {
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

// --- bash ---
const BashParams = Type.Object({
  command: Type.String({ description: "Shell command" }),
  timeout: Type.Optional(Type.Number({ description: "Timeout ms", default: 30000 })),
});

function doBash(
  params: Static<typeof BashParams>,
  signal?: AbortSignal
): Promise<AgentToolResult<string>> {
  return new Promise((resolve_) => {
    const timeout = params.timeout ?? 30000;
    exec(
      params.command,
      { cwd: WORKSPACE, timeout, maxBuffer: 1024 * 1024 },
      (error, stdout, stderr) => {
        let text = "";
        if (stdout) text += stdout;
        if (stderr) text += (text ? "\n" : "") + stderr;
        if (error && !text) text = `Exit code ${error.code ?? "null"}: ${error.message}`;
        const isError = !!error;
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

// --- Export all tools ---
export const tools: AgentTool<TSchema, string | Record<string, unknown>>[] = [
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
];
