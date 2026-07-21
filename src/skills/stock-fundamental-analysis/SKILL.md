---
name: stock-fundamental-analysis
summary: A股个股基本面分析（业务/财务/估值/行业/资金），数据来自 stocks_db
user-invocable: true
priority: high
category: finance
triggers:
  keywords:
    - 基本面
    - 公司分析
    - 财务分析
    - 估值分析
    - 护城河
    - 投资亮点
    - 公司基本面
  intents:
    - 系统分析一只 A 股的基本面
    - 评估公司的业务、估值、行业地位
not_for:
  - 仅技术面（K线/均线/缠论） → 用 stock-chart-analysis
  - 仅查财务报表数据 → 用 gs-stock-financial-query
examples:
  - 这只股票的基本面怎么样
  - 帮我分析一下宁德时代
metadata: {}
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

> ⛔ **硬性禁令（违反将导致"数据库密码错误"等故障）**
> 1. **必须且只能**通过下方 Python 脚本获取数据。**严禁**自己执行 `psql`、`pg_isready`、`PGPASSWORD=... psql ...` 等任何直连数据库的命令。
> 2. **严禁编造、猜测数据库账号/密码/库名**。脚本内部已内置正确的连接凭据（`pilot` / `pilot123` / `stocks_db`）。除此之外的任何账号（尤其是 `postgres` 超级用户、`ubuntu`、`root`）**都不得使用** —— `postgres` 角色未设密码，任何密码都会触发 `password authentication failed for user "postgres"`。
> 3. **严禁手写 SQL 查询**（包括 `SELECT`、`\d`、`information_schema` 等）。表结构、列名、字段类型一律以脚本输出为准，**不要猜测**。已知易错点：
>    - 列名是 `stock_code` / `stock_name`，**不是** `code` / `name`
>    - `is_leader` 是 **文本**（如 `"是"`），**不能**用 `is_leader::int` 或 `~* '^[1-5]$'` 转换
>    - `pe_median` / `pe_percentile` 字段失真，按 CLAUDE.md 规则用 `check_pe_quality.py` 取实时 TTM PE
> 4. 如果脚本返回错误（退出码 2 = 连接失败），**不要**尝试改用其他账号绕过，应直接把脚本 stderr 原样反馈给用户。

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

### 数据库表结构参考（仅供理解，不得据此手写 SQL）

> ⚠️ 此表仅供理解脚本输出含义。**严禁**基于此表自行编写 `psql` 查询；所有访问必须经 `fetch_fundamental.py`。

`stocks` 表（`stocks_db`）：

| 列名 | 类型 | 说明 |
|------|------|------|
| `stock_code` | varchar(20) | 股票代码（如 `002471.SZ`），**注意不是 `code`** |
| `stock_name` | varchar(50) | 股票名称，**注意不是 `name`** |
| `industry_level1/2/3` | varchar(50) | 行业分类（一/二/三级） |
| `is_leader` | varchar(10) | 是否龙头，**文本**（值为 `"是"` 等），**不可强转 int** |
| `description` | text | 主营业务描述 |
| `fund_holding` / `fund_change` | real | 公募持仓/变动 |
| `northbound_holding` / `northbound_change` | real | 北向持仓/变动 |
| `pe_median` / `pe_percentile` | real | **历史统计量，已失真，禁止使用**，改用 `check_pe_quality.py` |

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

---

### 📌 数据来源
- 行业/资金/描述/同行业对比：本地知识库 stocks_db（PostgreSQL）
- PE 估值（TTM，近五年分位）：AKShare 百度股市通（check_pe_quality.py 实时查询）
- 题材/异动（如有）：韭研公社
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

1. **【最高优先级】数据获取的唯一入口是 `fetch_fundamental.py` 脚本**。严禁自行执行 `psql`、严禁手写 SQL、严禁编造数据库账号。违反此规则必然导致认证失败或 SQL 语法错误。
2. **正确的数据库凭据仅有一组**：`pilot` / `pilot123` / `stocks_db` / `localhost:5432`，且已封装在脚本内，agent 无需也**不得**在命令行中传递任何密码。`postgres`、`ubuntu`、`root` 等账号一律禁用。
3. 数据主要来自本地 PostgreSQL 知识库，无需外部 API 调用
4. 韭研公社数据为可选辅助，缺失时不影响基本面分析
5. 同一只股票的基本面数据有 1 小时缓存，可用 `--no-cache` 强制刷新
6. **PE 数据规则**：本地 `pe_median`/`pe_percentile` 字段为历史统计量且存在失真，**禁止**直接引用。涉及当前 PE/分位时，必须追加执行实时查询脚本：
   ```bash
   python3 /home/ubuntu/pilot-agent/user_addons/check_pe_quality.py <股票代码>
   ```
   以百度股市通 TTM PE（近五年分位）为准。
7. PE 分位评价标准：>70% 偏高、30-70% 合理、<30% 偏低
8. 投资亮点与风险由数据自动推导，仅供参考，不构成投资建议
9. 退出码：0 成功、1 股票不存在、2 数据库连接失败（**此时不要换账号绕过，直接反馈 stderr**）
