# Pilot Code

AI 编程助手后端服务，为 H5 前端提供多 agent 对话能力（Express + SSE）。

## 技术栈

- 后端：Node.js + TypeScript，用 `tsx` 直接运行（不编译）
- SDK：`@mariozechner/pi-agent-core`（Agent 类）+ `@mariozechner/pi-ai`（模型/流式）
- 前端：Vue 3 + Vant 4 + Vite
- 数据库：better-sqlite3（users.db + sessions.db）
- 通信：Express REST + SSE

## 常用命令

```bash
npx tsc --noEmit          # 类型检查
npm run dev               # 开发（自动重启）
npm start                 # 生产
cd frontend && npm run build  # 前端构建
sudo systemctl restart pilot-agent  # 重启服务（生产）
curl -s http://127.0.0.1:8081/api/health  # 健康检查 → {"status":"ok"}
```

## 项目结构

```
src/
├── index.ts          # Express 入口，所有路由，端口 8081
├── agent.ts          # Agent 生命周期、prompt 组装、子 agent 执行
├── tools.ts          # Agent 工具集 + delegate 工具 + 工作区管理
├── bootstrap.ts      # Bootstrap 文件管理（源码 → 运行时同步）
├── memory.ts         # 记忆系统（MEMORY.md + 每日笔记）
├── acp-client.ts     # ACP 协议客户端（claude_code 工具的底层）
├── session.ts        # 会话管理（SQLite）
├── sse.ts            # SSE pub/sub 事件分发
├── event-bridge.ts   # Pi Agent 事件 → SSE 事件转换
├── compaction.ts     # 对话上下文压缩
├── auth.ts           # 用户认证（users.db SQLite）
├── agents/           # Agent 定义（源码级，git 版本控制）
│   ├── main/         #   config.json + AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md
│   ├── dev/
│   └── user/
├── audit.ts          # 审计日志
├── rate-limit.ts     # 请求限流
├── review.ts         # MIMO 自动代码审查
└── skills/           # Skill 定义（stock-chart-analysis、github 等）

frontend/src/
├── App.vue            # 根组件
├── composables/       # useAuth, useChat, useSend, useStreaming, useEventStream
├── components/        # SettingsPopup, SessionList, MessageInput, MessageBubble, AcpLogPanel
├── pages/             # LoginPage, ChatPage
├── router/            # 路由配置
└── constants/         # API 路径、token key
```

## 编码约定

- 后端用 ESM（`"type": "module"`），import 带 `.js` 后缀（tsx 自动解析 `.ts`）
- 不用 `tsc` 编译，直接 `tsx` 运行，但保持类型正确（`npx tsc --noEmit` 通过）
- 前端是 Vue 3 Composition API + `<script setup>`，UI 库 Vant 4
- 数据库用 better-sqlite3，同步 API，schema 直接在代码中
- bash 安全过滤在 `tools.ts` 的 `DANGEROUS_COMMANDS` 数组中
- 不添加注释，除非用户明确要求

## 多 Agent 架构

每个 agent 在 `src/agents/<id>/` 目录下自包含定义，`agents.json` 仅保留全局模型配置。

| Agent ID | 名称 | 角色 | 工具 | 工作区 |
|----------|------|------|------|--------|
| `main` | 智能助手 | 协调器 | read, write, edit, bash, skill, delegate | `main/user-<id>/` |
| `dev` | 开发助手 | 子 agent | claude_code（ACP）, skill | `dev/user-<id>/` |
| `user` | 个人助手 | 独立 | read, bash, skill | `user/user-<id>/` |

`src/agents/*/AGENTS.md` 是运行时 agent 配置，不是 OpenCode 指令。

## 改动验证

每次代码修改后必须执行：

1. `npx tsc --noEmit` — 类型检查通过
2. `cd frontend && npm run build` — 前端构建通过
3. `sudo systemctl restart pilot-agent` — 重启服务
4. `curl -s http://127.0.0.1:8081/api/health` — 确认 `{"status":"ok"}`

## 安全红线

- 不读取、不提交 `.env` 文件
- 不修改 `data/workspace/` 下的用户数据
- 不在日志或输出中暴露 API Key

## 项目边界

- 所有操作在 `/home/ubuntu/pilot-agent/` 目录下进行
- 不操作 `/home/ubuntu/.openclaw/`，那是另一个项目
- 修改文件前先用 Read 工具读取当前内容
- 局部修改用 edit，不要用 write 覆写整个文件
