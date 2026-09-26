import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientFields, clientKey, clientQuery } from "@/lib/client-ref";
import { clientCoreGet, clientCorePost } from "@/lib/client-core";
import { checkUpload } from "@/lib/client-upload";
import { slidingWindowAllow } from "@/lib/rate-limit";
import { botToken } from "@/lib/lawyer-documents";
import { TelegramFileError, uploadTelegramDocument } from "@/lib/telegram-file";

/**
 * Клиент загружает документ по своему обращению — из кабинета или мини-аппа.
 *
 * Файл уходит юристу в Telegram тем же ботом, что потом открывает его в
 * рабочем месте, и регистрируется в ядре тем же вызовом, что у бота: сам
 * файл живёт в Telegram, в ядре — ссылка на него. Условия те же, что в
 * чате: обращение клиента и подписанный NDA. Проверяются до отправки —
 * чтобы юристу не пришёл файл, который принять нельзя.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Не больше десяти файлов за десять минут с одного аккаунта: чат юриста —
// не место для потока файлов.
const recent = new Map<string, number[]>();

type Summary = {
  client?: { name?: string | null };
  nda?: { signed?: boolean };
  cases?: {
    id: string;
    category?: string | null;
    document_requests?: { request_id: string; title: string; status: string }[];
  }[];
};

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

  const summaryResponse = await clientCoreGet(`/api/v1/client-portal/summary?${clientQuery(auth)}`);
  if (!summaryResponse.ok) return summaryResponse;
  const summary = (await summaryResponse.json().catch(() => ({}))) as Summary;
  const matter = (summary.cases || []).find((item) => item.id === intakeId);
  if (!matter) return Response.json({ detail: "Обращение не найдено." }, { status: 404 });
  const requested = requestId
    ? (matter.document_requests || []).find((item) => item.request_id === requestId && item.status !== "cancelled")
    : undefined;
  if (requestId && !requested) return Response.json({ detail: "Пункт запроса не найден." }, { status: 404 });
  if (!summary.nda?.signed) {
    return Response.json({ detail: "Документы принимаются после подписания NDA." }, { status: 409 });
  }

  const limit = slidingWindowAllow(recent, clientKey(auth), 10, 10 * 60_000);
  if (!limit.allowed) {
    return Response.json({ detail: "Слишком много файлов подряд — подождите несколько минут." }, { status: 429 });
  }

  const token = botToken();
  const lawyerChat = Number(process.env.ADMIN_TELEGRAM_ID || 0);
  if (!token || !lawyerChat) return Response.json({ detail: "Загрузка временно не настроена." }, { status: 503 });

  let sent: Record<string, unknown>;
  try {
    sent = await uploadTelegramDocument(
      token,
      lawyerChat,
      { name: check.name, type: file.type || "application/octet-stream", bytes: new Uint8Array(await file.arrayBuffer()) },
      `Документ от клиента через кабинет: ${summary.client?.name || "клиент"}` +
        (matter.category ? ` · ${matter.category}` : "") +
        (requested ? ` — по запросу «${requested.title}»` : ""),
    );
  } catch (error) {
    const detail = error instanceof TelegramFileError ? error.message : "Не удалось передать файл юристу";
    return Response.json({ detail: `${detail}. Попробуйте ещё раз.` }, { status: 502 });
  }
  const document = (sent.document || {}) as { file_id?: string };
  if (!document.file_id) return Response.json({ detail: "Telegram не вернул файл — попробуйте ещё раз." }, { status: 502 });

  return clientCorePost(`/api/v1/legal-intakes/${intakeId}/documents`, {
    ...clientFields(auth),
    telegram_file_id: document.file_id,
    file_name: check.name,
    file_size: file.size,
    mime_type: file.type || null,
    ...(requestId ? { request_id: requestId } : {}),
  });
}
