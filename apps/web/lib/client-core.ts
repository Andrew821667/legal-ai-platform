import { NextResponse } from "next/server";

import { translateCoreErrorBody } from "./core-errors";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY = process.env.CORE_API_BOT_KEY || process.env.API_KEY_BOT || "";

type Method = "GET" | "POST" | "DELETE";

async function call(method: Method, path: string, payload?: unknown): Promise<NextResponse> {
  if (!CORE_API_BOT_KEY) {
    return NextResponse.json({ detail: "Кабинет временно не настроен." }, { status: 503 });
  }
  try {
    const response = await fetch(`${CORE_API_URL}${path}`, {
      method,
      headers: {
        "X-API-Key": CORE_API_BOT_KEY,
        ...(payload === undefined ? {} : { "content-type": "application/json" }),
      },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const raw = await response.text();
    // Отказы ядра — по-английски; клиенту они нужны по-русски.
    return new NextResponse(response.ok ? raw : translateCoreErrorBody(raw), {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Ядро не ответило вовремя." }, { status: 504 });
  }
}

export const clientCoreGet = (path: string) => call("GET", path);
export const clientCorePost = (path: string, payload: unknown) => call("POST", path, payload);
export const clientCoreDelete = (path: string) => call("DELETE", path);

export type ClientAccountInfo = {
  client_account_id: string;
  email: string;
  telegram_user_id: number | null;
  telegram_username: string | null;
  telegram_linked_at: string | null;
};

/** Учётная запись из ядра — для серверных страниц кабинета; null, если ядро молчит. */
export async function fetchClientAccount(accountId: string): Promise<ClientAccountInfo | null> {
  if (!CORE_API_BOT_KEY) return null;
  try {
    const response = await fetch(`${CORE_API_URL}/api/v1/client-auth/accounts/${encodeURIComponent(accountId)}`, {
      headers: { "X-API-Key": CORE_API_BOT_KEY },
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    return response.ok ? ((await response.json()) as ClientAccountInfo) : null;
  } catch {
    return null;
  }
}

/** Файл из ядра (PDF своего договора) — как есть, с типом и именем от ядра. */
export async function clientCoreGetFile(path: string): Promise<NextResponse> {
  if (!CORE_API_BOT_KEY) {
    return NextResponse.json({ detail: "Кабинет временно не настроен." }, { status: 503 });
  }
  try {
    const response = await fetch(`${CORE_API_URL}${path}`, {
      headers: { "X-API-Key": CORE_API_BOT_KEY },
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) {
      return new NextResponse(translateCoreErrorBody(await response.text()), {
        status: response.status,
        headers: { "content-type": "application/json" },
      });
    }
    return new NextResponse(await response.arrayBuffer(), {
      status: 200,
      headers: {
        "content-type": response.headers.get("content-type") || "application/octet-stream",
        "content-disposition": response.headers.get("content-disposition") || "attachment",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Ядро не ответило вовремя." }, { status: 504 });
  }
}
