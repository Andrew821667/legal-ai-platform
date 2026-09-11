import { NextRequest } from "next/server";

import { requireLawyer } from "@/lib/lawyer-auth";
import { agreementsCsvFile } from "@/lib/lawyer-export";
import { contentDisposition } from "@/lib/telegram-file";

/**
 * Договоры в CSV — для отчётности, вне Telegram.
 *
 * В Safari это обычная ссылка: файл скачивается с именем и датой. Внутри
 * Telegram скачивание не работает — там тот же файл уходит в чат
 * (соседний маршрут /send).
 */

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const file = await agreementsCsvFile();
  if (file instanceof Response) return file;

  return new Response(file.bytes, {
    headers: {
      "content-type": file.type,
      "content-disposition": contentDisposition(file.name, false),
      "cache-control": "no-store",
    },
  });
}
