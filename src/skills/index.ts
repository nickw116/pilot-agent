import fs from "fs";
import path from "path";
import { parse as parseYaml } from "yaml";

export type SkillPriority = "high" | "medium" | "low";

export interface SkillTriggers {
  keywords: string[];
  intents: string[];
}

export interface SkillMeta {
  name: string;
  summary: string;
  description?: string;
  userInvocable: boolean;
  priority: SkillPriority;
  category?: string;
  triggers: SkillTriggers;
  notFor: string[];
  examples: string[];
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

const PRIORITY_ORDER: Record<SkillPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

// --- helpers ---

function dedupe(arr: string[]): string[] {
  return [...new Set(arr)];
}

function firstSentence(text: string): string {
  if (!text) return "";
  const line = text.split(/\n/)[0].trim();
  // 只识别中文句号/感叹号/问号 —— 避免英文点号误伤 URL、版本号、缩写
  const sentence = line.split(/[。！？]/)[0].trim();
  return sentence || line;
}

function splitTriggerString(trigger?: string): string[] {
  if (!trigger) return [];
  return dedupe(
    trigger
      .split(/[|｜,，;；\s]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0),
  );
}

function normalizeStringArray(value: any): string[] {
  if (!Array.isArray(value)) return [];
  return dedupe(
    value
      .map((v) => String(v).trim())
      .filter((v) => v.length > 0),
  );
}

function extractFromBody(body: string): { name: string; keywords: string[] } {
  let name = "";
  let keywords: string[] = [];

  const h1 = body.match(/^#\s+(.+)$/m);
  if (h1) name = h1[1].trim();

  // 提取 ## 触发条件 / ## 触发 / ## Trigger 章节
  const triggerSection = body.match(
    /##\s*(触发条件|触发|Trigger|Triggers|When to use)[^\n]*\n([\s\S]*?)(?=\n##\s|$)/i,
  );
  if (triggerSection) {
    const section = triggerSection[2];
    const itemMatches = section.matchAll(/^\s*[-*]\s*(.+)$/gm);
    for (const m of itemMatches) {
      const line = m[1].trim();
      // 过滤掉"当用户提及..."这类引导句
      if (/^(当|如果|若|用户)/.test(line)) continue;
      // 拆分"关键词 / 关键词 / 关键词"
      const parts = line
        .split(/[/／、,，|｜·]/)
        .map((s) => s.trim())
        .filter((s) => s && s.length <= 16);
      keywords.push(...parts);
    }
  }

  return { name, keywords: dedupe(keywords) };
}

// --- frontmatter parsing ---

function buildDefaultMeta(): SkillMeta {
  return {
    name: "",
    summary: "",
    userInvocable: false,
    priority: "medium",
    triggers: { keywords: [], intents: [] },
    notFor: [],
    examples: [],
    metadata: {},
  };
}

function parseFrontmatter(raw: string): { meta: SkillMeta; body: string } {
  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  const body = fmMatch ? fmMatch[2].trim() : raw.trim();

  if (!fmMatch) {
    const extracted = extractFromBody(body);
    return {
      meta: {
        ...buildDefaultMeta(),
        name: extracted.name,
        summary: extracted.name,
        triggers: { keywords: extracted.keywords, intents: [] },
      },
      body,
    };
  }

  let parsed: any = {};
  try {
    parsed = parseYaml(fmMatch[1]) || {};
  } catch (err) {
    console.warn(`[skills] frontmatter YAML 解析失败，降级到 body 提取:`, (err as Error).message);
    const extracted = extractFromBody(body);
    return {
      meta: {
        ...buildDefaultMeta(),
        name: extracted.name,
        summary: extracted.name,
        triggers: { keywords: extracted.keywords, intents: [] },
      },
      body,
    };
  }

  // 兼容老字段
  const name = String(parsed.name || "").trim();
  const description = String(parsed.description || parsed.description_zh || "").trim();
  const summary = String(parsed.summary || firstSentence(description) || name).trim();

  // 老 metadata.trigger（正则字符串）→ keywords
  const legacyTrigger = splitTriggerString(parsed.metadata?.trigger);

  // 新 triggers
  const triggersField = parsed.triggers || {};
  const keywords = dedupe([
    ...normalizeStringArray(triggersField.keywords),
    ...legacyTrigger,
  ]);
  const intents = normalizeStringArray(triggersField.intents);

  // not_for / notFor
  const notFor = normalizeStringArray(parsed.not_for || parsed.notFor);

  // examples
  const examples = normalizeStringArray(parsed.examples);

  // priority
  const rawPriority = String(parsed.priority || "medium").toLowerCase();
  const priority: SkillPriority = (["high", "medium", "low"] as const).includes(
    rawPriority as SkillPriority,
  )
    ? (rawPriority as SkillPriority)
    : "medium";

  // user-invocable
  const userInvocable =
    parsed["user-invocable"] === true || parsed.userInvocable === true;

  const meta: SkillMeta = {
    name,
    summary,
    description: description || undefined,
    userInvocable,
    priority,
    category: parsed.category ? String(parsed.category).trim() : undefined,
    triggers: { keywords, intents },
    notFor,
    examples,
    metadata: parsed.metadata || {},
  };

  return { meta, body };
}

// --- skill loading ---

function findReferences(dir: string): string[] {
  const refs: string[] = [];
  const refDir = path.join(dir, "references");
  if (!fs.existsSync(refDir)) return refs;
  for (const f of fs.readdirSync(refDir)) {
    if (f.endsWith(".md")) refs.push(path.join(refDir, f));
  }
  return refs;
}

export function loadSkill(dir: string, id: string): Skill | null {
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

// --- skill summary (injected into system prompt) ---

export function buildSkillSummary(
  agentId?: string,
  allowedSkillIds?: string[],
): string {
  let skills = mergeSkills(agentId);
  if (allowedSkillIds !== undefined) {
    // 空数组 = 显式不注入任何 skill；undefined = 不过滤
    skills = skills.filter(
      (s) => allowedSkillIds.includes(s.id) || allowedSkillIds.includes(s.meta.name),
    );
  }
  if (skills.length === 0) return "";

  // 排序：priority → category → name
  const sorted = [...skills].sort((a, b) => {
    const p = PRIORITY_ORDER[a.meta.priority] - PRIORITY_ORDER[b.meta.priority];
    if (p !== 0) return p;
    const c = (a.meta.category || "其他").localeCompare(
      b.meta.category || "其他",
      "zh",
    );
    if (c !== 0) return c;
    return (a.meta.name || a.id).localeCompare(b.meta.name || b.id, "zh");
  });

  // 分组：按 category
  const groups = new Map<string, Skill[]>();
  for (const s of sorted) {
    const cat = s.meta.category || "其他";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat)!.push(s);
  }

  const lines: string[] = [
    "\n\n## 可用 Skills\n",
    "你拥有以下 skill 知识。当用户的问题与某个 skill 的关键词/意图/示例匹配时，先调用 `skill` 工具加载完整知识，再按指引执行。\n",
  ];

  for (const [category, groupSkills] of groups) {
    lines.push(`\n### ${category}`);
    for (const skill of groupSkills) {
      const name = skill.meta.name || skill.id;
      const summary = skill.meta.summary || "";
      lines.push(`- **${name}** (\`${skill.id}\`) [${skill.meta.priority}]：${summary}`);
      if (skill.meta.triggers.keywords.length > 0) {
        lines.push(`  - 关键词: ${skill.meta.triggers.keywords.slice(0, 8).join("、")}`);
      }
      if (skill.meta.triggers.intents.length > 0) {
        lines.push(`  - 意图: ${skill.meta.triggers.intents.slice(0, 3).join("；")}`);
      }
      if (skill.meta.examples.length > 0) {
        lines.push(`  - 示例: "${skill.meta.examples[0]}"`);
      }
      if (skill.meta.notFor.length > 0) {
        lines.push(`  - 不适用: ${skill.meta.notFor.slice(0, 2).join("；")}`);
      }
    }
  }

  lines.push("\n### 触发规则");
  lines.push("1. 用户问题命中某 skill 的关键词/意图/示例 → 立即调用 `skill` 工具加载知识");
  lines.push("2. 多个 skill 重叠时，参考「不适用」字段做取舍");
  lines.push("3. 明显不相关时**不要**加载（节省 token）");
  lines.push("4. 拿不准时优先加载，加载后判断是否真适用");
  lines.push("5. **硬约束**：涉及时事/新闻/实时数据/训练截止后的新事实时，必须调用 `web-search`，禁止用 bash 自行 curl/爬取网页（你无法处理反爬，只会失败）\n");

  return lines.join("\n");
}
