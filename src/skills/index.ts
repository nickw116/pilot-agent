import fs from "fs";
import path from "path";

export interface SkillMeta {
  name: string;
  description: string;
  userInvocable: boolean;
  metadata: Record<string, any>;
}

export interface Skill {
  id: string;
  dir: string;
  meta: SkillMeta;
  body: string;
  references: string[];
}

const SKILLS_DIR = path.join(process.cwd(), "src", "skills");
const AGENTS_DIR = path.join(process.cwd(), "src", "agents");

function parseFrontmatter(raw: string): { meta: SkillMeta; body: string } {
  const meta: SkillMeta = {
    name: "",
    description: "",
    userInvocable: false,
    metadata: {},
  };

  let body = raw;
  const fmMatch = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (fmMatch) {
    const fm = fmMatch[1];
    body = fmMatch[2];

    const nameMatch = fm.match(/^name:\s*(.+)$/m);
    if (nameMatch) meta.name = nameMatch[1].trim();

    const descMatch = fm.match(/^description:\s*(.+)$/m);
    if (descMatch) meta.description = descMatch[1].trim();

    const uiMatch = fm.match(/^user-invocable:\s*(true|false)/m);
    if (uiMatch) meta.userInvocable = uiMatch[1] === "true";

    const mdMatch = fm.match(/^metadata:\s*(\{[\s\S]*?\})\s*$/m);
    if (mdMatch) {
      try {
        meta.metadata = JSON.parse(mdMatch[1]);
      } catch {}
    }
  } else {
    const titleMatch = raw.match(/^#\s+(.+)$/m);
    if (titleMatch) meta.name = titleMatch[1].replace(/^#+\s*/, "").trim();
  }

  return { meta, body: body.trim() };
}

function findReferences(dir: string): string[] {
  const refs: string[] = [];
  const refDir = path.join(dir, "references");
  if (!fs.existsSync(refDir)) return refs;
  for (const f of fs.readdirSync(refDir)) {
    if (f.endsWith(".md")) refs.push(path.join(refDir, f));
  }
  return refs;
}

function loadSkill(dir: string, id: string): Skill | null {
  const mdPath = path.join(dir, "SKILL.md");
  if (!fs.existsSync(mdPath)) return null;
  const raw = fs.readFileSync(mdPath, "utf-8");
  const { meta, body } = parseFrontmatter(raw);
  const references = findReferences(dir);
  return { id, dir, meta, body, references };
}

function loadSkillsFromDir(baseDir: string): Skill[] {
  const skills: Skill[] = [];
  if (!fs.existsSync(baseDir)) return skills;
  const entries = fs.readdirSync(baseDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const skill = loadSkill(path.join(baseDir, entry.name), entry.name);
    if (skill) skills.push(skill);
  }
  return skills;
}

// --- Global skills (cached) ---

let cachedGlobalSkills: Skill[] | null = null;

function loadGlobalSkills(): Skill[] {
  if (cachedGlobalSkills) return cachedGlobalSkills;
  const skills = loadSkillsFromDir(SKILLS_DIR);
  console.log(`[skills] loaded ${skills.length} global skills`);
  cachedGlobalSkills = skills;
  return skills;
}

// --- Agent private skills (not cached) ---

function loadAgentSkills(agentId: string): Skill[] {
  const agentSkillsDir = path.join(AGENTS_DIR, agentId, "skills");
  const skills = loadSkillsFromDir(agentSkillsDir);
  if (skills.length > 0) {
    console.log(`[skills] loaded ${skills.length} private skills for agent '${agentId}'`);
  }
  return skills;
}

function mergeSkills(agentId?: string): Skill[] {
  const global = loadGlobalSkills();
  if (!agentId) return global;
  const private_ = loadAgentSkills(agentId);
  if (private_.length === 0) return global;
  // Merge: private skills override global ones with the same id
  const map = new Map<string, Skill>();
  for (const s of global) map.set(s.id, s);
  for (const s of private_) map.set(s.id, s);
  return Array.from(map.values());
}

// --- Public API ---

export function loadAllSkills(): Skill[] {
  return loadGlobalSkills();
}

export function getSkillById(id: string, agentId?: string): Skill | null {
  const skills = mergeSkills(agentId);
  return skills.find((s) => s.id === id || s.meta.name === id) || null;
}

export function loadSkillContent(id: string, agentId?: string): string {
  const skill = getSkillById(id, agentId);
  if (!skill) return `Skill "${id}" not found.`;

  const parts: string[] = [`# ${skill.meta.name || skill.id}\n`];
  parts.push(skill.body);

  for (const refPath of skill.references) {
    const name = path.basename(refPath, ".md");
    const content = fs.readFileSync(refPath, "utf-8");
    parts.push(`\n\n## Reference: ${name}\n\n${content}`);
  }

  return parts.join("\n");
}

export function buildSkillSummary(agentId?: string): string {
  const skills = mergeSkills(agentId);
  if (skills.length === 0) return "";

  const lines: string[] = [
    "\n\n## 可用 Skills\n",
    "你拥有以下 skill 知识。当用户的问题与某个 skill 相关时，先使用 skill 工具加载对应知识，然后按照知识指引来执行：\n",
  ];

  for (const skill of skills) {
    const desc = skill.meta.description || "";
    const trigger = skill.meta.metadata?.trigger || "";
    lines.push(`- **${skill.meta.name || skill.id}** (\`${skill.id}\`): ${desc}`);
    if (trigger) lines.push(`  触发词: ${trigger}`);
  }

  lines.push("\n使用 `skill` 工具加载某个 skill 的完整知识后，再按指引操作。\n");

  return lines.join("\n");
}
