import { timingSafeEqual } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import {
  CLIENT_ACCOUNT_COOKIE,
  CLIENT_OAUTH_COOKIE,
  CLIENT_OAUTH_MAX_AGE_SECONDS,
  CLIENT_SESSION_MAX_AGE_SECONDS,
  clientCookieOptions,
  clientSessionSecret,
  sealClientAccount,
} from "@/lib/client-session";
import { publicOrigin } from "@/lib/public-origin";
import { openCookieValue } from "@/lib/signed-cookie";
import { exchangeYandexCode, fetchYandexProfile, yandexConfig, YandexOauthError } from "@/lib/yandex-oauth";

/**
 * Возврат с oauth.yandex.ru: сверить state, обменять код на токен (на
 * сервере), взять из Яндекса id и подтверждённую почту, найти или завести
 * учётную запись в ядре и выдать сессию кабинета (кука client_account).
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY = process.env.CORE_API_BOT_KEY || process.env.API_KEY_BOT || "";

type OauthCookie = { provider?: string; state: string; verifier: string; next: string };

function denyTo(origin: string, reason: string): NextResponse {
  const response = NextResponse.redirect(new URL(`/cabinet?login=${reason}`, origin));
  // Кука обмена одноразовая: неудачная попытка не оставляет её для повтора.
  response.cookies.set(CLIENT_OAUTH_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/cabinet", maxAge: 0 });
  return response;
}

function sameState(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);
  const params = request.nextUrl.searchParams;
  if (params.get("error")) return denyTo(origin, "denied");
  const code = params.get("code") || "";
  const state = params.get("state") || "";
  if (!code || !state) return denyTo(origin, "state");

  const cookieSecret = clientSessionSecret();
  const config = yandexConfig(process.env, origin);
  if (!cookieSecret || !config || !CORE_API_BOT_KEY) return denyTo(origin, "misconfigured");

  const oauth = openCookieValue<OauthCookie>(
    request.cookies.get(CLIENT_OAUTH_COOKIE)?.value || "",
    cookieSecret,
    CLIENT_OAUTH_MAX_AGE_SECONDS,
  );
  if (!oauth || oauth.provider !== "yandex" || !sameState(oauth.state, state)) return denyTo(origin, "state");

  let profile;
  try {
    const token = await exchangeYandexCode({ code, codeVerifier: oauth.verifier, config });
    profile = await fetchYandexProfile(token, config.clientId);
  } catch (error) {
    const reason = error instanceof YandexOauthError ? error.reason : "exchange";
    // eslint-disable-next-line no-console
    console.error("Yandex OAuth:", reason, (error as Error).message);
    return denyTo(origin, reason === "email" ? "email" : reason === "profile" ? "profile" : "exchange");
  }

  let account: { client_account_id?: string; email?: string; display_name?: string | null };
  try {
    const response = await fetch(`${CORE_API_URL}/api/v1/client-auth/yandex`, {
      method: "POST",
      headers: { "X-API-Key": CORE_API_BOT_KEY, "content-type": "application/json" },
      body: JSON.stringify({ yandex_id: profile.yandexId, email: profile.email, display_name: profile.displayName }),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (response.status === 409) return denyTo(origin, "conflict");
    if (!response.ok) throw new Error(`core answered ${response.status}`);
    account = await response.json();
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Yandex OAuth: ядро не приняло вход:", (error as Error).message);
    return denyTo(origin, "exchange");
  }
  if (!account.client_account_id) return denyTo(origin, "profile");

  const response = NextResponse.redirect(new URL(oauth.next || "/cabinet", origin));
  response.cookies.set(
    CLIENT_ACCOUNT_COOKIE,
    sealClientAccount(
      { accountId: account.client_account_id, email: account.email || profile.email, name: account.display_name || profile.displayName },
      cookieSecret,
    ),
    clientCookieOptions(CLIENT_SESSION_MAX_AGE_SECONDS),
  );
  response.cookies.set(CLIENT_OAUTH_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/cabinet", maxAge: 0 });
  return response;
}
