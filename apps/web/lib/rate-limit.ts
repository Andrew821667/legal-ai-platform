/**
 * Общий sliding-window лимитер поверх Map<key, timestamps[]> — вынесен из
 * assistant-security.ts (recordAssistantRequest), чтобы не копировать ту же
 * логику для /cabinet/login. Раздельные check/commit, а не одна функция —
 * потому что assistant-security проверяет два независимых лимита (IP и
 * session) и обязана либо засчитать попытку в оба сразу, либо не засчитывать
 * ни в один (иначе отказ по session-лимиту тихо расходовал бы IP-лимит).
 */

export type RateWindowResult = { allowed: boolean; retryAfter: number };
export type RateWindowCheck = { allowed: boolean; rows: number[] };

function prune(store: Map<string, number[]>, key: string, now: number, windowMs: number): number[] {
  const rows = (store.get(key) || []).filter((ts) => now - ts <= windowMs);
  if (rows.length) {
    store.set(key, rows);
  } else {
    store.delete(key);
  }
  return rows;
}

/** Проверяет лимит, не фиксируя попытку — вызывающая сторона решает, коммитить ли. */
export function checkSlidingWindow(
  store: Map<string, number[]>,
  key: string,
  limit: number,
  windowMs: number,
  now: number = Date.now(),
): RateWindowCheck {
  const rows = prune(store, key, now, windowMs);
  return { allowed: rows.length < limit, rows };
}

/** Фиксирует попытку в момент now поверх rows, ранее полученных из checkSlidingWindow. */
export function commitSlidingWindowHit(
  store: Map<string, number[]>,
  key: string,
  rows: number[],
  now: number,
): void {
  rows.push(now);
  store.set(key, rows);
}

function retryAfterSeconds(rows: number[], now: number, windowMs: number): number {
  const oldest = rows[0] ?? now;
  return Math.max(1, Math.ceil((oldest + windowMs - now) / 1000));
}

/** Однолимитный частый случай: проверяет И, если разрешено, сразу фиксирует попытку. */
export function slidingWindowAllow(
  store: Map<string, number[]>,
  key: string,
  limit: number,
  windowMs: number,
  now: number = Date.now(),
): RateWindowResult {
  const { allowed, rows } = checkSlidingWindow(store, key, limit, windowMs, now);
  if (!allowed) {
    return { allowed: false, retryAfter: retryAfterSeconds(rows, now, windowMs) };
  }
  commitSlidingWindowHit(store, key, rows, now);
  return { allowed: true, retryAfter: 0 };
}

export { retryAfterSeconds };
