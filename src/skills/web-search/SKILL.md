---
name: web-search
summary: 搜索网络获取实时信息、新闻和时事（智谱 web_search_prime，返回标题/链接/摘要）
user-invocable: true
priority: medium
category: 搜索
triggers:
  keywords:
    - 搜索
    - 搜一下
    - 查一下
    - web搜索
    - 网络搜索
    - 最新
    - 实时
    - 新闻
    - 今天
    - 近日
    - search
  intents:
    - 查询实时信息或最新新闻
    - 获取训练数据截止后的新事实
    - 验证时效性事实
examples:
  - 搜一下 Python 3.13 有什么新特性
  - 查一下今天北京天气
  - 最近金价走势怎么样
not_for:
  - 离线/本地知识问答（无需联网即可回答）
---

# Web Search

通过智谱 `web_search_prime` MCP 接口搜索网络，返回结构化结果（标题、链接、摘要、日期）。

## 用法

```bash
python3 /home/ubuntu/pilot-agent/src/skills/web-search/scripts/web_search.py "<搜索词>" [选项]
```

### 选项

| 选项 | 取值 | 说明 |
|------|------|------|
| `--content-size` | `medium`(默认) / `high` | 摘要详细度：medium≈400-600字，high≈2500字（更全面但更慢/更贵） |
| `--recency` | `oneDay`/`oneWeek`/`oneMonth`/`oneYear`/`noLimit` | 时间范围过滤，默认不限 |
| `--location` | `cn`(默认) / `us` | 地区：cn=中文区结果，us=非中文区结果 |
| `--domain` | 如 `www.example.com` | 限定返回结果的域名 |

## 示例

```bash
# 基础搜索
python3 /home/ubuntu/pilot-agent/src/skills/web-search/scripts/web_search.py "Python 3.13 新特性"

# 只要最近一周的结果，且要详细摘要
python3 /home/ubuntu/pilot-agent/src/skills/web-search/scripts/web_search.py "OpenAI 最新动态" --recency oneWeek --content-size high

# 搜索英文/海外内容
python3 /home/ubuntu/pilot-agent/src/skills/web-search/scripts/web_search.py "Rust 2024 edition" --location us
```

## 何时使用

- 用户询问**当前事件、最新新闻、实时数据**（天气、股价、汇率、赛果等）
- 需要**训练数据截止日期之后**的新信息
- 验证可能已过时的事实

## 输出格式

每条结果：
```
[序号] 标题
    链接
    摘要内容
    (发布日期，若有)
```

## 环境依赖

- 环境变量 `ZAI_API_KEY`（已在项目 `.env` 中配置，bash 工具会自动继承）
- Python 3.10+ 及 `requests` 库
- 若报 `ZAI_API_KEY 环境变量未设置`，说明服务未加载 `.env`，需重启服务
