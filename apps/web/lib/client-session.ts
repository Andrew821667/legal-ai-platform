import { mintSessionToken, verifySessionToken, type SessionTokenResult } from "./session-token.ts";

/**
 * Сессия личного кабинета клиента — stateless-кука по образцу lawyer_session,
 * но с собственным сроком жизни и собственным секретом.
 *
 * CLIENT_SESSION_SECRET обязан отличаться от LAWYER_SESSION_SECRET: формат
 * токена (<tgId>.<issuedAt>.<hex-hmac>) у обеих ролей одинаковый, и одинаковый
 * секрет означал бы, что кука клиента с id практикующего юриста проходит как
 * lawyer_session, и наоборот — читай clientSessionSecret().
 */

export const CLIENT_SESSION_COOKIE = "client_session";
export const CLIENT_PROFILE_COOKIE = "client_profile";
export const CLIENT_OAUTH_COOKIE = "client_oauth";

export const CLIENT_SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;
export const CLIENT_OAUTH_MAX_AGE_SECONDS = 10 * 60;

let loggedSecretCollision = false;

/**
 * Секрет сессии клиента. Пусто, если не настроен ИЛИ совпадает с секретом
 * юриста — во втором случае это не ошибка конфигурации, которую можно молча
 * пропустить: возврат непустого совпадающего значения означал бы, что вход
 * клиента и вход юриста делят один HMAC-ключ. Отключаем вход клиента (вызывающая
 * сторона отдаёт 500) и один раз пишем в лог, а не роняем процесс — сайт не
 * должен падать целиком из-за одной опечатки в .env.
 */
export function clientSessionSecret(): string {
  const secret = (process.env.CLIENT_SESSION_SECRET || "").trim();
  if (!secret) return "";
  const lawyerSecret = (process.env.LAWYER_SESSION_SECRET || "").trim();
  if (lawyerSecret && secret === lawyerSecret) {
    if (!loggedSecretCollision) {
      loggedSecretCollision = true;
      // eslint-disable-next-line no-console
      console.error(
        "CLIENT_SESSION_SECRET совпадает с LAWYER_SESSION_SECRET — вход клиента отключён до исправления .env",
      );
    }
    return "";
  }
  return secret;
}

export function mintClientSessionToken(
  telegramUserId: number,
  secret: string,
  issuedAt?: number,
): string {
  return mintSessionToken(telegramUserId, secret, issuedAt);
}

export function verifyClientSessionToken(
  token: string,
  secret: string,
  now?: number,
): SessionTokenResult | null {
  return verifySessionToken(token, secret, CLIENT_SESSION_MAX_AGE_SECONDS, now);
}

export type CookieOptions = {
  httpOnly: true;
  secure: true;
  sameSite: "lax";
  path: string;
  maxAge: number;
};

/**
 * sameSite=lax везде, а не strict — /cabinet/callback приходит top-level GET
 * с oauth.telegram.org (редирект после согласия), а также ссылка на кабинет
 * может прийти из Telegram-бота. strict эту куку попросту не отправил бы.
 */
export function clientCookieOptions(maxAge: number, path = "/"): CookieOptions {
  return { httpOnly: true, secure: true, sameSite: "lax", path, maxAge };
}
