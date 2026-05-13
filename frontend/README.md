# h5-frontend

> H5 聊天前端 — 基于 Vue 3 + Vant 的移动端 AI 聊天应用

## 架构概览

```
用户浏览器
    │
    ├── GET /chat/* ──► Caddy ──► 静态文件 (/var/www/chat)
    │
    ├── POST /api/chat ──► Caddy ──► h5-bridge (:8080) ──► OpenClaw Gateway
    │
    └── SSE stream ◄── h5-bridge（流式推送 delta 事件）
```

## 技术栈

- **框架**: Vue 3 (Composition API)
- **UI 组件库**: Vant 4（移动端）
- **构建工具**: Vite 8
- **富文本**: Marked + Highlight.js（Markdown 渲染 + 代码高亮）
- **样式**: CSS 变量 + 自定义紫色主题

## 项目结构

```
h5-frontend/
├── index.html                   # HTML 入口
├── package.json                 # 依赖配置
├── vite.config.js               # Vite 构建配置（base: /chat/）
├── public/
│   ├── favicon.svg              # 网站图标
│   └── icons.svg                # 图标资源
└── src/
    ├── main.js                  # Vue 应用入口
    ├── App.vue                  # 根组件（路由控制：登录/聊天）
    ├── style.css                # 全局样式
    ├── components/
    │   ├── LoginPage.vue        # 登录页（毛玻璃 + CSS 机器人图标）
    │   ├── ChatPage.vue         # 聊天页（消息列表 + 输入框 + Markdown 渲染）
    │   └── SettingsPopup.vue    # 设置弹窗（用户信息/清空/退出）
    ├── composables/
    │   ├── useAuth.js           # 认证逻辑（登录/Token 管理/自动恢复）
    │   └── useChat.js           # 聊天逻辑（历史加载/SSE 流式/消息管理）
    ├── constants/
    │   └── index.js             # API 路径/常量定义
    ├── utils/
    │   └── format.js            # 文本格式化（Markdown 渲染 + HTML 转义）
    └── assets/                  # 静态资源
```

## 核心功能

### 用户认证

- JWT Bearer Token 认证
- Token 持久化到 `localStorage`，刷新页面自动恢复登录
- 支持登录/注销，Token 过期自动跳转登录页

### 聊天系统

- **SSE 流式接收**: 通过 `fetch` + `ReadableStream` 逐字渲染 AI 回复
- **历史记录**: 自动加载最近 30 条对话，过滤系统消息（NO_REPLY/HEARTBEAT_OK）
- **会话管理**: `/new` 命令开启新会话，上下文自动隔离
- **中止回复**: 支持中断当前生成中的回复

### 富文本渲染

AI 回复支持完整 Markdown 渲染：

- ✅ 代码块语法高亮（Highlight.js）+ 语言标签 + 一键复制
- ✅ 表格、列表（有序/无序）
- ✅ 引用块、标题层级
- ✅ 加粗、斜体、行内代码
- ✅ 链接

用户消息保持纯文本显示（HTML 转义 + 换行）。

### UI 设计

- **配色**: 紫色主调 `#7C3AED`，渐变 `#7C3AED → #A78BFA`
- **字体**: Space Grotesk（标题）+ DM Sans（正文）
- **动效**: 消息入场动画、思考中弹跳点、按钮微交互
- **登录页**: 毛玻璃卡片 + CSS 机器人图标 + 渐变背景
- **聊天页**: 毛玻璃导航栏/输入栏、紫色渐变用户气泡、悬浮效果
- **设置**: 底部弹窗，显示用户信息、Session Key、清空/退出操作

## 开发

```bash
cd /root/h5-frontend
npm install
npm run dev      # 开发模式（自动代理 /api → localhost:8080）
npm run build    # 生产构建（输出到 dist/）
```

## 部署

构建产物部署到 `/var/www/chat/`，由 Caddy 提供服务：

```bash
npm run build
cp -r dist/* /var/www/chat/
```

Vite `base` 配置为 `/chat/`，确保路由正确。

## API 常量

```javascript
API_BASE      = '/api'
API_STATUS    = '/status'
API_LOGIN     = '/login'
API_HISTORY   = '/history'
API_CHAT      = '/chat'
COMMAND_NEW   = '/new'
SESSION_PREFIX = 'agent:main:h5'
TOKEN_KEY     = 'h5-chat-token'
```

## 访问地址

**生产环境**: [https://www.nickhome.cloud/chat](https://www.nickhome.cloud/chat)
