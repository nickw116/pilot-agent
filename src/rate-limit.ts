const WINDOW_MS = 60_000;
const MAX_REQUESTS = 20;

const buckets = new Map<number, { tokens: number; lastRefill: number }>();

function refill(bucket: { tokens: number; lastRefill: number }): void {
  const now = Date.now();
  const elapsed = now - bucket.lastRefill;
  if (elapsed >= WINDOW_MS) {
    const periods = Math.floor(elapsed / WINDOW_MS);
    bucket.tokens = Math.min(MAX_REQUESTS, bucket.tokens + periods * MAX_REQUESTS);
    bucket.lastRefill += periods * WINDOW_MS;
  }
}

export function checkRateLimit(userId: number): boolean {
  let bucket = buckets.get(userId);
  if (!bucket) {
    bucket = { tokens: MAX_REQUESTS, lastRefill: Date.now() };
    buckets.set(userId, bucket);
  }
  refill(bucket);
  if (bucket.tokens <= 0) return false;
  bucket.tokens--;
  return true;
}
