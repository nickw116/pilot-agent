import fs from "fs";
import path from "path";

// Agent bootstrap files live in the source tree:
//   src/agents/<agentId>/AGENTS.md, SOUL.md, IDENTITY.md, TOOLS.md
//
// At runtime, they are copied to the workspace:
//   data/workspace/<agentId>/AGENTS.md, ...
//
// USER.md is per-user, generated at runtime only:
//   data/workspace/<agentId>/user-<id>/USER.md

const AGENT_BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "IDENTITY.md", "TOOLS.md"] as const;

const USER_MD_DEFAULT = `# USER.md

## 用户偏好
（此文件用于记录用户的偏好和背景信息，由 memory_save 工具自动更新或手动编辑）
`;

// Resolve the source directory for agent bootstrap files
const AGENTS_SOURCE_DIR = path.join(process.cwd(), "src", "agents");

function getSourceDir(agentId: string): string {
  return path.join(AGENTS_SOURCE_DIR, agentId);
}

// --- Agent-level (shared, source-controlled → runtime copy) ---

export function ensureAgentBootstrapFiles(agentDir: string, agentId: string): void {
  fs.mkdirSync(agentDir, { recursive: true });
  const sourceDir = getSourceDir(agentId);

  for (const file of AGENT_BOOTSTRAP_FILES) {
    // Source-controlled shared files: always overwrite the runtime copy so edits
    // to src/agents/<id>/ propagate. Only skip when no source file exists.
    const sourcePath = path.join(sourceDir, file);
    if (!fs.existsSync(sourcePath)) continue;
    const targetPath = path.join(agentDir, file);
    fs.copyFileSync(sourcePath, targetPath);
  }
}

export function loadAgentBootstrap(agentDir: string, agentId?: string): string {
  if (agentId) ensureAgentBootstrapFiles(agentDir, agentId);
  const parts: string[] = [];
  for (const file of AGENT_BOOTSTRAP_FILES) {
    const filePath = path.join(agentDir, file);
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, "utf-8").trim();
      if (content) parts.push(content);
    }
  }
  return parts.join("\n\n");
}

// --- User-level (per-user, runtime only) ---

export function ensureUserBootstrapFiles(userDir: string): void {
  fs.mkdirSync(userDir, { recursive: true });
  const userMd = path.join(userDir, "USER.md");
  if (!fs.existsSync(userMd)) {
    fs.writeFileSync(userMd, USER_MD_DEFAULT, "utf-8");
  }
}

export function loadUserBootstrap(userDir: string): string {
  const filePath = path.join(userDir, "USER.md");
  if (!fs.existsSync(filePath)) return "";
  return fs.readFileSync(filePath, "utf-8").trim();
}

// Backward-compatible alias
export function ensureBootstrapFiles(dir: string): void {
  // Used by tools.ts ensureWorkspace — agentId unknown here, use "user" as default
  ensureAgentBootstrapFiles(dir, "user");
}
