#!/bin/bash
# PreToolUse hook for Claude Code to intercept self-restart commands.
# Blocks 'systemctl restart pilot-agent' and schedules a delayed restart instead.
# Reads tool input from stdin, exits 0 to allow, exits 2 to block.

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

if [ "$TOOL_NAME" = "Bash" ]; then
  if echo "$COMMAND" | grep -qiE 'systemctl\s+(restart|stop)\s+pilot-agent'; then
    bash /home/ubuntu/pilot-agent/tools/request-restart.sh
    echo "BLOCKED: 重启 pilot-agent 服务已安排在当前任务完成后执行。请继续完成当前任务。" >&2
    exit 2
  fi
fi

exit 0
