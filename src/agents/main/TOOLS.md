# TOOLS.md

## 工具使用备注
- `delegate`: 将任务委派给专业子 agent（dev、user）。遇到专业性问题必须使用。
- `read`: 读取文件或列出目录内容（只读）。
- `bash`: 执行 shell 命令（仅用于查询）。
- `skill`: 加载 skill 的完整知识。
- `memory_save`: 保存重要信息到持久记忆。
- `memory_search`: 搜索记忆中的相关信息。

## 约束
你没有 `write` 和 `edit` 工具。任何需要创建或修改文件的任务，必须委派给 `dev` agent。
