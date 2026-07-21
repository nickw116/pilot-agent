# Pilot Code

AI 编程助手后端服务，为 H5 前端提供对话能力（Express + SSE）。单 agent 架构，通过 agent-type 切换技能组合与提示词。

## 技术栈

- 后端：Node.js + TypeScript，用 `tsx` 直接运行（不编译）
- SDK：`@mariozechner/pi-agent-core`（Agent 类）+ `@mariozechner/pi-ai`（模型/流式）
- 前端：Vue 3 + Vant 4 + Vite
- 数据库：better-sqlite3（users.db + sessions.db）
- 通信：Express REST + SSE

## 常用命令

```bash
npx tsc --noEmit          # 类型检查（注意：吃内存，低内存机器慎跑）
npm run dev               # 开发（自动重启）
npm start                 # 生产
cd frontend && npm run build  # 前端构建
bash tools/request-restart.sh  # 生产环境温和重启（等当前任务完成）
curl -s http://127.0.0.1:8081/api/health  # 健康检查 → {"status":"ok"}
```

> ⚠️ **禁止直接 `systemctl restart/stop pilot-agent`**：会杀死正在处理用户请求的进程。只能用 `tools/request-restart.sh`。

## 项目结构

```
src/
├── index.ts          # Express 入口，所有路由，端口 8081
├── agent.ts          # Agent 生命周期、prompt 组装、agent-type 切换
├── agent-types.ts    # Agent-type 加载器（读取 src/agent-types/*.json）
├── agent-types/      # Agent-type 定义（general / ppt / securities）
│   ├── general.json
│   ├── ppt.json
│   └── securities.json
├── tools.ts          # Agent 工具集（read/write/edit/bash/skill）+ 工作区管理
├── bootstrap.ts      # Bootstrap 文件管理（源码 → 运行时同步）
├── memory.ts         # 记忆系统（MEMORY.md + 每日笔记）
├── session.ts        # 会话管理（SQLite），session key: agent:<id>:h5-<user>-<ts>
├── sse.ts            # SSE pub/sub 事件分发
├── event-bridge.ts   # Pi Agent 事件 → SSE 事件转换
├── compaction.ts     # 对话上下文压缩
├── auth.ts           # 用户认证（users.db SQLite）
├── audit.ts          # 审计日志
├── rate-limit.ts     # 请求限流
├── agents/           # Agent 定义（源码级，git 版本控制）
│   └── user/         #   config.json + AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md
└── skills/           # 全局 Skill 定义（src/skills/<id>/SKILL.md）
    ├── index.ts      #   skill 加载器
    ├── github/、web-search/、web-reader/
    ├── stock-chart-analysis/、stock-fundamental-analysis/
    ├── gs-stock-market-query/、gs-stock-financial-query/、gs-economy-query/...
    ├── ppt-maker/、md-to-slides/、beautiful-mermaid/
    ├── tencent-docs/、tencent-cos-skill/、tencent-meeting-skill/、tencentcloud-lighthouse-skill/
    ├── quadrant-analysis/、serenity-analysis/、five-elements-analysis/
    └── ...

frontend/src/
├── App.vue            # 根组件
├── composables/       # useAuth, useChat, useSend, useStreaming, useEventStream
├── components/        # SettingsPopup, SessionList, MessageInput, MessageBubble, AcpLogPanel
├── pages/             # LoginPage, ChatPage
├── router/            # 路由配置
└── constants/         # API 路径、token key
```

## 架构：单 Agent + 多 Agent-Type

只有**一个 agent**：`user`（Pilot Agent）。不再有 main/dev 子 agent，不再有 delegate 工具、claude_code、ACP 子进程。所有需求由 user agent 直接用 `read/write/edit/bash/skill` 工具处理。

### Agent 定义

`src/agents/user/`：

| 文件 | 作用 |
|------|------|
| `config.json` | agent 配置：`name`、`model`、`tools`、`hidden` |
| `AGENTS.md` | 运行时行为指令（不是本仓库的指令文件） |
| `SOUL.md` | 人格/语气 |
| `IDENTITY.md` | Agent 身份 |
| `TOOLS.md` | 工具备注 |

> 注意：`src/agents/user/AGENTS.md` 是**运行时 agent 配置**，不是本仓库的 AGENTS.md 指令文件。两者同名但职责不同。

### Agent-Type（模式切换）

`src/agent-types/*.json` 定义若干"模式"，每个 type 决定：
- `skills`：该模式下可用的 skill 白名单（`null` = 全部）
- `promptSuffix`：追加到 system prompt 末尾的模式专属指令
- `suggestions`：前端的快捷建议词
- `default`：是否默认模式

| Type ID | 名称 | 默认 | 定位 |
|---------|------|------|------|
| `securities` | 证券分析 | ✅ | A 股技术面 + 基本面、行情、选股、财经新闻 |
| `general` | 通用助手 | | 日常问答、写作、编程、文档、云服务 |
| `ppt` | PPT 制作 | | 大纲设计、Markdown 转 PPT、图表 |

用户在前端切换 type → 调用 `/api/session/agent-type` → `agent.ts` 检测 type 变化后**销毁旧 Agent 实例、重建新实例**（不同 type 有不同 system prompt + 不同 skill 白名单）。

### 模型

`agents.json` 配置全局模型池：

| 模型 ID | 用途 | 特点 |
|---------|------|------|
| `minimax/m3` | **默认主模型** | 100 万 context，支持图片输入，reasoning |
| `deepseek/deepseek-v4-flash` | fallback | 128K context，轻量快速 |

`user` agent 默认用 `minimax/m3`，可在会话中通过 `/api/model/switch` 切换。

## 交互流程

```
用户 → user agent（唯一入口，agent-type 决定 skill 白名单）
         ├── 简单任务：直接用 read/write/edit/bash
         ├── 联网/搜索：skill → web-search / web-reader
         ├── 证券分析：skill → stock-* / gs-* / quadrant-analysis
         ├── 文档产出：skill → ppt-maker / md-to-slides / tencent-docs
         └── 记忆：memory_save / memory_search 工具
```

## 工作区结构

两级 workspace：**agent 级（共享）+ user 级（按用户隔离）**。

```
data/workspace/
└── user/                                   ← agent 级（agentId="user"）
    └── user-<userId>/                      ← user 级（按 userId 隔离）
        ├── AGENTS.md                       ← 操作指令（从源码同步）
        ├── SOUL.md                         ← 人格/语气
        ├── USER.md                         ← 用户档案（运行时可写）
        ├── IDENTITY.md                     ← Agent 身份
        ├── TOOLS.md                        ← 工具备注
        ├── memory/                         ← 记忆系统
        │   ├── MEMORY.md                   ← 长期记忆
        │   └── YYYY-MM-DD.md               ← 每日笔记
        ├── uploads/                        ← 上传文件
        └── charts/                         ← 生成的图表（matplotlib savefig 输出）
```

## Prompt 组装

```
agentBootstrap (AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md)
  + userBootstrap (USER.md)
  + skillSummary（按 agentType 过滤后的可用 skills）
  + memorySection（MEMORY.md + 近两日笔记）
  + agentType.promptSuffix（模式专属指令）
```

## 权限

- admin / 普通用户都用同一个 `user` agent，差异在于会话隔离和可访问的 API（如 `/api/admin/sessions` 仅 admin）
- 会话隔离：每个用户访问自己的 `user-<userId>/` 工作区

## 关键 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` / `/api/logout` | 登录 / 登出 |
| GET | `/api/status` | 当前用户状态 |
| POST | `/api/change-password` | 改密 |
| GET | `/api/agents` | agent 列表（当前只有 user） |
| GET | `/api/agent-types` | agent-type 列表 + 默认 type |
| GET | `/api/session` / `/api/sessions` | 当前/全部会话 |
| GET | `/api/admin/sessions` | 全部会话（admin only） |
| POST | `/api/session/new` / `/api/sessions` | 创建会话 |
| DELETE | `/api/session/:key` / `/api/sessions` | 删除会话 |
| PUT | `/api/sessions/active` | 切换活跃会话 |
| POST | `/api/session/agent-type` | 切换 agent-type |
| POST | `/api/chat/v2` | 发消息（fire-and-forget，返回 runId） |
| POST | `/api/chat` / `/api/chat/append` | 发消息（其它变体） |
| POST | `/api/abort` | 中止当前 run |
| GET | `/api/events?sessionKey=xxx` | SSE 事件流 |
| POST | `/api/events/ack` | 确认事件已读 |
| GET | `/api/history?sessionKey=xxx` | 历史消息 |
| GET | `/api/models` / POST `/api/model/switch` | 模型列表/切换 |
| POST | `/api/upload` | 文件上传 |
| POST | `/api/stt` | 语音转文字 |
| GET | `/api/download` / `/api/local-file` / `/api/resolve-attachment` | 文件下载/本地文件/附件解析 |
| GET | `/api/context/stats` / `/api/agent-dashboard` | 上下文统计 / Agent 仪表盘 |
| GET | `/api/health` | 健康检查 → `{"status":"ok"}` |

## 编码约定

- 后端用 ESM（`"type": "module"`），import 带 `.js` 后缀（tsx 自动解析 `.ts`）
- 不用 `tsc` 编译，直接 `tsx` 运行，但保持类型正确（`npx tsc --noEmit` 通过）
- 前端是 Vue 3 Composition API + `<script setup>`，UI 库 Vant 4
- 数据库用 better-sqlite3，同步 API，schema 直接在代码中
- bash 安全过滤在 `tools.ts` 的 `DANGEROUS_COMMANDS` 数组中
- 不添加注释，除非用户明确要求

## 改动验证

改完代码后必须验证无回归：

1. `npx tsc --noEmit` — 类型检查通过（**内存吃紧时跳过**，服务器曾因内存不足被冻结）
2. `cd frontend && npm run build` — 前端构建通过
3. `bash tools/request-restart.sh` — 温和重启服务
4. `curl -s http://127.0.0.1:8081/api/health` — 确认启动正常
5. **端到端 API 测试**（每次代码改动都必须执行）：
   - 登录：`curl -s http://127.0.0.1:8081/api/login -X POST -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'` → 获取 token
   - 用获取的 token 测试相关 API 端点（sessions、history、agents、agent-types 等），确认返回格式正确、状态码正常
   - 如有权限相关改动，需分别用不同权限级别的用户测试（admin/user）

## 安全红线

- 不读取、不提交 `.env` 文件（含 `MINIMAX_API_KEY` / `DEEPSEEK_API_KEY`）
- 不修改 `data/workspace/` 下的用户数据
- 不在日志或输出中暴露 API Key
- 不直接 `systemctl restart/stop pilot-agent`（用 `tools/request-restart.sh`）

## 注意

- `data/` 存运行时数据（sessions、workspace），不在 git 中（已在 `.gitignore`）
- 生产前端由 Express 直接 serve `frontend/dist/`
- `data.pre-single-agent-backup/` 是多 agent → 单 agent 重构前的数据备份，不在 git 中

## 项目边界

- 所有操作在 `/home/ubuntu/pilot-agent/` 目录下进行
- 修改文件前先用 Read 工具读取当前内容
- 局部修改用 Edit，不要用 Write 覆写整个文件（除非整体重写）
