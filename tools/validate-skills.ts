#!/usr/bin/env tsx
import fs from "fs";
import path from "path";
import { loadSkill, type Skill } from "../src/skills/index.js";

interface Finding {
  level: "ERROR" | "WARN" | "OK";
  skillId: string;
  message: string;
}

const VALID_PRIORITIES = new Set(["high", "medium", "low"]);

function scanDir(baseDir: string, scope: string): { id: string; dir: string; scope: string }[] {
  const out: { id: string; dir: string; scope: string }[] = [];
  if (!fs.existsSync(baseDir)) return out;
  for (const entry of fs.readdirSync(baseDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const dir = path.join(baseDir, entry.name);
    if (!fs.existsSync(path.join(dir, "SKILL.md"))) continue;
    out.push({ id: entry.name, dir, scope });
  }
  return out;
}

function validate(skill: Skill, scope: string): Finding[] {
  const findings: Finding[] = [];
  const id = `${scope}/${skill.id}`;
  const m = skill.meta;

  if (!m.name) {
    findings.push({ level: "ERROR", skillId: id, message: "name 为空" });
  }
  if (!m.summary) {
    findings.push({ level: "ERROR", skillId: id, message: "summary 为空（frontmatter 缺 summary 且无法从 description/body 推断）" });
  }
  if (m.summary && m.summary.length > 80) {
    findings.push({ level: "WARN", skillId: id, message: `summary 偏长（${m.summary.length} 字符，建议 ≤80）：${m.summary.slice(0, 40)}...` });
  }
  if (!VALID_PRIORITIES.has(m.priority)) {
    findings.push({ level: "ERROR", skillId: id, message: `priority "${m.priority}" 不是 high/medium/low` });
  }
  if (!m.category) {
    findings.push({ level: "WARN", skillId: id, message: "category 未设置（会被归到「其他」分组）" });
  }
  if (m.triggers.keywords.length === 0) {
    findings.push({ level: "WARN", skillId: id, message: "triggers.keywords 为空，模型几乎只能靠 summary 匹配" });
  } else if (m.triggers.keywords.length > 10) {
    findings.push({ level: "WARN", skillId: id, message: `keywords 偏多（${m.triggers.keywords.length} 个，摘要只展示前 8 个）` });
  }
  if (m.triggers.intents.length === 0) {
    findings.push({ level: "WARN", skillId: id, message: "triggers.intents 为空（强烈建议补 1-3 条自然语言意图，命中率显著提升）" });
  }
  if (m.examples.length === 0) {
    findings.push({ level: "WARN", skillId: id, message: "examples 为空（建议至少 1 条真实用户说法）" });
  }

  if (findings.length === 0) {
    findings.push({ level: "OK", skillId: id, message: `category=${m.category} priority=${m.priority} kw=${m.triggers.keywords.length} intents=${m.triggers.intents.length}` });
  }
  return findings;
}

function main(): number {
  const cwd = process.cwd();
const targets = [
  ...scanDir(path.join(cwd, "src", "skills"), "global"),
  ...fs
    .readdirSync(path.join(cwd, "src", "agents"), { withFileTypes: true })
    .filter((e) => e.isDirectory() && !e.name.startsWith(".") && e.name !== "node_modules")
    .flatMap((a) => scanDir(path.join(cwd, "src", "agents", a.name, "skills"), `agent:${a.name}`)),
];

  if (targets.length === 0) {
    console.log("没有发现任何 SKILL.md");
    return 0;
  }

  console.log(`扫描 ${targets.length} 个 skill...\n`);

  let errors = 0;
  let warns = 0;
  let oks = 0;
  for (const t of targets) {
    const skill = loadSkill(t.dir, t.id);
    if (!skill) {
      console.log(`❌ ${t.scope}/${t.id}: SKILL.md 存在但加载失败`);
      errors++;
      continue;
    }
    for (const f of validate(skill, t.scope)) {
      const tag = f.level === "ERROR" ? "❌" : f.level === "WARN" ? "⚠️ " : "✅";
      console.log(`${tag} ${f.skillId}: ${f.message}`);
      if (f.level === "ERROR") errors++;
      else if (f.level === "WARN") warns++;
      else oks++;
    }
  }

  console.log(`\n汇总：✅ ${oks} ok / ⚠️  ${warns} warn / ❌ ${errors} error`);

  return errors > 0 ? 1 : 0;
}

process.exit(main());
