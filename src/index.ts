import "dotenv/config";
import express from "express";
import crypto from "crypto";
import { registerSubscriber, unregisterSubscriber, publish } from "./sse.js";
import * as agentModule from "./agent.js";

const PORT = parseInt(process.env.PORT || "8081", 10);
const HARDCODED_TOKEN = "pilot-mvp-token-2026";
const SESSION_KEY = "pilot:h5-mvp";

const app = express();
app.use(express.json({ limit: "10mb" }));

// CORS
app.use((_req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Headers", "Authorization, Content-Type");
  res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  if (_req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

// --- Auth middleware ---
function auth(req: express.Request, res: express.Response, next: express.NextFunction) {
  const token = req.headers.authorization?.replace("Bearer ", "");
  if (!token || token !== HARDCODED_TOKEN) {
    return res.status(401).json({ detail: "Unauthorized" });
  }
  (req as any).user = { username: "pilot", role: "admin" };
  next();
}

// --- Routes ---

app.post("/api/login", (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    return res.status(400).json({ detail: "Missing username or password" });
  }
  res.json({
    token: HARDCODED_TOKEN,
    username,
    role: "admin",
    display_name: username,
  });
});

app.get("/api/status", auth, (_req, res) => {
  res.json({ connected: true, user: (_req as any).user.username, role: "admin" });
});

app.post("/api/change-password", auth, (_req, res) => {
  res.json({ ok: true });
});

app.get("/api/session", auth, (_req, res) => {
  res.json({ sessionKey: SESSION_KEY });
});

app.get("/api/sessions", auth, (_req, res) => {
  res.json({ sessions: [{ sessionKey: SESSION_KEY, title: "Pilot MVP", active: true }] });
});

app.post("/api/session/new", auth, (_req, res) => {
  res.json({ sessionKey: SESSION_KEY });
});

app.post("/api/sessions", auth, (_req, res) => {
  res.json({ sessionKey: SESSION_KEY });
});

app.put("/api/sessions/active", auth, (_req, res) => {
  res.json({ ok: true });
});

app.delete("/api/sessions", auth, (_req, res) => {
  res.json({ ok: true });
});

app.post("/api/chat/v2", auth, (req, res) => {
  const { message } = req.body || {};
  if (!message) return res.status(400).json({ detail: "No message" });

  // Fire-and-forget: respond immediately, agent runs in background
  agentModule.runPrompt(message).catch((err) => {
    console.error("[chat/v2] agent error:", err.message);
  });

  res.json({ ok: true, sessionKey: SESSION_KEY });
});

// Legacy chat alias
app.post("/api/chat", (req, _res, next) => {
  req.url = "/api/chat/v2";
  next("router");
});

app.post("/api/abort", auth, (_req, res) => {
  agentModule.abort();
  res.json({ ok: true });
});

app.get("/api/events", auth, (req, res) => {
  const sessionKey = (req.query.sessionKey as string) || SESSION_KEY;

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders();

  const subscriberId = crypto.randomUUID();
  registerSubscriber(sessionKey, subscriberId, res as any);

  // Heartbeat
  const heartbeat = setInterval(() => {
    try { res.write(":\n\n"); } catch { clearInterval(heartbeat); }
  }, 8000);

  req.on("close", () => {
    clearInterval(heartbeat);
    unregisterSubscriber(sessionKey, subscriberId);
  });
});

app.post("/api/events/ack", auth, (_req, res) => {
  res.json({ ok: true });
});

app.get("/api/history", auth, (_req, res) => {
  res.json({ entries: [], messages: [] });
});

app.get("/api/models", auth, (_req, res) => {
  res.json({
    models: [
      { id: "xiaomi/mimo-v2.5-pro", name: "MiMo V2.5 Pro", alias: "MiMo Pro" },
      { id: "deepseek/deepseek-v4-flash", name: "DeepSeek V4 Flash", alias: "DeepSeek" },
    ],
  });
});

app.post("/api/model/switch", auth, (_req, res) => {
  res.json({ ok: true });
});

app.post("/api/upload", auth, (_req, res) => {
  res.json({ url: "", detail: "not implemented in MVP" });
});

app.get("/api/download", auth, (_req, res) => {
  res.status(404).json({ detail: "not implemented in MVP" });
});

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", version: "0.1.0" });
});

// --- Start ---
app.listen(PORT, () => {
  console.log(`Pilot Code bridge listening on http://0.0.0.0:${PORT}`);
  console.log(`Workspace: ${process.env.WORKSPACE_DIR || "data/workspace"}`);
});
