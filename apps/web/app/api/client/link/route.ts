import { NextRequest, NextResponse } from "next/server";

import { isTrustedAssistantOrigin, trustedHostsFor } from "@/lib/assistant-security";
import { checkClientAccountCookie } from "@/lib/client-access";
import { clientCoreDelete, clientCorePost, fetchClientAccount } from "@/lib/client-core";
import { cleanLinkCode, readBothSessions } from "@/lib/client-link";
import {
  CLIENT_ACCOUNT_COOKIE,
  CLIENT_PROFILE_COOKIE,
  CLIENT_SESSION_COOKIE,
  CLIENT_SESSION_MAX_AGE_SECONDS,
  clientSessionSecret,
} from "@/lib/client-session";
import { resolveLeadClientIp } from "@/lib/lead-security";
import { checkSlidingWindow, commitSlidingWindowHit } from "@/lib/rate-limit";
import { openCookieValue } from "@/lib/signed-cookie";
import type { ClientProfileCookie } from "@/lib/telegram-login-profile";

/**
 * Объединение учётной записи (вход через Яндекс ID) с Telegram — по согласию
 * клиента (кнопка «Объединить»), с доказательством владения обоими входами:
 * кодом из бота или двумя свежими сессиями в этом браузере (lib/client-link.ts).
 * DELETE — отзыв согласия (отвязать Telegram).
 */

export const dynamic = "force-dynamic";

const WINDOW_MS = 10 * 60_000;
const accountAttempts = new Map<string, number[]>();
const ipAttempts = new Map<string, number[]>();

function accountFrom(request: NextRequest): { accountId: string; secret: string } | NextResponse {
  if (!isTrustedAssistantOrigin(request.headers.get("origin"), trustedHostsFor(request))) {
    return NextResponse.json({ detail: "Недопустимый источник запроса" }, { status: 403 });
  }
  const secret = clientSessionSecret();
  const result = checkClientAccountCookie({ cookie: request.cookies.get(CLIENT_ACCOUNT_COOKIE)?.value || "", secret });
  if (!result.ok) {
    const detail = result.status === 401 ? "Войдите в кабинет через Яндекс ID." : result.detail;
    return NextResponse.json({ detail }, { status: result.status });
  }
  return { accountId: result.accountId, secret };
}

/** Состояние объединения — профиль опрашивает его, пока ждёт «Да» в боте. */
export async function GET(request: NextRequest) {
  const secret = clientSessionSecret();
  const result = checkClientAccountCookie({ cookie: request.cookies.get(CLIENT_ACCOUNT_COOKIE)?.value || "", secret });
  if (!result.ok) {
    return NextResponse.json({ detail: result.detail }, { status: result.status });
  }
  const account = await fetchClientAccount(result.accountId);
  if (!account) {
    return NextResponse.json({ detail: "Кабинет временно недоступен." }, { status: 503 });
  }
  return NextResponse.json({ linked: Boolean(account.telegram_user_id), pending: Boolean(account.link_pending) });
}

export async function POST(request: NextRequest) {
  const auth = accountFrom(request);
  if (auth instanceof NextResponse) return auth;
  const body = (await request.json().catch(() => ({}))) as { code?: unknown; from_session?: unknown };
  const path = `/api/v1/client-auth/accounts/${auth.accountId}/telegram`;

  if (body.from_session === true) {
    const both = readBothSessions({
      sessionCookie: request.cookies.get(CLIENT_SESSION_COOKIE)?.value || "",
      accountCookie: request.cookies.get(CLIENT_ACCOUNT_COOKIE)?.value || "",
      secret: auth.secret,
    });
    if (!both || both.accountId !== auth.accountId) {
      return NextResponse.json({ detail: "Войдите через Telegram, чтобы объединить." }, { status: 401 });
    }
    if (!both.telegramFresh || !both.accountFresh) {
      return NextResponse.json(
        {
          detail:
            "Для объединения подтвердите оба входа заново: войдите через Telegram и через Яндекс ID, затем нажмите «Объединить» в течение 15 минут.",
          relogin: { telegram: !both.telegramFresh, yandex: !both.accountFresh },
        },
        { status: 409 },
      );
    }
    const profile = openCookieValue<ClientProfileCookie>(
      request.cookies.get(CLIENT_PROFILE_COOKIE)?.value || "",
      auth.secret,
      CLIENT_SESSION_MAX_AGE_SECONDS,
    );
    return clientCorePost(path, { telegram_user_id: both.telegramUserId, telegram_username: profile?.un || null });
  }

  const code = cleanLinkCode(body.code);
  if (!code) {
    return NextResponse.json({ detail: "Введите код из бота." }, { status: 422 });
  }
  // Код — ~40 бит, перебор и так безнадёжен; лимит — чтобы не нагружать ядро.
  const now = Date.now();
  const ip = resolveLeadClientIp(request.headers);
  const byAccount = checkSlidingWindow(accountAttempts, auth.accountId, 8, WINDOW_MS, now);
  const byIp = checkSlidingWindow(ipAttempts, ip, 20, WINDOW_MS, now);
  if (!byAccount.allowed || !byIp.allowed) {
    return NextResponse.json(
      { detail: "Слишком много попыток. Запросите в боте новый код и попробуйте через 10 минут." },
      { status: 429 },
    );
  }
  commitSlidingWindowHit(accountAttempts, auth.accountId, byAccount.rows, now);
  commitSlidingWindowHit(ipAttempts, ip, byIp.rows, now);
  return clientCorePost(path, { code });
}

export async function DELETE(request: NextRequest) {
  const auth = accountFrom(request);
  if (auth instanceof NextResponse) return auth;
  return clientCoreDelete(`/api/v1/client-auth/accounts/${auth.accountId}/telegram`);
}
