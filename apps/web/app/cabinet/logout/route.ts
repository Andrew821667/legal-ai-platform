import { NextRequest, NextResponse } from "next/server";

import { isTrustedAssistantOrigin, trustedHostsFor } from "@/lib/assistant-security";
import { CLIENT_PROFILE_COOKIE, CLIENT_SESSION_COOKIE } from "@/lib/client-session";
import { publicOrigin } from "@/lib/public-origin";

export const dynamic = "force-dynamic";

/**
 * Только POST — выход не должен срабатывать по обычной GET-ссылке или
 * префетчу. Кнопка на странице — обычная <form method="post">, браузер сам
 * шлёт Origin на такой запрос, поэтому проверка ниже что-то значит.
 */
export async function POST(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);
  if (!isTrustedAssistantOrigin(request.headers.get("origin"), trustedHostsFor(request))) {
    return NextResponse.json({ detail: "Недопустимый источник запроса" }, { status: 403 });
  }

  const response = NextResponse.redirect(new URL("/", origin));
  response.cookies.set(CLIENT_SESSION_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  response.cookies.set(CLIENT_PROFILE_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  return response;
}
