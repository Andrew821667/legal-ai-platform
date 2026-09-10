import { NextRequest, NextResponse } from "next/server";

import { checkLawyerSessionCookie } from "@/lib/lawyer-access";
import { LAWYER_SESSION_COOKIE, allowedLawyerIds, lawyerSessionSecret } from "@/lib/lawyer-auth";

export const dynamic = "force-dynamic";

/**
 * Автономный вход: ссылку сюда даёт только бот (кнопка в /admin), с токеном,
 * подписанным общим секретом. Дальше — обычная httpOnly-кука: её ставит браузер
 * сам, и дальнейшие запросы к /api/lawyer/* проходят с ней без Telegram.
 */
export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token") || "";

  const result = checkLawyerSessionCookie({
    cookie: token,
    secret: lawyerSessionSecret(),
    allowedIds: allowedLawyerIds(),
  });

  if (!result.ok) {
    return NextResponse.json({ detail: result.detail }, { status: result.status });
  }

  const response = NextResponse.redirect(new URL("/lawyer", request.url));
  response.cookies.set(LAWYER_SESSION_COOKIE, token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    // Сама кука не короче срока, который проверяет сервер на каждый запрос
    // (30 дней по умолчанию) — токен всё равно будет отклонён после этого
    // срока, здесь только чтобы браузер не выбросил куку раньше сервера.
    maxAge: 30 * 24 * 60 * 60,
  });
  return response;
}
