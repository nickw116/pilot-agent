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

function nextEventId(sessionKey: string): string {
  const seq = (eventSeqs.get(sessionKey) ?? 0) + 1;
  eventSeqs.set(sessionKey, seq);
  return `evt-${seq.toString(16).padStart(6, "0")}`;
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
  if (!event.source) event.source = "main";

  const data = JSON.stringify(event);
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
