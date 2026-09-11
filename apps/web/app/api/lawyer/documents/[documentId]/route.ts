import { NextRequest } from "next/server";

import { botToken, documentMeta } from "@/lib/lawyer-documents";
import { requireLawyer } from "@/lib/lawyer-auth";
import {
  MAX_FILE_BYTES,
  TelegramFileError,
  contentDisposition,
  getTelegramFilePath,
  showsInline,
  telegramFileUrl,
} from "@/lib/telegram-file";

/**
 * Файл, который клиент прислал боту, — потоком в браузер.
 *
 * Для входа из Safari: там кука, и обычная ссылка открывает PDF во вкладке.
 * Внутри Telegram этот путь не нужен — файл пересылается в чат (см. /send).
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
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
  if (meta.file_size && meta.file_size > MAX_FILE_BYTES) {
    return Response.json({ detail: "Файл больше 20 МБ — откройте его в Telegram" }, { status: 413 });
  }

  try {
    const path = await getTelegramFilePath(token, meta.telegram_file_id);
    const file = await fetch(telegramFileUrl(token, path), { cache: "no-store" });
    if (!file.ok || !file.body) {
      return Response.json({ detail: "Файл недоступен в Telegram" }, { status: 502 });
    }
    const type = meta.mime_type || file.headers.get("content-type") || "application/octet-stream";
    return new Response(file.body, {
      headers: {
        "content-type": type,
        "content-disposition": contentDisposition(meta.file_name, showsInline(meta.mime_type)),
        "cache-control": "private, no-store",
        ...(file.headers.get("content-length")
          ? { "content-length": file.headers.get("content-length") as string }
          : {}),
      },
    });
  } catch (err) {
    const detail = err instanceof TelegramFileError ? err.message : "Не удалось получить файл";
    return Response.json({ detail }, { status: 502 });
  }
}
