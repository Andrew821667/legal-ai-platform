const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";

const CORE_API_READER_KEY =
  process.env.CORE_API_BOT_KEY ||
  process.env.API_KEY_BOT ||
  process.env.API_KEY_NEWS ||
  process.env.CORE_API_ADMIN_KEY ||
  process.env.API_KEY_ADMIN ||
  "";

const CORE_API_FETCH_TIMEOUT_MS = (() => {
  const parsed = Number(process.env.CORE_API_FETCH_TIMEOUT_MS || "7000");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 7000;
  }
  return Math.round(parsed);
})();

const CORE_API_READ_CACHE_TTL_MS = (() => {
  const parsed = Number(process.env.CORE_API_READ_CACHE_TTL_MS || "10000");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 10000;
  }
  return Math.round(parsed);
})();

const CORE_API_READ_CACHE_STALE_MS = (() => {
  const parsed = Number(process.env.CORE_API_READ_CACHE_STALE_MS || "120000");
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 120000;
  }
  return Math.round(parsed);
})();

type ReaderCoreCacheEntry = {
  expiresAt: number;
  staleUntil: number;
  status: number;
  data: any;
};

const READER_CORE_GET_CACHE = new Map<string, ReaderCoreCacheEntry>();

export type CoreCallResult = {
  response: Response;
  data: any;
};

export type CoreCachedCallResult = CoreCallResult & {
  cacheState: "miss" | "hit" | "stale";
};

export function ensureReaderKey(): string | null {
  if (!CORE_API_READER_KEY) {
    return null;
  }
  return CORE_API_READER_KEY;
}

export async function callReaderCore(path: string, init?: RequestInit): Promise<CoreCallResult> {
  const controller = new AbortController();
  const upstreamSignal = init?.signal;
  const onAbort = () => controller.abort();
  if (upstreamSignal) {
    upstreamSignal.addEventListener("abort", onAbort, { once: true });
  }
  const timeoutId = setTimeout(() => controller.abort(), CORE_API_FETCH_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${CORE_API_URL}${path}`, {
      ...init,
      headers: {
        "X-API-Key": CORE_API_READER_KEY,
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (error: any) {
    if (error?.name === "AbortError") {
      throw new Error(`Core API timeout after ${CORE_API_FETCH_TIMEOUT_MS}ms`);
    }
    throw new Error(error?.message || "Core API request failed");
  } finally {
    clearTimeout(timeoutId);
    if (upstreamSignal) {
      upstreamSignal.removeEventListener("abort", onAbort);
    }
  }

  const raw = await response.text();
  let data: any = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw ? { detail: raw } : {};
  }

  return { response, data };
}

function getCachedCoreResult(path: string, allowStale: boolean): CoreCallResult | null {
  const row = READER_CORE_GET_CACHE.get(path);
  if (!row) {
    return null;
  }
  const now = Date.now();
  if (now > row.expiresAt && (!allowStale || now > row.staleUntil)) {
    READER_CORE_GET_CACHE.delete(path);
    return null;
  }
  const response = new Response(JSON.stringify(row.data ?? {}), {
    status: row.status,
    headers: {
      "Content-Type": "application/json",
    },
  });
  return {
    response,
    data: row.data,
  };
}

function setCachedCoreResult(path: string, result: CoreCallResult, ttlMs: number, staleMs: number): void {
  const now = Date.now();
  READER_CORE_GET_CACHE.set(path, {
    expiresAt: now + Math.max(500, ttlMs),
    staleUntil: now + Math.max(500, ttlMs) + Math.max(0, staleMs),
    status: result.response.status,
    data: result.data,
  });
}

export async function callReaderCoreCached(
  path: string,
  init?: RequestInit,
  options?: {
    ttlMs?: number;
    staleMs?: number;
    forceRefresh?: boolean;
  },
): Promise<CoreCachedCallResult> {
  const method = String(init?.method || "GET").toUpperCase();
  if (method !== "GET") {
    const result = await callReaderCore(path, { ...init, method });
    return { ...result, cacheState: "miss" };
  }

  const forceRefresh = Boolean(options?.forceRefresh);
  const ttlMs = Math.max(500, Number(options?.ttlMs ?? CORE_API_READ_CACHE_TTL_MS));
  const staleMs = Math.max(0, Number(options?.staleMs ?? CORE_API_READ_CACHE_STALE_MS));

  if (!forceRefresh) {
    const hit = getCachedCoreResult(path, false);
    if (hit) {
      return { ...hit, cacheState: "hit" };
    }
  }

  try {
    const result = await callReaderCore(path, { ...init, method: "GET" });
    if (result.response.ok) {
      setCachedCoreResult(path, result, ttlMs, staleMs);
    }
    return { ...result, cacheState: "miss" };
  } catch (error) {
    const stale = getCachedCoreResult(path, true);
    if (stale) {
      return { ...stale, cacheState: "stale" };
    }
    throw error;
  }
}
