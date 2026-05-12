import type { AgentEvent } from "@mariozechner/pi-agent-core";
import { publish, type SseEvent } from "./sse.js";
import { v4 as uuid } from "crypto";

/** Translate Pi AgentEvent → H5 frontend SSE events and publish them. */
export function bridgeAndPublish(
  event: AgentEvent,
  runId: string,
  sessionKey: string
): void {
  const events = translate(event, runId, sessionKey);
  for (const e of events) {
    publish(sessionKey, e);
  }
}

function sse(
  kind: string,
  runId: string,
  sessionKey: string,
  payload: Record<string, unknown> = {}
): SseEvent {
  return { kind, runId, sessionKey, payload };
}

let accumulatedText = "";

function translate(
  event: AgentEvent,
  runId: string,
  sessionKey: string
): SseEvent[] {
  switch (event.type) {
    case "agent_start":
      accumulatedText = "";
      return [sse("run.started", runId, sessionKey)];

    case "message_update": {
      const sub = event.assistantMessageEvent;
      // text delta
      if (sub.type === "text_delta" && sub.delta) {
        accumulatedText += sub.delta;
        return [sse("assistant.delta", runId, sessionKey, { delta: sub.delta })];
      }
      // tool call start
      if (sub.type === "toolcall_start") {
        return [
          sse("tool_use", runId, sessionKey, {
            name: sub.toolCall?.name,
            input: sub.toolCall?.arguments,
          }),
        ];
      }
      return [];
    }

    case "tool_execution_start":
      return [
        sse("command.output", runId, sessionKey, {
          text: `▶ ${event.toolName}(${JSON.stringify(event.args).slice(0, 200)})`,
        }),
      ];

    case "tool_execution_end": {
      const resultText =
        typeof event.result?.content === "string"
          ? event.result.content
          : Array.isArray(event.result?.content)
            ? event.result.content
                .map((c: any) => c.text ?? "")
                .join("")
            : JSON.stringify(event.result);
      return [
        sse("tool_result", runId, sessionKey, {
          name: event.toolName,
          output: String(resultText).slice(0, 2000),
          isError: event.isError,
        }),
      ];
    }

    case "agent_end": {
      const done = sse("run.done", runId, sessionKey);
      if (accumulatedText) {
        return [
          sse("full_result", runId, sessionKey, { text: accumulatedText }),
          done,
        ];
      }
      return [done];
    }

    case "message_start":
    case "message_end":
    case "turn_start":
    case "turn_end":
    case "tool_execution_update":
      return [];

    default:
      return [];
  }
}
