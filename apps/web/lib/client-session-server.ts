import { cookies } from "next/headers";

import { CLIENT_PROFILE_COOKIE, CLIENT_SESSION_COOKIE, CLIENT_SESSION_MAX_AGE_SECONDS, clientSessionSecret, verifyClientSessionToken } from "./client-session";
import { openCookieValue } from "./signed-cookie";
import type { ClientProfileCookie } from "./telegram-login-profile";

export type ClientSession = { telegramUserId: number; profile: ClientProfileCookie | null };

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
  if (!verified) return null;

  const profile = openCookieValue<ClientProfileCookie>(
    store.get(CLIENT_PROFILE_COOKIE)?.value || "",
    secret,
    CLIENT_SESSION_MAX_AGE_SECONDS,
  );

  return { telegramUserId: verified.telegramUserId, profile };
}
