import { NextRequest } from "next/server";

import { slidingWindowAllow } from "@/lib/rate-limit";

/**
 * Отчёты браузера о том, что заблокировала политика безопасности (CSP).
 *
 * Политика в боевом режиме: если источник забыли разрешить, часть страницы
 * молча перестанет работать у посетителей. Браузер присылает сюда, что и
 * где заблокировано; строка уходит в журнал сайта. Пишем только директиву,
 * адрес источника и путь страницы — без параметров запроса: в них бывают
 * ключи и токены. Поток ограничен: отчёты шлёт любой браузер.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const recent = new Map<string, number[]>();

function clean(value: unknown): string {
  if (typeof value !== "string" || !value) return "-";
  try {
    const url = new URL(value);
    return `${url.origin}${url.pathname}`.slice(0, 200);
  } catch {
    return value.replace(/[\r\n]/g, " ").slice(0, 100);
  }
}

export async function POST(request: NextRequest) {
  if (Number(request.headers.get("content-length") || "0") > 8_000) return new Response(null, { status: 413 });
  if (!slidingWindowAllow(recent, "csp", 60, 10 * 60_000).allowed) return new Response(null, { status: 204 });
  const body = (await request.json().catch(() => null)) as { "csp-report"?: Record<string, unknown> } | null;
  const report = body?.["csp-report"];
  if (report) {
    console.warn(
      `[csp] blocked ${clean(report["violated-directive"] ?? report["effective-directive"])} ` +
        `source=${clean(report["blocked-uri"])} page=${clean(report["document-uri"])}`,
    );
  }
  return new Response(null, { status: 204 });
}
