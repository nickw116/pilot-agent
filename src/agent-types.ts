import fs from "fs";
import path from "path";

export interface AgentTypeSuggestion {
  icon: string;
  text: string;
}

export interface AgentType {
  id: string;
  name: string;
  icon: string;
  description: string;
  default: boolean;
  skills: string[] | null;
  promptSuffix: string;
  suggestions: AgentTypeSuggestion[];
}

const TYPES_DIR = path.join(process.cwd(), "src", "agent-types");

let cachedTypes: AgentType[] | null = null;

function loadAgentTypes(): AgentType[] {
  if (cachedTypes) return cachedTypes;

  const types: AgentType[] = [];
  if (!fs.existsSync(TYPES_DIR)) {
    console.warn("[agent-types] directory not found:", TYPES_DIR);
    cachedTypes = types;
    return types;
  }

  const files = fs.readdirSync(TYPES_DIR).filter((f) => f.endsWith(".json"));
  for (const file of files) {
    try {
      const raw = JSON.parse(fs.readFileSync(path.join(TYPES_DIR, file), "utf-8"));
      const t: AgentType = {
        id: String(raw.id || file.replace(/\.json$/, "")),
        name: String(raw.name || raw.id || "Unknown"),
        icon: String(raw.icon || "🤖"),
        description: String(raw.description || ""),
        default: raw.default === true,
        skills: Array.isArray(raw.skills) ? raw.skills.map(String) : null,
        promptSuffix: String(raw.promptSuffix || ""),
        suggestions: Array.isArray(raw.suggestions)
          ? raw.suggestions.map((s: any) => ({
              icon: String(s.icon || "💡"),
              text: String(s.text || ""),
            }))
          : [],
      };
      types.push(t);
    } catch (err) {
      console.error(`[agent-types] failed to load ${file}:`, err);
    }
  }

  const hasDefault = types.some((t) => t.default);
  if (!hasDefault && types.length > 0) types[0].default = true;

  types.sort((a, b) => (b.default ? 1 : 0) - (a.default ? 1 : 0));

  console.log(`[agent-types] loaded ${types.length} agent type(s): ${types.map((t) => t.id).join(", ")}`);
  cachedTypes = types;
  return types;
}

export function getAgentTypes(): AgentType[] {
  return loadAgentTypes();
}

export function getAgentType(id: string): AgentType | null {
  return loadAgentTypes().find((t) => t.id === id) || null;
}

export function getDefaultAgentType(): AgentType {
  const types = loadAgentTypes();
  return types.find((t) => t.default) || types[0] || {
    id: "securities",
    name: "证券分析",
    icon: "📈",
    description: "",
    default: true,
    skills: null,
    promptSuffix: "",
    suggestions: [],
  };
}
