---
name: pre-market-briefing
description: 盘前纪要信息源，提供盘前市场分析、重要新闻、政策动向、机构观点等。数据来源：盘前纪要信息源。
user-invocable: true
metadata:
  trigger: "盘前|盘前纪要|盘前分析|盘前新闻|盘前市场|盘前资讯|盘前播报|盘前简报|盘前要点"
---

# 盘前纪要

查询**盘前市场分析、重要新闻、政策动向、机构观点**。数据来自盘前纪要信息源。

## 触发条件

当用户提到以下关键词时触发本 skill：
- 盘前、盘前纪要、盘前分析、盘前新闻
- 盘前市场、盘前资讯、盘前播报、盘前简报
- 盘前要点、盘前总结、盘前回顾
- 今日盘前、明天盘前、开盘前

**不要**在用户只询问技术面分析（K线、均线等）时触发，那种情况使用 `stock-chart-analysis` skill。

## 输出语言

全部使用中文输出。

## 执行方式

通过 Python 脚本从盘前纪要信息源抓取数据，脚本路径：
```
/home/ubuntu/pilot-agent/src/agents/user/skills/pre-market-briefing/scripts/fetch_briefing.py
```

### 命令格式

```bash
# 查询今日盘前纪要（推荐）
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/pre-market-briefing/scripts/fetch_briefing.py --date YYYY-MM-DD

# 按关键词搜索盘前纪要
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/pre-market-briefing/scripts/fetch_briefing.py --date YYYY-MM-DD --keyword 关键词

# 查看盘前纪要摘要
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/pre-market-briefing/scripts/fetch_briefing.py --date YYYY-MM-DD --summary

# 查看完整盘前纪要文本
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/pre-market-briefing/scripts/fetch_briefing.py --date YYYY-MM-DD --verbose

# JSON 格式输出（供程序解析）
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/pre-market-briefing/scripts/fetch_briefing.py --date YYYY-MM-DD --json
```

### 日期说明

- 日期格式：`YYYY-MM-DD`，如 `2025-05-16`
- 如果用户没指定日期，默认使用**今天**的日期
- 如果指定日期是非交易日或数据未更新，脚本会自动向前查找最近的交易日（最多回退 5 天）
- 盘前数据通常在当日 08:30 前更新

### 关键词搜索

支持以下关键词搜索：
- 政策类：政策、监管、央行、财政、产业政策
- 新闻类：新闻、公告、财报、业绩、并购
- 机构类：机构、券商、研报、评级、目标价
- 市场类：大盘、指数、板块、概念、热点

## 输出报告格式

查询到数据后，按照以下模板输出报告：

```
## {日期} 盘前纪要

### 市场概览
- **主要指数**：{指数表现}
- **市场情绪**：{情绪描述}
- **资金流向**：{资金情况}

### 重要新闻
{新闻列表，包括标题、来源、摘要}

### 政策动向
{政策信息，包括政策名称、发布机构、影响分析}

### 机构观点
{机构观点，包括机构名称、观点摘要、目标价}

### 热点板块
{热点板块，包括板块名称、催化剂、相关个股}

### 风险提示
{风险因素，包括市场风险、政策风险、个股风险}
```

## 使用示例

### 示例1：查询今日盘前纪要
用户: "今天盘前有什么重要信息？"
→ 执行: `python3 .../fetch_briefing.py --date 2025-05-16 --summary`
→ 按模板输出报告

### 示例2：搜索特定关键词
用户: "盘前有关于新能源汽车的新闻吗？"
→ 执行: `python3 .../fetch_briefing.py --date 2025-05-16 --keyword 新能源汽车`
→ 列出所有匹配的盘前纪要内容

### 示例3：查看完整盘前纪要
用户: "给我看完整的盘前纪要"
→ 执行: `python3 .../fetch_briefing.py --date 2025-05-16 --verbose`
→ 展示完整盘前纪要文本

## 注意事项

1. 数据来源为盘前纪要信息源，信息及时但可能有发布延迟
2. 非交易日或数据未更新时，脚本会自动回退到最近的交易日
3. 不要频繁请求，保持合理的请求频率
4. 如果查不到数据，提示用户可能是非交易日或数据尚未更新
5. 盘前纪要中的政策信息和机构观点仅供参考，不构成投资建议
6. **重要**：盘前纪要数据可能需要登录API。如果脚本返回"需要登录"的错误，需要提供Cookie：
   - 首次使用：`python3 .../fetch_briefing.py --cookie "session=xxx;..." --save-cookie`
   - 后续使用Cookie会自动从文件加载，无需每次指定

## 与其他 Skill 的关系

- **stock-anomaly-analysis（已下线）：盘前纪要提供盘前市场概览和新闻
- **stock-chart-analysis**：盘前纪要提供基本面和政策信息，技术分析提供K线和均线分析
- **gs-stock-market-query**：盘前纪要提供市场情绪和机构观点，行情查询提供实时行情数据

## 数据更新时间

- 盘前数据：通常在当日 08:30 前更新
- 盘中数据：实时更新
- 盘后数据：通常在当日 15:30 后完整

## 技术支持

如果遇到技术问题，请检查：
1. Python 版本是否为 3.6+
2. 依赖包是否安装：`pip install requests`
3. 网络连接是否正常
4. Cookie 是否有效（如需要登录）
