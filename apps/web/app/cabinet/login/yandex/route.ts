import { NextRequest, NextResponse } from "next/server";

import { safeNextPath } from "@/lib/cabinet-redirect";
import {
  CLIENT_OAUTH_COOKIE,
  CLIENT_OAUTH_MAX_AGE_SECONDS,
  clientCookieOptions,
  clientSessionSecret,
} from "@/lib/client-session";
import { resolveLeadClientIp } from "@/lib/lead-security";
import { publicOrigin } from "@/lib/public-origin";
import { slidingWindowAllow } from "@/lib/rate-limit";
import { sealCookieValue } from "@/lib/signed-cookie";
import { createPkce, randomToken } from "@/lib/telegram-login-oidc";
import { buildYandexAuthorizeUrl, yandexConfig } from "@/lib/yandex-oauth";

/**
 * Начало входа через Яндекс ID (lib/yandex-oauth.ts): state и PKCE — в
 * подписанную одноразовую куку, клиента — на oauth.yandex.ru.
 */

export const dynamic = "force-dynamic";

const loginAttempts = new Map<string, number[]>();

export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);
  const config = yandexConfig(process.env, origin);
  const cookieSecret = clientSessionSecret();
  if (!config || !cookieSecret) {
    return NextResponse.redirect(new URL("/cabinet?login=misconfigured", origin));
  }
  const rate = slidingWindowAllow(loginAttempts, resolveLeadClientIp(request.headers), 10, 600_000);
  if (!rate.allowed) {
    return NextResponse.redirect(new URL("/cabinet?login=ratelimit", origin));
  }
  const state = randomToken();
  const { verifier, challenge } = createPkce();
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));
  const response = NextResponse.redirect(
    buildYandexAuthorizeUrl({ clientId: config.clientId, redirectUri: config.redirectUri, state, codeChallenge: challenge }),
  );
  response.cookies.set(
    CLIENT_OAUTH_COOKIE,
    sealCookieValue({ provider: "yandex", state, verifier, next }, cookieSecret),
    clientCookieOptions(CLIENT_OAUTH_MAX_AGE_SECONDS, "/cabinet"),
  );
  return response;
}
