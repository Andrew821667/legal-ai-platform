import { CLIENT_SESSION_MAX_AGE_SECONDS, openClientAccount, verifyClientSessionToken } from "./client-session.ts";

/**
 * Решение о допуске в личный кабинет по cookie-сессии — framework-free, по
 * образцу checkLawyerSessionCookie в lawyer-access.ts. Namespace клиента не
 * содержит allowlist: в отличие от рабочего места юриста (данные всех
 * клиентов практики), кабинет показывает только данные владельца сессии —
 * ядро (core-api) само проверяет владение по telegramUserId.
 */

export type ClientAccessOk = { ok: true; telegramUserId: number };
export type ClientAccessDenied = { ok: false; status: 401 | 500; detail: string };
export type ClientAccessResult = ClientAccessOk | ClientAccessDenied;

export type ClientSessionCookieInput = {
  cookie: string;
  secret: string;
  now?: number;
};

export function checkClientSessionCookie({
  cookie,
  secret,
  now = Math.floor(Date.now() / 1000),
}: ClientSessionCookieInput): ClientAccessResult {
  if (!cookie.trim()) {
    return { ok: false, status: 401, detail: "Войдите в личный кабинет через Telegram." };
  }
  if (!secret.trim()) {
    return {
      ok: false,
      status: 500,
      detail: "Сервер не настроен: нет секрета сессии кабинета",
    };
  }

  const verified = verifyClientSessionToken(cookie, secret, now);
  if (verified === null) {
    return { ok: false, status: 401, detail: "Сеанс кабинета истёк. Войдите через Telegram ещё раз." };
  }

  return { ok: true, telegramUserId: verified.telegramUserId };
}

export { CLIENT_SESSION_MAX_AGE_SECONDS };

export type ClientAccountAccessResult = { ok: true; accountId: string } | ClientAccessDenied;

/** Сессия учётной записи (вход через Яндекс ID). */
export function checkClientAccountCookie({
  cookie,
  secret,
  now = Math.floor(Date.now() / 1000),
}: ClientSessionCookieInput): ClientAccountAccessResult {
  if (!cookie.trim()) {
    return { ok: false, status: 401, detail: "Войдите в личный кабинет." };
  }
  if (!secret.trim()) {
    return { ok: false, status: 500, detail: "Сервер не настроен: нет секрета сессии кабинета" };
  }
  const session = openClientAccount(cookie, secret, now);
  if (session === null) {
    return { ok: false, status: 401, detail: "Сеанс кабинета истёк. Войдите ещё раз." };
  }
  return { ok: true, accountId: session.accountId };
}
