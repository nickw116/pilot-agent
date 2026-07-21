import type { ServerResponse } from "http";

export interface SseEvent {
  eventId: string;
  kind: string;
  runId?: string;
  sessionKey?: string;
  source?: string;
  payload?: unknown;
}

// sessionKey → Map<subscriberId, res>
const subscribers = new Map<string, Map<string, ServerResponse>>();
const eventSeqs = new Map<string, number>();

// ── Event buffer for replay on reconnect ──
const BUFFER_MAX = 200;
const buffer = new Map<string, { eventId: string; data: string }[]>();

function nextEventId(sessionKey: string): string {
  const seq = (eventSeqs.get(sessionKey) ?? 0) + 1;
  eventSeqs.set(sessionKey, seq);
  return `evt-${seq.toString(16).padStart(6, "0")}`;
}

function appendBuffer(sessionKey: string, eventId: string, data: string): void {
  let buf = buffer.get(sessionKey);
  if (!buf) {
    buf = [];
    buffer.set(sessionKey, buf);
  }
  buf.push({ eventId, data });
  if (buf.length > BUFFER_MAX) {
    buf.splice(0, buf.length - BUFFER_MAX);
  }
}

export function replayBuffer(sessionKey: string, lastEventId: string | null): string[] {
  const buf = buffer.get(sessionKey);
  if (!buf || !lastEventId) return [];
  const idx = buf.findIndex((e) => e.eventId === lastEventId);
  if (idx < 0) return [];
  return buf.slice(idx + 1).map((e) => e.data);
}

export function clearBuffer(sessionKey: string): void {
  buffer.delete(sessionKey);
}

export function registerSubscriber(
  sessionKey: string,
  subscriberId: string,
  res: ServerResponse
): void {
  if (!subscribers.has(sessionKey)) {
    subscribers.set(sessionKey, new Map());
  }
  subscribers.get(sessionKey)!.set(subscriberId, res);
}

export function unregisterSubscriber(
  sessionKey: string,
  subscriberId: string
): void {
  subscribers.get(sessionKey)?.delete(subscriberId);
}

export function publish(sessionKey: string, event: SseEvent): void {
  if (!event.eventId) event.eventId = nextEventId(sessionKey);
  if (!event.sessionKey) event.sessionKey = sessionKey;
  if (!event.source) event.source = "user";

  const data = JSON.stringify(event);

  appendBuffer(sessionKey, event.eventId, data);

  const subs = subscribers.get(sessionKey);
  if (!subs) return;

  for (const [id, res] of subs) {
    try {
      res.write(`data: ${data}\n\n`);
    } catch {
      subs.delete(id);
    }
  }
}
