import { createHash, randomBytes } from "node:crypto";

import { createRemoteJWKSet, jwtVerify, type JWTPayload, type JWTVerifyGetKey } from "jose";

/**
 * Telegram Login через OpenID Connect — Authorization Code Flow + PKCE.
 * Проверено по https://oauth.telegram.org/.well-known/openid-configuration:
 * authorization_endpoint=/auth, token_endpoint=/token,
 * jwks_uri=/.well-known/jwks.json, id_token подписан RS256/ES256/EdDSA/ES256K
 * (ES256K не поддерживает jose, в algorithms не включаем — если Telegram
 * когда-нибудь подпишет им конкретный токен, verifyIdToken его отклонит).
 * Userinfo-эндпоинта нет — весь профиль только из id_token claims.
 */

const AUTHORIZATION_ENDPOINT = "https://oauth.telegram.org/auth";
const TOKEN_ENDPOINT = "https://oauth.telegram.org/token";
const JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json";
const ISSUER = "https://oauth.telegram.org";

export { ISSUER as TELEGRAM_OIDC_ISSUER };

export type PkcePair = { verifier: string; challenge: string };

/** code_verifier — 43..128 символов из unreserved-набора; 32 случайных байта
 * в base64url без паддинга дают 43 символа, что укладывается в диапазон. */
export function createPkce(): PkcePair {
  const verifier = randomBytes(32).toString("base64url");
  const challenge = createHash("sha256").update(verifier).digest("base64url");
  return { verifier, challenge };
}

export function randomToken(bytes = 24): string {
  return randomBytes(bytes).toString("base64url");
}

export type AuthorizationUrlParams = {
  clientId: string;
  redirectUri: string;
  scope: string;
  state: string;
  nonce: string;
  codeChallenge: string;
};

export function buildAuthorizationUrl(params: AuthorizationUrlParams): string {
  const url = new URL(AUTHORIZATION_ENDPOINT);
  url.searchParams.set("client_id", params.clientId);
  url.searchParams.set("redirect_uri", params.redirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", params.scope);
  url.searchParams.set("state", params.state);
  url.searchParams.set("nonce", params.nonce);
  url.searchParams.set("code_challenge", params.codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

export type ExchangeCodeParams = {
  code: string;
  redirectUri: string;
  codeVerifier: string;
  clientId: string;
  clientSecret: string;
  tokenEndpoint?: string;
};

export type ExchangeCodeResult = {
  idToken: string;
  accessToken?: string;
  expiresIn?: number;
};

/** fetchImpl инъецируется, чтобы тесты не ходили в сеть. */
export async function exchangeCode(
  params: ExchangeCodeParams,
  fetchImpl: typeof fetch = fetch,
): Promise<ExchangeCodeResult> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code: params.code,
    redirect_uri: params.redirectUri,
    code_verifier: params.codeVerifier,
  });
  // RFC 6749 §2.3.1 — client_secret_basic: оба компонента form-urlencoded
  // перед конкатенацией через ":" и base64.
  const basic = Buffer.from(
    `${encodeURIComponent(params.clientId)}:${encodeURIComponent(params.clientSecret)}`,
  ).toString("base64");

  let response: Response;
  try {
    response = await fetchImpl(params.tokenEndpoint ?? TOKEN_ENDPOINT, {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        authorization: `Basic ${basic}`,
      },
      body: body.toString(),
      signal: AbortSignal.timeout(10_000),
    });
  } catch (error) {
    throw new Error(`Telegram token endpoint unreachable: ${(error as Error).message}`);
  }
  if (!response.ok) {
    throw new Error(`Telegram token endpoint returned ${response.status}`);
  }
  const data = (await response.json().catch(() => null)) as Record<string, unknown> | null;
  if (!data || typeof data.id_token !== "string" || !data.id_token) {
    throw new Error("Telegram token endpoint response has no id_token");
  }
  return {
    idToken: data.id_token,
    accessToken: typeof data.access_token === "string" ? data.access_token : undefined,
    expiresIn: typeof data.expires_in === "number" ? data.expires_in : undefined,
  };
}

let cachedJwks: JWTVerifyGetKey | null = null;

/** Один процесс — один remote JWKS с собственным кешем ключей на стороне
 * jose; cooldownDuration защищает от повторных запросов при неизвестном kid
 * чаще, чем раз в 30с (например, если атакующий шлёт токены с мусорным kid). */
export function remoteJwks(): JWTVerifyGetKey {
  if (!cachedJwks) {
    cachedJwks = createRemoteJWKSet(new URL(JWKS_URL), {
      cooldownDuration: 30_000,
      cacheMaxAge: 600_000,
    });
  }
  return cachedJwks;
}

export type VerifyIdTokenParams = {
  issuer?: string;
  audience: string;
  nonce?: string;
  clockToleranceSeconds?: number;
};

export async function verifyIdToken(
  idToken: string,
  params: VerifyIdTokenParams,
  getKey: JWTVerifyGetKey = remoteJwks(),
): Promise<JWTPayload> {
  const { payload } = await jwtVerify(idToken, getKey, {
    issuer: params.issuer ?? ISSUER,
    audience: params.audience,
    algorithms: ["RS256", "ES256", "EdDSA"],
    clockTolerance: params.clockToleranceSeconds ?? 60,
  });
  if (params.nonce && payload.nonce !== params.nonce) {
    throw new Error("id_token nonce mismatch");
  }
  return payload;
}
