---
name: web-reader
summary: 读取网页正文（智谱 webReader），返回干净的 Markdown/纯文本，支持文档/文章/博客
user-invocable: true
priority: medium
category: 搜索
triggers:
  keywords:
    - 读取网页
    - 读一下这个链接
    - 网页正文
    - 提取正文
    - web-reader
    - 这个网址
    - 这篇文章
    - 总结这篇文章
  intents:
    - 读取并理解给定 URL 的网页内容
    - 提取文章/文档/博客正文（去广告/导航噪声）
    - 配合 web-search 实现「搜索 → 精读」闭环
examples:
  - 读一下 https://example.com 这篇文章说了什么
  - 帮我总结这个网页的内容
not_for:
  - 仅需搜索结果摘要（用 web-search 即可，无需抓全文）
---

# Web Reader

通过智谱 `webReader` MCP 接口抓取并提取网页正文，返回干净的 Markdown。与 `web-search` 配对使用：先搜索找到 URL，再精读全文。

## 用法

```bash
python3 /home/ubuntu/pilot-agent/src/skills/web-reader/scripts/web_reader.py "<URL>" [选项]
```

### 选项

| 选项 | 取值 | 说明 |
|------|------|------|
| `--format` | `markdown`(默认) / `text` | 返回格式 |
| `--no-cache` | 标志 | 禁用缓存，强制重新抓取 |
| `--timeout` | 整数 | 请求超时（秒） |
| `--images-summary` | 标志 | 附上图片清单摘要 |
| `--links-summary` | 标志 | 附上链接清单摘要 |

## 示例

```bash
# 读文档正文
python3 /home/ubuntu/pilot-agent/src/skills/web-reader/scripts/web_reader.py "https://docs.python.org/zh-cn/3/tutorial/"

# 只要纯文本
python3 /home/ubuntu/pilot-agent/src/skills/web-reader/scripts/web_reader.py "https://example.com" --format text

# 强制刷新 + 附链接清单
python3 /home/ubuntu/pilot-agent/src/skills/web-reader/scripts/web_reader.py "https://news.example.com/123" --no-cache --links-summary
```

## 何时使用

- 用户给出 URL 并询问其内容
- 需要读取文章、文档、博客的正文
- 配合 web-search 的结果做深度阅读（搜索只给摘要，这里给全文）

## 与 web-search 的配合

```
用户提问 → web-search 给出候选链接 → web-reader 精读选中的链接 → 综合回答
```

## 环境依赖

- 环境变量 `ZAI_API_KEY`（已在项目 `.env` 中配置，bash 工具会自动继承）
- Python 3.10+ 及 `requests` 库
