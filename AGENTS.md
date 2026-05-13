# Pilot Code

AI 编程助手后端服务，基于 Pi Agent SDK，通过 Express + SSE 为 H5 前端提供多 agent 对话能力。

## 项目结构

```
pilot-code/
├── src/                    # 后端 TypeScript 源码（tsx 运行，不编译）
│   ├── index.ts            # Express 入口，路由定义，端口 8081
│   ├── agent.ts            # Agent 生命周期：创建、销毁、模型切换、空闲回收
│   ├── tools.ts            # Agent 工具集：read/write/edit/bash/opencode/claude_code
│   ├── auth.ts             # 用户认证（users.db SQLite）
│   ├── session.ts          # 会话管理（SQLite），session key 格式 agent:<agentId>:h5-<user>-<ts>
│   ├── sse.ts              # SSE pub/sub 事件分发
│   ├── event-bridge.ts     # Pi Agent 事件 → SSE 事件转换
│   ├── compaction.ts       # 对话上下文压缩
│   ├── acp-client.ts       # ACP 协议客户端（opencode / claude_code 工具）
│   ├── audit.ts            # 审计日志
│   └── rate-limit.ts       # 请求限流
├── frontend/               # Vue 3 + Vant 4 + Vite 前端
│   └── src/
│       ├── App.vue         # 根组件，状态编排
│       ├── composables/    # useAuth, useChat, useSend, useStreaming, useEventStream 等
│       ├── components/     # SettingsPopup, SessionList, MessageInput 等
│       ├── pages/          # LoginPage, ChatPage
│       └── constants/      # API 路径、token key
├── agents.json             # Agent 配置：角色、模型、工具白名单、systemPrompt
├── .env                    # API Key、端口、路径配置
└── data/                   # 运行时数据（gitignore）：sessions/、workspace/
```

## 多 Agent 架构

`agents.json` 定义三个 agent，各有独立工具权限和工作区：

| Agent ID | 名称 | 工具 | 工作区 |
|----------|------|------|--------|
| `main` | 运维助手 | read, write, edit, bash, opencode, claude_code | `user-<id>/` |
| `dev` | 开发助手 | read, bash, opencode, claude_code | `user-<id>/dev/` |
| `user` | 个人助手 | read, bash | `user-<id>/user/` |

- Session key 格式：`agent:<agentId>:h5-<username>-<timestamp>`
- 工具过滤：`createUserTools(workspace, allowedTools)` 按 `agents.json` 的 `tools` 数组过滤
- 前端 `GET /api/agents` 获取 agent 列表，设置页可切换

## 技术栈

- **后端**：Node.js + TypeScript (tsx 直接运行，不经过 tsc 编译)
- **Pi SDK**：`@mariozechner/pi-agent-core` (Agent 类) + `@mariozechner/pi-ai` (模型/流式)
- **前端**：Vue 3 Composition API + Vant 4 + Vite
- **数据库**：better-sqlite3（users.db + sessions.db）
- **通信**：Express REST API + SSE (两种模式：legacy per-request SSE / persistent event stream)

## 构建 & 运行

```bash
# 后端类型检查
npx tsc --noEmit

# 后端启动（开发，自动重启）
npm run dev

# 后端启动（生产）
npm start

# 前端构建
cd frontend && npm run build

# 生产部署用 systemd
sudo systemctl restart pilot-code
```

## API 端点（主要）

- `POST /api/login` — 登录
- `POST /api/chat/v2` — 发送消息（fire-and-forget，返回 runId）
- `GET /api/events?sessionKey=xxx` — SSE 事件流
- `GET /api/agents` — 获取 agent 列表
- `POST /api/sessions` — 创建新会话（body: `{ agent_id }`）
- `GET /api/models` — 获取模型列表
- `POST /api/model/switch` — 切换模型

## 端到端测试验证（必须）

**每次修改代码后，必须执行端到端测试验证改动生效且无回归。** 不可跳过。

### 后端验证步骤

```bash
# 1. 类型检查通过
npx tsc --noEmit

# 2. 重启服务
sudo systemctl restart pilot-code

# 3. 检查服务启动正常
curl -s http://127.0.0.1:8081/api/health
# 期望：{"status":"ok","version":"0.3.0"}

# 4. 测试登录获取 token
TOKEN=$(curl -s -X POST http://127.0.0.1:8081/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"test"}' | jq -r '.token')

# 5. 测试 agent 列表
curl -s http://127.0.0.1:8081/api/agents \
  -H "Authorization: Bearer $TOKEN" | jq .
# 期望：返回 3 个 agent（main/dev/user），各自 tools 数组正确

# 6. 测试创建会话（指定 agent_id）
curl -s -X POST http://127.0.0.1:8081/api/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"dev"}' | jq .
# 期望：返回 sessionKey 包含 "agent:dev:h5-"

# 7. 测试发送消息（SSE 流）
curl -s -N -X POST http://127.0.0.1:8081/api/chat/v2 \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":"你好","session_key":"<上一步的 sessionKey>"}'
# 期望：返回 runId，且 SSE 事件流正常推送
```

### 前端验证步骤

```bash
# 1. 构建前端
cd frontend && npm run build

# 2. 浏览器验证
#    - 打开页面，登录
#    - 打开设置页，确认显示 3 个 agent 卡片（运维助手/开发助手/个人助手）
#    - 切换到不同 agent，确认创建新会话且 session key 包含对应 agent_id
#    - 发送消息，确认 SSE 流式响应正常
```

### 改动范围与最小验证

| 改动文件 | 必须验证 |
|---------|---------|
| `agents.json` | agent 列表 API、工具权限隔离 |
| `src/agent.ts` | agent 创建、工具加载、模型切换 |
| `src/tools.ts` | 工具执行、allowedTools 过滤 |
| `src/index.ts` | 路由、API 端点 |
| `src/session.ts` | 会话创建、agent_id 路由 |
| `frontend/src/components/SettingsPopup.vue` | 设置页 agent 选择器 |
| `frontend/src/App.vue` | agent 切换流程 |

## 注意事项

- `.env` 含 API Key，不在 git 中，修改配置需手动编辑
- `data/` 目录存放运行时数据（sessions、workspace），不在 git 中
- 前端 API 代理通过 vite.config.js 代理到后端 8081 端口
- 生产环境前端静态文件由后端 Express 直接 serve（`frontend/dist/`）
- ACP 工具（opencode/claude_code）依赖环境变量 `OPENCODE_ENABLED`/`CLAUDE_CODE_ENABLED`
