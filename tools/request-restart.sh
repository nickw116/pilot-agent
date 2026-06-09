#!/bin/bash
# Request a delayed restart of pilot-agent service.
# Instead of restarting immediately, writes a flag file.
# The agent.ts code will check for this file after each run completes
# and restart the service after saving the response.

FLAG_FILE="/tmp/pilot-agent-restart-requested"
echo "$(date +%s)" > "$FLAG_FILE"
echo "Restart scheduled. Will execute after current task completes."
