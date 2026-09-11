import { NextRequest } from "next/server";

import { requireLawyer } from "@/lib/lawyer-auth";
import { botToken } from "@/lib/lawyer-documents";
import { agreementsCsvFile } from "@/lib/lawyer-export";
import { TelegramFileError, uploadTelegramDocument } from "@/lib/telegram-file";

/**
 * Договоры в CSV — в чат юриста с ботом.
 *
 * Внутри Telegram файл нельзя скачать, зато можно получить сообщением: он
 * откроется в Excel или Numbers с телефона. Куда слать — из проверенной
 * сессии, а не из запроса: выгрузка со всеми клиентами чужому чату не
 * достанется.
 */

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const token = botToken();
  if (!token) {
    return Response.json({ detail: "Сервер не настроен: нет токена бота" }, { status: 500 });
  }

  const file = await agreementsCsvFile();
  if (file instanceof Response) return file;

  try {
    await uploadTelegramDocument(token, auth.telegramUserId, file, "Договоры практики — выгрузка для отчётности");
    return Response.json({ ok: true });
  } catch (err) {
    const detail = err instanceof TelegramFileError ? err.message : "Не удалось отправить файл";
    return Response.json({ detail }, { status: 502 });
  }
}
