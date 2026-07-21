---
name: 韭研盘前纪要
summary: 抓取韭研公社官方「盘前纪要」当日全文，含板块热点、题材催化、公告、业绩、停复牌
user-invocable: true
priority: medium
category: 财经
triggers:
  keywords:
    - 盘前纪要
    - 韭研公社
    - 今日盘前
    - 盘前资讯
    - 盘前热点
    - 盘前催化
    - 每日财经资讯
    - 早盘前瞻
    - 盘前必读
  intents:
    - 获取今日A股盘前热点板块、题材催化逻辑、重要公告与业绩等财经资讯
    - 查看韭研公社盘前纪要全文并梳理当日盘面要点
examples:
  - 今天盘前有什么消息
  - 帮我看看盘前纪要
  - 今天有什么题材催化
  - 盘前梳理一下
not_for:
  - 盘中/盘后复盘（本 skill 只覆盖开盘前信息）
  - 个股深度基本面分析（用 stock 相关能力）
---

# 韭研盘前纪要

抓取韭研公社（jiuyangongshe.com）官方每日「盘前纪要」全文，无需登录。
通过网页端 SSR（解析 `window.__NUXT__`）获取，并对正文做结构化解析：
板块热点（含个股）、催化事件、相关股票列表等。

盘前纪要典型结构：昨日热点 → 盘前催化题材（含产业链个股）→ 行业要闻 → 公告精选 → 业绩预告 → 停复牌。

## 用法

```bash
python3 main.py -b panqianjiyao -n 1
```

> 必须在 `tools/jiuyan-daily` 目录下运行（脚本是同目录导入）。
> 用 bash 工具时设 `workdir: /home/ubuntu/pilot-agent/tools/jiuyan-daily`。

### 选项

| 选项 | 说明 |
|------|------|
| `-b panqianjiyao` | 抓「盘前纪要」（核心场景） |
| `-b caiwenSixiang` | 抓「财闻私享」（晚间资讯补充） |
| `-b all` | 两个都抓 |
| `-d 2026-06-26` | 指定日期（YYYY-MM-DD）；默认当天 |
| `-n 1` | 取最近 N 篇（默认 1） |

### 示例

```bash
# 今日盘前纪要
python3 main.py -b panqianjiyao -n 1

# 指定日期
python3 main.py -b panqianjiyao -d 2026-06-26

# 财闻私享晚间资讯
python3 main.py -b caiwenSixiang -n 1
```

## 输出

脚本把结构化 JSON 打印到 stdout（日志走 stderr，可忽略）。JSON 字段：

| 字段 | 说明 |
|------|------|
| `title` / `create_time` / `url` | 文章元信息 |
| `sectors` | 昨日热点板块列表，每项 `{sector, stocks[]}` |
| `events` | 盘前催化事件段落，每项 `{number, title, content}` |
| `stocks` | 文章关联的个股 `{name, code}` |
| `full_text` | 清洗后的纯文本全文 |

## 何时使用

- 用户问今天盘前有什么消息 / 利好利空 / 题材催化
- 用户要看盘前纪要 / 财经早报 / 早盘前瞻
- 开盘前需要梳理当日盘面要点

## 汇报要求

抓取成功后，向用户汇报时：
1. 先用 2-3 句话概括当日盘面核心主线（哪些板块/题材在发酵）
2. 再按重要性列举 5-8 条关键信息（题材催化 + 相关个股、重要公告、业绩、停复牌等）
3. 用户需要全文细节时，展示 `full_text` 或 `events`

## 环境依赖

- Python 3.10+ 及 `requests`、`beautifulsoup4`（已安装）

## 维护参考

- 抓取实现：`tools/jiuyan-daily/`（fetcher 走网页 SSR，parser 做结构化解析）
- 备选方案：App 接口 `app.jiuyangongshe.com/jystock-app/api/v2`，鉴权 token=`md5("Uu0KfOB8iUP69d3c:"+毫秒时间戳)`，无需登录
- 若 SSR 解析失效（`__NUXT__` 取不到），可改用 App 接口：`/article/community` 列表 + `/article/detail` 全文
