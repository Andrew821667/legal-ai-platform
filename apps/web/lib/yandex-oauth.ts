/**
 * Вход в кабинет через Яндекс ID — OAuth 2.0 Authorization Code + PKCE.
 *
 * Telegram в России заблокирован: «Войти через Telegram» без VPN не работает.
 * Аккаунт Яндекса есть почти у всех, и Яндекс сам подтверждает почту — её
 * берём как идентификатор клиента.
 *
 * Поток: /cabinet/login/yandex → oauth.yandex.ru/authorize → обратно на
 * /cabinet/callback/yandex с кодом → обмен кода на токен (на сервере, с
 * client_secret и code_verifier) → login.yandex.ru/info → почта и id.
 * В браузер токен не попадает.
 *
 * Доступы приложения задаются при регистрации на oauth.yandex.ru:
 * «Доступ к адресу электронной почты» и «Доступ к логину, имени и фамилии».
 * Модуль без Next — чтобы тестировать с подставным fetch.
 */

export const YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize";
export const YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token";
export const YANDEX_INFO_URL = "https://login.yandex.ru/info?format=json";

export type YandexConfig = { clientId: string; clientSecret: string; redirectUri: string };

export type YandexProfile = { yandexId: string; email: string; displayName: string | null };

export class YandexOauthError extends Error {
  readonly reason: "exchange" | "profile" | "email";

  constructor(reason: "exchange" | "profile" | "email", message: string) {
    super(message);
    this.reason = reason;
  }
}

export function yandexConfig(
  env: Record<string, string | undefined>,
  origin: string,
): YandexConfig | null {
  const clientId = (env.YANDEX_OAUTH_CLIENT_ID || "").trim();
  const clientSecret = (env.YANDEX_OAUTH_CLIENT_SECRET || "").trim();
  if (!clientId || !clientSecret) return null;
  // Адрес возврата должен побайтно совпадать с указанным при регистрации
  // приложения — поэтому из настроек, а не из заголовков запроса.
  const redirectUri = (env.YANDEX_OAUTH_REDIRECT_URI || "").trim() || `${origin}/cabinet/callback/yandex`;
  return { clientId, clientSecret, redirectUri };
}

export function buildYandexAuthorizeUrl(params: {
  clientId: string;
  redirectUri: string;
  state: string;
  codeChallenge: string;
}): string {
  const url = new URL(YANDEX_AUTHORIZE_URL);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", params.clientId);
  url.searchParams.set("redirect_uri", params.redirectUri);
  url.searchParams.set("state", params.state);
  url.searchParams.set("code_challenge", params.codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

export async function exchangeYandexCode(
  params: { code: string; codeVerifier: string; config: YandexConfig },
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code: params.code,
    client_id: params.config.clientId,
    client_secret: params.config.clientSecret,
    code_verifier: params.codeVerifier,
  });
  let response: Response;
  try {
    response = await fetchImpl(YANDEX_TOKEN_URL, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch (error) {
    throw new YandexOauthError("exchange", `token request failed: ${(error as Error).name}`);
  }
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  const token = typeof data.access_token === "string" ? data.access_token : "";
  if (!response.ok || !token) {
    throw new YandexOauthError("exchange", `token endpoint answered ${response.status}: ${String(data.error || "")}`);
  }
  return token;
}

/** Профиль из ответа login.yandex.ru/info: нужен id и подтверждённая почта. */
export function profileFromYandexInfo(info: unknown, clientId: string): YandexProfile {
  if (!info || typeof info !== "object") throw new YandexOauthError("profile", "empty profile");
  const data = info as Record<string, unknown>;
  const yandexId = typeof data.id === "string" || typeof data.id === "number" ? String(data.id) : "";
  if (!/^[0-9A-Za-z_-]{1,64}$/.test(yandexId)) throw new YandexOauthError("profile", "no yandex id");
  // Токен должен быть выдан нашему приложению, а не принесён от чужого.
  if (typeof data.client_id === "string" && data.client_id && data.client_id !== clientId) {
    throw new YandexOauthError("profile", "token issued to another client");
  }
  const emails = Array.isArray(data.emails) ? data.emails.filter((e): e is string => typeof e === "string") : [];
  const email = (typeof data.default_email === "string" && data.default_email) || emails[0] || "";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    throw new YandexOauthError("email", "no email: grant the email access in the app settings");
  }
  const pick = (key: string) => (typeof data[key] === "string" && (data[key] as string).trim()) || null;
  const displayName = pick("first_name") || pick("display_name") || pick("real_name") || pick("login");
  return { yandexId, email: email.toLowerCase(), displayName: displayName ? displayName.slice(0, 255) : null };
}

export async function fetchYandexProfile(
  accessToken: string,
  clientId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<YandexProfile> {
  let response: Response;
  try {
    response = await fetchImpl(YANDEX_INFO_URL, {
      headers: { authorization: `OAuth ${accessToken}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch (error) {
    throw new YandexOauthError("profile", `info request failed: ${(error as Error).name}`);
  }
  if (!response.ok) throw new YandexOauthError("profile", `info endpoint answered ${response.status}`);
  return profileFromYandexInfo(await response.json().catch(() => null), clientId);
}
