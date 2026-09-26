import { cookies } from "next/headers";

import {
  CLIENT_ACCOUNT_COOKIE,
  CLIENT_PROFILE_COOKIE,
  CLIENT_SESSION_COOKIE,
  CLIENT_SESSION_MAX_AGE_SECONDS,
  clientSessionSecret,
  openClientAccount,
  verifyClientSessionToken,
} from "./client-session";
import { openCookieValue } from "./signed-cookie";
import type { ClientProfileCookie } from "./telegram-login-profile";

export type ClientSession = {
  telegramUserId: number | null;
  accountId: string | null;
  profile: ClientProfileCookie | null;
};

/**
 * Единственный модуль с next/headers для сессии клиента — серверные
 * компоненты /cabinet читают куку напрямую, без похода на свой же
 * /api/client/me (тот эндпоинт существует для клиентского JS, не для RSC).
 */
export async function readClientSession(): Promise<ClientSession | null> {
  const secret = clientSessionSecret();
  if (!secret) return null;

  const store = await cookies();
  const verified = verifyClientSessionToken(store.get(CLIENT_SESSION_COOKIE)?.value || "", secret);
  if (!verified) {
    // Вход через Яндекс ID: сессия — учётная запись, профиль — из её куки.
    const account = openClientAccount(store.get(CLIENT_ACCOUNT_COOKIE)?.value || "", secret);
    if (!account) return null;
    return {
      telegramUserId: null,
      accountId: account.accountId,
      profile: { fn: account.name || account.email || "Клиент", method: "yandex", email: account.email || undefined },
    };
  }

  const profile = openCookieValue<ClientProfileCookie>(
    store.get(CLIENT_PROFILE_COOKIE)?.value || "",
    secret,
    CLIENT_SESSION_MAX_AGE_SECONDS,
  );

  return { telegramUserId: verified.telegramUserId, accountId: null, profile };
}
