import { NextRequest, NextResponse } from "next/server";

import { sameOriginAllowed, trustedHostsFor } from "./assistant-security";

/**
 * Изменяющий запрос по куке — только со своих страниц.
 *
 * Куки рабочего места юриста и админки SameSite (lax и strict), и браузер не
 * пошлёт их с чужого сайта. Но «чужой» для SameSite — другой домен, а не
 * поддомен: contract.ai-verdict.ru — другое приложение на том же домене, и
 * для браузера он «свой». Проверка Origin закрывает и этот путь, и старые
 * браузеры без SameSite. Запросы с initData (мини-апп в Telegram) несут
 * подпись в заголовке, куки там ни при чём — их не проверяем.
 */
export function rejectForeignOrigin(request: NextRequest): NextResponse | null {
  if (sameOriginAllowed(request.method, request.headers.get("origin"), trustedHostsFor(request))) return null;
  return NextResponse.json({ detail: "Недопустимый источник запроса" }, { status: 403 });
}
