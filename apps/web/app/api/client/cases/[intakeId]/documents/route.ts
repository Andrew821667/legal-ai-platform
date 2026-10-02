import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientFields, clientKey } from "@/lib/client-ref";
import { clientCorePostForm } from "@/lib/client-core";
import { checkUpload } from "@/lib/client-upload";
import { slidingWindowAllow } from "@/lib/rate-limit";

/**
 * Клиент загружает документ по своему обращению — из кабинета или мини-аппа.
 *
 * Файл хранится у нас, в базе ядра, зашифрованным; юрист открывает его в
 * рабочем месте (карточка клиента, «Файлы»). Раньше файл пересылался юристу
 * в Telegram — а серверы Telegram за рубежом, трансграничной передачи у нас
 * нет. Условия те же, что в чате: обращение клиента и подписанный NDA — их
 * проверяет ядро.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Не больше десяти файлов за десять минут с одного аккаунта.
const recent = new Map<string, number[]>();

export async function POST(request: NextRequest, ctx: { params: Promise<{ intakeId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { intakeId } = await ctx.params;
  if (!UUID.test(intakeId)) return Response.json({ detail: "Обращение не найдено." }, { status: 404 });

  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return Response.json({ detail: "Выберите файл." }, { status: 400 });
  // Пункт списка «юрист просит», в который загружен файл; ядро закроет его.
  const requestId = String(form?.get("request_id") || "");
  if (requestId && !UUID.test(requestId)) return Response.json({ detail: "Пункт запроса не найден." }, { status: 404 });
  const check = checkUpload({ name: file.name, size: file.size });
  if (!check.ok) return Response.json({ detail: check.detail }, { status: 400 });

  const limit = slidingWindowAllow(recent, clientKey(auth), 10, 10 * 60_000);
  if (!limit.allowed) {
    return Response.json({ detail: "Слишком много файлов подряд — подождите несколько минут." }, { status: 429 });
  }

  const upstream = new FormData();
  upstream.set("file", new Blob([await file.arrayBuffer()], { type: file.type || "application/octet-stream" }), check.name);
  for (const [key, value] of Object.entries(clientFields(auth))) upstream.set(key, String(value));
  if (requestId) upstream.set("request_id", requestId);
  return clientCorePostForm(`/api/v1/client-portal/cases/${intakeId}/files`, upstream);
}
