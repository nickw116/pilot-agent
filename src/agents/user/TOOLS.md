# TOOLS.md

## 工具使用备注
- `read`: 读取文件内容、列出目录，分析数据。
- `write`: 创建/覆盖文件（产出报告、文档、脚本等）。
- `edit`: 精确替换文件中的文本（修改前先 read）。
- `bash`: 执行 shell 命令、运行分析脚本（查询、数据处理等）。
- `skill`: 加载专业知识模块（你的私有 skills 见下方）。
- `memory_save` / `memory_search`: 跨会话记忆。

## 私有 Skills

### 搜索与联网
- **web-search** (`web-search`): 搜索网络获取实时信息、新闻、时事（智谱 web_search_prime，返回标题/链接/摘要）。涉及训练截止后的新事实、时事、实时数据时必须使用。
- **web-reader** (`web-reader`): 读取网页正文（智谱 webReader），返回干净的 Markdown。配合 web-search 做「搜索→精读」闭环。

### 证券分析
- **stock-chart-analysis** (`stock-chart-analysis`): K线技术分析，均线、缠论、筹码分布、头肩底形态
- **gs-stock-market-query** (`gs-stock-market-query`): 行情数据、行业板块、ETF、涨跌排名
- **gs-stock-financial-query** (`gs-stock-financial-query`): 港股/美股财务报表查询
- **gs-smart-stock-picking** (`gs-smart-stock-picking`): 多条件选股筛选
- **gs-economy-query** (`gs-economy-query`): 宏观经济数据
- **gs-etf-filter** (`gs-etf-filter`): ETF 筛选
- **gs-fund-compare** (`gs-fund-compare`): 基金对比
- **westockdata** (`westockdata`): 股票数据
- **five-elements-analysis** (`five-elements-analysis`): 五行行业轮动分析，基于天干地支/月令五行预测行业板块轮动
