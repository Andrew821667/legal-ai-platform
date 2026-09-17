import { NextRequest, NextResponse } from "next/server";

import { resolveLeadClientIp } from "@/lib/lead-security";
import { slidingWindowAllow } from "@/lib/rate-limit";
import { safeNextPath } from "@/lib/cabinet-redirect";
import {
  CLIENT_OAUTH_COOKIE,
  CLIENT_OAUTH_MAX_AGE_SECONDS,
  clientCookieOptions,
  clientSessionSecret,
} from "@/lib/client-session";
import { publicOrigin } from "@/lib/public-origin";
import { sealCookieValue } from "@/lib/signed-cookie";
import { buildAuthorizationUrl, createPkce, randomToken } from "@/lib/telegram-login-oidc";
import { telegramLoginMode } from "@/lib/telegram-login-mode";

export const dynamic = "force-dynamic";

function positiveInt(raw: string | undefined, fallback: number): number {
  const value = Number(raw || "");
  return Number.isFinite(value) && value > 0 ? Math.round(value) : fallback;
}

// Свой Map, отдельный от лимитов чата ассистента — разная семантика запроса
// и разные лимиты по умолчанию (вход дороже для атакующего перебирать смысла
// нет, но неограниченный редирект на внешний oauth-эндпоинт — тоже риск).
const loginAttempts = new Map<string, number[]>();

/**
 * Инициация входа: генерируем state/nonce/PKCE, откладываем их в подписанную
 * короткоживущую куку и редиректим на Telegram. Ничего не проверяем на
 * стороне Telegram здесь — вся проверка на обратном пути, в /cabinet/callback.
 */
export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);

  if (telegramLoginMode() !== "oidc") {
    return NextResponse.redirect(new URL("/cabinet", origin));
  }

  const clientId = (process.env.TELEGRAM_OAUTH_CLIENT_ID || "").trim();
  const clientSecret = (process.env.TELEGRAM_OAUTH_CLIENT_SECRET || "").trim();
  const cookieSecret = clientSessionSecret();
  if (!clientId || !clientSecret || !cookieSecret) {
    return NextResponse.redirect(new URL("/cabinet?login=misconfigured", origin));
  }

  const ip = resolveLeadClientIp(request.headers);
  const limit = positiveInt(process.env.CLIENT_LOGIN_IP_MAX_REQUESTS, 10);
  const windowSeconds = positiveInt(process.env.CLIENT_LOGIN_WINDOW_SECONDS, 600);
  const rate = slidingWindowAllow(loginAttempts, ip, limit, windowSeconds * 1000);
  if (!rate.allowed) {
    return NextResponse.redirect(new URL("/cabinet?login=ratelimit", origin));
  }

  const redirectUri =
    (process.env.TELEGRAM_OAUTH_REDIRECT_URI || "").trim() || `${origin}/cabinet/callback`;
  const scope = (process.env.TELEGRAM_OAUTH_SCOPE || "").trim() || "openid profile phone";

  const state = randomToken();
  const nonce = randomToken();
  const { verifier, challenge } = createPkce();
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));

  const authorizationUrl = buildAuthorizationUrl({
    clientId,
    redirectUri,
    scope,
    state,
    nonce,
    codeChallenge: challenge,
  });

  const response = NextResponse.redirect(authorizationUrl);
  response.cookies.set(
    CLIENT_OAUTH_COOKIE,
    sealCookieValue({ state, nonce, verifier, next }, cookieSecret),
    clientCookieOptions(CLIENT_OAUTH_MAX_AGE_SECONDS, "/cabinet"),
  );
  return response;
}
