import type { AgentEvent } from "@mariozechner/pi-agent-core";
import crypto from "crypto";
import { publish, type SseEvent } from "./sse.js";

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
  return {
    eventId: `evt-${crypto.randomBytes(4).toString("hex")}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    runId,
    sessionKey,
    payload,
  };
}

// Per-sessionKey stream state. Previously these were module-level globals,
// which caused concurrent sessions (and runs) to corrupt each other's
// accumulated text / thinking buffers. Keying by sessionKey isolates each run.
interface StreamState {
  accumulatedText: string;
  accumulatedThinking: string;
  inThinkingBlock: boolean;
  tagBuffer: string;
}

const streamStates = new Map<string, StreamState>();

function getState(sessionKey: string): StreamState {
  let s = streamStates.get(sessionKey);
  if (!s) {
    s = { accumulatedText: "", accumulatedThinking: "", inThinkingBlock: false, tagBuffer: "" };
    streamStates.set(sessionKey, s);
  }
  return s;
}

function resetState(sessionKey: string): void {
  streamStates.set(sessionKey, { accumulatedText: "", accumulatedThinking: "", inThinkingBlock: false, tagBuffer: "" });
}

function translate(
  event: AgentEvent,
  runId: string,
  sessionKey: string
): SseEvent[] {
  switch (event.type) {
    case "agent_start":
      resetState(sessionKey);
      return [sse("run.started", runId, sessionKey)];

    case "message_update": {
      const sub = event.assistantMessageEvent;
      if (sub.type === "text_delta" && sub.delta) {
        return handleTextDelta(sub.delta, runId, sessionKey);
      }
      if (sub.type === "thinking_delta" && sub.delta) {
        getState(sessionKey).accumulatedThinking += sub.delta;
        return [sse("assistant.thinking", runId, sessionKey, { delta: sub.delta })];
      }
      if (sub.type === "toolcall_start") {
        const subAny = sub as any;
        return [
          sse("tool_use", runId, sessionKey, {
            name: subAny.toolName || subAny.partial?.toolCalls?.[0]?.name,
            id: subAny.id || subAny.contentIndex,
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
      const st = getState(sessionKey);
      const flushEvents: SseEvent[] = [];
      if (st.tagBuffer) {
        if (st.inThinkingBlock) {
          st.accumulatedThinking += st.tagBuffer;
          flushEvents.push(sse("assistant.thinking", runId, sessionKey, { delta: st.tagBuffer }));
        } else {
          st.accumulatedText += st.tagBuffer;
          flushEvents.push(sse("assistant.delta", runId, sessionKey, { delta: st.tagBuffer }));
        }
        st.tagBuffer = "";
      }
      const done = sse("run.done", runId, sessionKey);
      if (st.accumulatedText) {
        const result = [
          ...flushEvents,
          sse("full_result", runId, sessionKey, { text: st.accumulatedText }),
          done,
        ];
        resetState(sessionKey);
        return result;
      }
      resetState(sessionKey);
      return [...flushEvents, done];
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

/**
 * Parse <think/> tags from text_delta events.
 * Content inside <think...>...</think(...)> is routed as assistant.thinking,
 * everything else is routed as assistant.delta.
 */
function handleTextDelta(delta: string, runId: string, sessionKey: string): SseEvent[] {
  const st = getState(sessionKey);
  const events: SseEvent[] = [];
  const combined = st.tagBuffer + delta;
  st.tagBuffer = "";
  let text = combined;

  while (text.length > 0) {
    if (st.inThinkingBlock) {
      const closeIdx = text.indexOf("</think");
      if (closeIdx >= 0) {
        const closeEnd = text.indexOf(">", closeIdx);
        if (closeEnd >= 0) {
          const thinkingPart = text.substring(0, closeIdx);
          if (thinkingPart) {
            st.accumulatedThinking += thinkingPart;
            events.push(sse("assistant.thinking", runId, sessionKey, { delta: thinkingPart }));
          }
          st.inThinkingBlock = false;
          text = text.substring(closeEnd + 1);
        } else {
          const thinkingPart = text.substring(0, closeIdx);
          if (thinkingPart) {
            st.accumulatedThinking += thinkingPart;
            events.push(sse("assistant.thinking", runId, sessionKey, { delta: thinkingPart }));
          }
          st.tagBuffer = text.substring(closeIdx);
          text = "";
        }
      } else {
        const partialPos = findPartialTag(text, "</think");
        if (partialPos >= 0) {
          const thinkingPart = text.substring(0, partialPos);
          if (thinkingPart) {
            st.accumulatedThinking += thinkingPart;
            events.push(sse("assistant.thinking", runId, sessionKey, { delta: thinkingPart }));
          }
          st.tagBuffer = text.substring(partialPos);
        } else {
          st.accumulatedThinking += text;
          events.push(sse("assistant.thinking", runId, sessionKey, { delta: text }));
        }
        text = "";
      }
    } else {
      const openIdx = text.indexOf("<think");
      if (openIdx >= 0) {
        const openEnd = text.indexOf(">", openIdx);
        if (openEnd >= 0) {
          const textPart = text.substring(0, openIdx);
          if (textPart) {
            st.accumulatedText += textPart;
            events.push(sse("assistant.delta", runId, sessionKey, { delta: textPart }));
          }
          st.inThinkingBlock = true;
          text = text.substring(openEnd + 1);
        } else {
          const textPart = text.substring(0, openIdx);
          if (textPart) {
            st.accumulatedText += textPart;
            events.push(sse("assistant.delta", runId, sessionKey, { delta: textPart }));
          }
          st.tagBuffer = text.substring(openIdx);
          text = "";
        }
      } else {
        const partialPos = findPartialTag(text, "<think");
        if (partialPos >= 0) {
          const textPart = text.substring(0, partialPos);
          if (textPart) {
            st.accumulatedText += textPart;
            events.push(sse("assistant.delta", runId, sessionKey, { delta: textPart }));
          }
          st.tagBuffer = text.substring(partialPos);
        } else {
          st.accumulatedText += text;
          events.push(sse("assistant.delta", runId, sessionKey, { delta: text }));
        }
        text = "";
      }
    }
  }

  return events;
}

function findPartialTag(text: string, tag: string): number {
  for (let len = Math.min(tag.length - 1, text.length); len >= 1; len--) {
    if (text.endsWith(tag.substring(0, len))) {
      return text.length - len;
    }
  }
  return -1;
}
