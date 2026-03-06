const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";

const CORE_API_READER_KEY =
  process.env.CORE_API_BOT_KEY ||
  process.env.API_KEY_BOT ||
  process.env.API_KEY_NEWS ||
  process.env.CORE_API_ADMIN_KEY ||
  process.env.API_KEY_ADMIN ||
  "";

export type CoreCallResult = {
  response: Response;
  data: any;
};

export function ensureReaderKey(): string | null {
  if (!CORE_API_READER_KEY) {
    return null;
  }
  return CORE_API_READER_KEY;
}

export async function callReaderCore(path: string, init?: RequestInit): Promise<CoreCallResult> {
  const response = await fetch(`${CORE_API_URL}${path}`, {
    ...init,
    headers: {
      "X-API-Key": CORE_API_READER_KEY,
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  const raw = await response.text();
  let data: any = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw ? { detail: raw } : {};
  }

  return { response, data };
}
