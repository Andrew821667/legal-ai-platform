import { NextResponse } from "next/server";

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
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Ядро не ответило вовремя." }, { status: 504 });
  }
}

export const clientCoreGet = (path: string) => call("GET", path);
export const clientCorePost = (path: string, payload: unknown) => call("POST", path, payload);
