import { NextRequest, NextResponse } from "next/server";

import {
  CLIENT_OAUTH_COOKIE,
  CLIENT_PROFILE_COOKIE,
  CLIENT_SESSION_COOKIE,
  CLIENT_SESSION_MAX_AGE_SECONDS,
  clientCookieOptions,
  clientSessionSecret,
  mintClientSessionToken,
} from "@/lib/client-session";
import { publicOrigin } from "@/lib/public-origin";
import { sealCookieValue } from "@/lib/signed-cookie";
import { toProfileCookie, type TelegramLoginProfile } from "@/lib/telegram-login-profile";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY = process.env.CORE_API_BOT_KEY || process.env.API_KEY_BOT || "";

/**
 * Верифицированный номер (scope phone, согласие получено) дозаполняет пустой
 * Lead.phone на стороне ядра. Best-effort и осознанно вне критического пути:
 * ядро может быть недоступно, но это не повод не пустить человека в его же
 * кабинет — просто телефон дозаполнится при следующем входе.
 */
async function syncTelegramProfileBestEffort(profile: TelegramLoginProfile): Promise<void> {
  if (!profile.phone || !profile.phoneVerified || !CORE_API_BOT_KEY) return;
  try {
    await fetch(`${CORE_API_URL}/api/v1/client-portal/telegram-profile`, {
      method: "POST",
      headers: { "X-API-Key": CORE_API_BOT_KEY, "content-type": "application/json" },
      body: JSON.stringify({
        telegram_user_id: profile.telegramUserId,
        phone: profile.phone,
        phone_verified: true,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Не удалось синхронизировать телефон клиента с ядром:", (error as Error).message);
  }
}

/**
 * Единственная точка выдачи сессии кабинета — общая для OIDC-callback и
 * legacy-callback. Дальше от режима входа ничего не зависит: одна и та же
 * кука, один и тот же кабинет.
 */
export async function establishClientSession(
  profile: TelegramLoginProfile,
  request: NextRequest,
  next: string = "/cabinet",
): Promise<NextResponse> {
  const secret = clientSessionSecret();
  if (!secret) {
    return NextResponse.redirect(
      new URL("/cabinet?login=misconfigured", publicOrigin(request.headers, request.nextUrl.host)),
    );
  }

  await syncTelegramProfileBestEffort(profile);

  const origin = publicOrigin(request.headers, request.nextUrl.host);
  const response = NextResponse.redirect(new URL(next, origin));

  response.cookies.set(
    CLIENT_SESSION_COOKIE,
    mintClientSessionToken(profile.telegramUserId, secret),
    clientCookieOptions(CLIENT_SESSION_MAX_AGE_SECONDS, "/"),
  );
  response.cookies.set(
    CLIENT_PROFILE_COOKIE,
    sealCookieValue(toProfileCookie(profile), secret),
    clientCookieOptions(CLIENT_SESSION_MAX_AGE_SECONDS, "/"),
  );
  response.cookies.set(CLIENT_OAUTH_COOKIE, "", { ...clientCookieOptions(0, "/cabinet") });

  return response;
}
