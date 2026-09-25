import { NextResponse } from "next/server";

import { translateCoreErrorBody } from "./core-errors";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY = process.env.CORE_API_BOT_KEY || process.env.API_KEY_BOT || "";

type Method = "GET" | "POST";

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
