import { NextRequest, NextResponse } from "next/server";

import {
  AssistantPayloadError,
  isTrustedAssistantOrigin,
  normalizeAssistantPayload,
  recordAssistantRequest,
} from "@/lib/assistant-security";
import { resolveLeadClientIp } from "@/lib/lead-security";

const ASSISTANT_API_URL = (process.env.ASSISTANT_API_URL || "http://127.0.0.1:8080").replace(/\/+$/, "");
const ASSISTANT_KEY = (process.env.WEB_ASSISTANT_INTERNAL_KEY || "").trim();

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!ASSISTANT_KEY) {
    return NextResponse.json({ detail: "Ассистент временно недоступен" }, { status: 503 });
  }
  const trustedHosts = [
    request.nextUrl.host,
    request.headers.get("host"),
    request.headers.get("x-forwarded-host"),
    process.env.NEXT_PUBLIC_SITE_URL,
  ].filter((value): value is string => Boolean(value));
  if (!isTrustedAssistantOrigin(request.headers.get("origin"), trustedHosts)) {
    return NextResponse.json({ detail: "Недопустимый источник запроса" }, { status: 403 });
  }
  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > 24_000) {
    return NextResponse.json({ detail: "Запрос слишком большой" }, { status: 413 });
  }

  let payload;
  try {
    payload = normalizeAssistantPayload(await request.json());
  } catch (error) {
    if (error instanceof AssistantPayloadError) {
      return NextResponse.json({ detail: error.message }, { status: error.status });
    }
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const ip = resolveLeadClientIp(request.headers);
  const rate = recordAssistantRequest(ip, payload.sessionId);
  if (!rate.allowed) {
    return NextResponse.json(
      { detail: "Слишком много сообщений. Подождите немного и продолжите диалог." },
      { status: 429, headers: { "Retry-After": String(rate.retryAfter) } },
    );
  }

  try {
    const response = await fetch(`${ASSISTANT_API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Assistant-Key": ASSISTANT_KEY,
      },
      body: JSON.stringify({
        session_id: payload.sessionId,
        messages: payload.messages,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(45_000),
    });

    if (!response.ok) {
      return NextResponse.json(
        { detail: response.status === 504 ? "Ассистент не успел ответить. Повторите сообщение." : "Ассистент временно недоступен" },
        { status: response.status === 429 ? 429 : 502 },
      );
    }
    const data = (await response.json()) as { reply?: unknown };
    const reply = typeof data.reply === "string" ? data.reply.trim().slice(0, 5000) : "";
    if (!reply) {
      return NextResponse.json({ detail: "Ассистент вернул пустой ответ" }, { status: 502 });
    }
    return NextResponse.json({ reply }, { status: 200, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Ассистент временно недоступен" }, { status: 502 });
  }
}
