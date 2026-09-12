import { NextResponse } from "next/server";

/**
 * Обращение к ядру от имени рабочего места.
 *
 * Ключ администратора живёт только здесь, на сервере: в браузер он не попадает
 * никогда. Мини-апп ходит в свои маршруты, а те — в ядро.
 */

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";

const CORE_API_ADMIN_KEY =
  process.env.CORE_API_ADMIN_KEY || process.env.API_KEY_ADMIN || "";

// Ядро на той же машине; если оно не ответило за это время, ответит и не позже.
const TIMEOUT_MS = 15_000;

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function coreCall(method: Method, path: string, payload?: unknown): Promise<NextResponse> {
  if (!CORE_API_ADMIN_KEY) {
    return NextResponse.json(
      { detail: "Сервер не настроен: нет ключа доступа к ядру" },
      { status: 500 },
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${CORE_API_URL}${path}`, {
      method,
      headers: {
        "X-API-Key": CORE_API_ADMIN_KEY,
        ...(payload === undefined ? {} : { "content-type": "application/json" }),
      },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: controller.signal,
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch (error) {
    // Отличаем обрыв по времени от прочих сбоев: юристу полезно понимать,
    // ядро молчит или упало.
    const timedOut = error instanceof Error && error.name === "AbortError";
    return NextResponse.json(
      { detail: timedOut ? "Ядро не ответило вовремя" : "Не удалось обратиться к ядру" },
      { status: 504 },
    );
  } finally {
    clearTimeout(timer);
  }
}

export function coreGet(path: string): Promise<NextResponse> {
  return coreCall("GET", path);
}

export function corePost(path: string, payload?: unknown): Promise<NextResponse> {
  return coreCall("POST", path, payload);
}

export function corePatch(path: string, payload: unknown): Promise<NextResponse> {
  return coreCall("PATCH", path, payload);
}

export function coreDelete(path: string): Promise<NextResponse> {
  return coreCall("DELETE", path);
}
