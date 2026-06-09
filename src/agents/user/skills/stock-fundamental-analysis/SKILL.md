---
name: stock-fundamental-analysis
description: 个股基本面分析（业务/财务/估值/行业/资金），结合本地知识库（stocks_db）与韭研公社题材数据。
user-invocable: true
metadata:
  trigger: "基本面|基本面分析|公司分析|财务分析|估值分析|个股分析|股票分析|护城河|投资亮点|公司基本面|stock fundamental"
---

# stock-fundamental-analysis

对个股做**基本面分析**，包括业务概况、行业地位、估值水平、资金动向、同行业对比。数据主要来自本地知识库 PostgreSQL `stocks_db`，韭研公社的题材/异动数据作为辅助参考。

## 触发条件

当用户提到以下关键词时触发本 skill：
- 基本面、基本面分析、公司分析、财务分析、估值分析
- 个股分析、股票分析、护城河、投资亮点、公司基本面
- "这只股票怎么样"、"XX公司怎么样"、"帮我分析一下XX"

**不要**在以下情况触发：
- 用户只询问技术面分析（K线、均线等）→ 使用 `stock-chart-analysis` skill
- 用户询问异动/涨停原因 → （韭研公社功能已下线，使用 stock-chart-analysis 看异动）

## 输出语言

全部使用中文输出。

## 执行方式

通过 Python 脚本从 PostgreSQL 知识库获取数据，脚本路径：
```
/home/ubuntu/pilot-agent/src/agents/user/skills/stock-fundamental-analysis/scripts/fetch_fundamental.py
```

### 命令格式

```bash
# 基本面分析（推荐）
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/stock-fundamental-analysis/scripts/fetch_fundamental.py --code 股票代码

# JSON 格式输出（供程序解析）
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/stock-fundamental-analysis/scripts/fetch_fundamental.py --code 股票代码 --json

# 显示完整韭研公社解析文本
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/stock-fundamental-analysis/scripts/fetch_fundamental.py --code 股票代码 --verbose

# 跳过韭研公社数据（仅数据库数据）
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/stock-fundamental-analysis/scripts/fetch_fundamental.py --code 股票代码 --no-jiuyan

# 忽略缓存，强制刷新
python3 /home/ubuntu/pilot-agent/src/agents/user/skills/stock-fundamental-analysis/scripts/fetch_fundamental.py --code 股票代码 --no-cache
```

### 股票代码格式

支持以下格式（脚本会自动标准化）：
- 纯数字：`002471`、`603678`
- 带市场前缀：`sz002471`、`sh603678`
- DB 格式：`002471.SZ`、`603678.SH`

## 数据源

| 优先级 | 数据源 | 状态 | 内容 |
|--------|--------|------|------|
| 1 | PostgreSQL `stocks_db` | 必须 | PE/分位/行业/龙头/公募/北向/描述 |
| 2 | 韭研公社 | 可选 | 题材/概念/异动/催化剂 |

### 韭研公社降级策略

韭研公社需要登录 Cookie 才能获取数据。如果 Cookie 不存在或调用失败：
- 不影响主流程，基本面数据正常输出
- 报告中标注"韭研公社数据未配置（需登录 Cookie）"
- 韭研公社功能已下线

## 输出报告格式

```
## {股票名称}（{股票代码}）基本面分析

### 一、核心结论
[2-3 句话的核心观点]

### 二、公司基本面
- **主营业务**：{description 字段}
- **行业地位**：{is_leader + 龙头说明}
- **行业分类**：{industry_level1 → level2 → level3}

### 三、估值水平
- **PE 中值**：{pe_median}
- **PE 历史分位**：{pe_percentile}%（{>70%: 偏高 | 30-70%: 合理 | <30%: 偏低}）

### 四、资金动向
- **公募持仓**：{fund_holding} 亿元（{fund_change: 增加/减少}）
- **北向持仓**：{northbound_holding} 亿元（{northbound_change: 加仓/减仓}）

### 五、行业地位
[在 industry_level3 同行业中的 PE/分位对比表格]

### 六、韭研公社题材参考（如有）
[最近的题材/概念/异动信息]

### 七、投资亮点与风险
- **亮点**：[最多 3 条]
- **风险**：[最多 3 条]
```

## 使用示例

### 示例1：分析一只股票
用户: "帮我分析一下火炬电子"
→ 执行: `python3 .../fetch_fundamental.py --code 603678`
→ 按模板输出基本面分析报告

### 示例2：查看某公司估值
用户: "鸿远电子估值怎么样？"
→ 执行: `python3 .../fetch_fundamental.py --code 603267`
→ 重点关注 PE 中值和分位数据

### 示例3：了解公司基本面
用户: "中超控股这家公司怎么样？"
→ 执行: `python3 .../fetch_fundamental.py --code 002471 --verbose`
→ 完整的基本面分析 + 韭研公社题材参考

### 示例4：JSON 格式
用户: "获取火炬电子的基本面数据"
→ 执行: `python3 .../fetch_fundamental.py --code 603678 --json`
→ 返回结构化 JSON 数据

## 注意事项

1. 数据主要来自本地 PostgreSQL 知识库，无需外部 API 调用
2. 韭研公社数据为可选辅助，缺失时不影响基本面分析
3. 同一只股票的基本面数据有 1 小时缓存，可用 `--no-cache` 强制刷新
4. PE 分位评价标准：>70% 偏高、30-70% 合理、<30% 偏低
5. 投资亮点与风险由数据自动推导，仅供参考，不构成投资建议
6. 退出码：0 成功、1 股票不存在、2 数据库连接失败
