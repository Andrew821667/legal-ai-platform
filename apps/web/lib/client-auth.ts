import { NextRequest, NextResponse } from "next/server";

import { trustedHostsFor, isTrustedAssistantOrigin } from "./assistant-security";
import { checkClientSessionCookie } from "./client-access";
import { CLIENT_SESSION_COOKIE, clientSessionSecret } from "./client-session";
import {
  getMiniAppBotTokens,
  TELEGRAM_INIT_DATA_HEADER,
  verifyTelegramWebAppInitDataWithAny,
} from "./telegram-initdata";

export type ClientContext = { telegramUserId: number; via: "initdata" | "cookie" };

/**
 * Два независимых пути входа, тот же принцип, что requireLawyer в
 * lawyer-auth.ts. initData (Mini App внутри Telegram) — основной, строгий
 * путь без послаблений; куку client_session (личный кабинет на сайте, вход
 * через Telegram Login) пробуем, только когда заголовок initData отсутствует
 * целиком. Если заголовок есть, но не прошёл проверку — это не повод молча
 * переключиться на куку, это ошибка, о которой надо сказать прямо: иначе
 * протухший Mini App тихо съезжал бы на куку другого браузера/устройства.
 *
 * В отличие от юриста, здесь нет allowlist — личный кабинет показывает
 * только данные владельца сессии, ядро (core-api) само проверяет владение
 * каждым договором/актом по telegramUserId.
 */
export function requireClient(request: NextRequest): ClientContext | NextResponse {
  const initData = (request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "").trim();
  if (initData) {
    const tokens = getMiniAppBotTokens();
    if (tokens.length === 0) {
      return NextResponse.json(
        { detail: "Откройте кабинет из бота-ассистента." },
        { status: 401 },
      );
    }
    const auth = verifyTelegramWebAppInitDataWithAny(initData, tokens);
    if (!auth) {
      return NextResponse.json(
        { detail: "Сеанс Telegram истёк. Закройте Mini App и откройте его снова из бота." },
        { status: 401 },
      );
    }
    return { telegramUserId: auth.telegramUserId, via: "initdata" };
  }

  const cookieResult = checkClientSessionCookie({
    cookie: request.cookies.get(CLIENT_SESSION_COOKIE)?.value || "",
    secret: clientSessionSecret(),
  });
  if (!cookieResult.ok) {
    return NextResponse.json({ detail: cookieResult.detail }, { status: cookieResult.status });
  }

  // CSRF-подстраховка для cookie-пути: SameSite=Lax уже не отправляет куку на
  // cross-site form-POST, Origin-проверка — второй, независимый от браузера
  // слой (тот же список хостов, что у чата ассистента).
  if (request.method !== "GET" && request.method !== "HEAD") {
    if (!isTrustedAssistantOrigin(request.headers.get("origin"), trustedHostsFor(request))) {
      return NextResponse.json({ detail: "Недопустимый источник запроса" }, { status: 403 });
    }
  }

  return { telegramUserId: cookieResult.telegramUserId, via: "cookie" };
}
