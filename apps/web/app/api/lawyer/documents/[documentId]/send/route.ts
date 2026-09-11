import { NextRequest } from "next/server";

import { requireLawyer } from "@/lib/lawyer-auth";
import { TelegramFileError, sendTelegramDocument } from "@/lib/telegram-file";
import { botToken, documentMeta } from "@/lib/lawyer-documents";

/**
 * Переслать файл клиента в чат юриста с ботом.
 *
 * Внутри Telegram это лучший способ открыть документ: по идентификатору
 * файла бот пересылает его мгновенно, без байтов через нас, и он откроется
 * нативным просмотрщиком. Куда слать — берём из проверенной сессии, а не из
 * запроса: чужому чату файлы клиента не достанутся.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { documentId } = await params;
  if (!UUID.test(documentId)) {
    return Response.json({ detail: "Некорректный идентификатор документа" }, { status: 400 });
  }
  const token = botToken();
  if (!token) {
    return Response.json({ detail: "Сервер не настроен: нет токена бота" }, { status: 500 });
  }

  const meta = await documentMeta(documentId);
  if (meta instanceof Response) return meta;

  try {
    await sendTelegramDocument(
      token,
      auth.telegramUserId,
      meta.telegram_file_id,
      meta.file_name || "Документ клиента",
    );
    return Response.json({ ok: true });
  } catch (err) {
    const detail = err instanceof TelegramFileError ? err.message : "Не удалось переслать файл";
    return Response.json({ detail }, { status: 502 });
  }
}
