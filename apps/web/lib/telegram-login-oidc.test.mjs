import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";

import { createLocalJWKSet, exportJWK, generateKeyPair, SignJWT } from "jose";

import {
  buildAuthorizationUrl,
  createPkce,
  exchangeCode,
  TELEGRAM_OIDC_ISSUER,
  verifyIdToken,
} from "./telegram-login-oidc.ts";

const AUDIENCE = "123456789";

async function issuer() {
  const { publicKey, privateKey } = await generateKeyPair("RS256");
  const kid = "test-key-1";
  const jwk = await exportJWK(publicKey);
  const jwks = createLocalJWKSet({ keys: [{ ...jwk, kid, alg: "RS256", use: "sig" }] });

  async function sign(claims, { alg = "RS256", withKid = true, expiresInSeconds = 300 } = {}) {
    let builder = new SignJWT(claims)
      .setProtectedHeader(withKid ? { alg, kid } : { alg })
      .setIssuedAt();
    if (expiresInSeconds !== null) {
      builder = builder.setExpirationTime(Math.floor(Date.now() / 1000) + expiresInSeconds);
    }
    return builder.sign(privateKey);
  }

  return { jwks, sign };
}

function baseClaims(overrides = {}) {
  return {
    iss: TELEGRAM_OIDC_ISSUER,
    aud: AUDIENCE,
    sub: "848510279",
    nonce: "test-nonce",
    ...overrides,
  };
}

test("валидный id_token с верной подписью проходит", async () => {
  const { jwks, sign } = await issuer();
  const token = await sign(baseClaims());
  const payload = await verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, jwks);
  assert.equal(payload.sub, "848510279");
});

test("неверный issuer отклоняется", async () => {
  const { jwks, sign } = await issuer();
  const token = await sign(baseClaims({ iss: "https://evil.example" }));
  await assert.rejects(() => verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, jwks));
});

test("неверный audience отклоняется", async () => {
  const { jwks, sign } = await issuer();
  const token = await sign(baseClaims({ aud: "someone-elses-bot" }));
  await assert.rejects(() => verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, jwks));
});

test("несовпадающий nonce отклоняется", async () => {
  const { jwks, sign } = await issuer();
  const token = await sign(baseClaims({ nonce: "another-nonce" }));
  await assert.rejects(() => verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, jwks));
});

test("истёкший токен отклоняется", async () => {
  const { jwks, sign } = await issuer();
  const token = await sign(baseClaims(), { expiresInSeconds: -120 });
  await assert.rejects(() => verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, jwks));
});

test("токен с неизвестным kid отклоняется (chuzhoy ключ)", async () => {
  const { sign } = await issuer();
  const other = await issuer(); // другой issuer => другой jwks-набор
  const token = await sign(baseClaims());
  await assert.rejects(() => verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, other.jwks));
});

test("алгоритм вне allow-list (HS256) отклоняется", async () => {
  const { jwks } = await issuer();
  // HS256 — симметричный алгоритм, не входит в допустимый список RS256/ES256/EdDSA.
  const token = await new SignJWT(baseClaims())
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(Math.floor(Date.now() / 1000) + 300)
    .sign(new TextEncoder().encode("some-hmac-secret-that-is-long-enough"));
  await assert.rejects(() => verifyIdToken(token, { audience: AUDIENCE, nonce: "test-nonce" }, jwks));
});

test("PKCE: challenge — base64url(sha256(verifier))", () => {
  const { verifier, challenge } = createPkce();
  const expected = createHash("sha256").update(verifier).digest("base64url");
  assert.equal(challenge, expected);
  assert.match(verifier, /^[A-Za-z0-9_-]{43,128}$/);
});

test("buildAuthorizationUrl содержит все обязательные параметры PKCE-запроса", () => {
  const url = new URL(
    buildAuthorizationUrl({
      clientId: "123456789",
      redirectUri: "https://ai-verdict.ru/cabinet/callback",
      scope: "openid profile phone",
      state: "state-value",
      nonce: "nonce-value",
      codeChallenge: "challenge-value",
    }),
  );
  assert.equal(url.origin + url.pathname, "https://oauth.telegram.org/auth");
  assert.equal(url.searchParams.get("client_id"), "123456789");
  assert.equal(url.searchParams.get("redirect_uri"), "https://ai-verdict.ru/cabinet/callback");
  assert.equal(url.searchParams.get("response_type"), "code");
  assert.equal(url.searchParams.get("scope"), "openid profile phone");
  assert.equal(url.searchParams.get("state"), "state-value");
  assert.equal(url.searchParams.get("nonce"), "nonce-value");
  assert.equal(url.searchParams.get("code_challenge"), "challenge-value");
  assert.equal(url.searchParams.get("code_challenge_method"), "S256");
});

function fakeFetch(handler) {
  return async (url, init) => handler(url, init);
}

test("exchangeCode шлёт Basic-заголовок, form-тело с code_verifier и парсит id_token", async () => {
  let seenUrl;
  let seenInit;
  const fetchImpl = fakeFetch(async (url, init) => {
    seenUrl = url;
    seenInit = init;
    return new Response(JSON.stringify({ id_token: "abc.def.ghi", access_token: "at", expires_in: 3600 }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  });

  const result = await exchangeCode(
    {
      code: "the-code",
      redirectUri: "https://ai-verdict.ru/cabinet/callback",
      codeVerifier: "the-verifier",
      clientId: "123456789",
      clientSecret: "the-secret",
    },
    fetchImpl,
  );

  assert.equal(result.idToken, "abc.def.ghi");
  assert.equal(result.accessToken, "at");
  assert.equal(result.expiresIn, 3600);
  assert.equal(seenUrl, "https://oauth.telegram.org/token");
  assert.equal(seenInit.method, "POST");
  const expectedBasic = Buffer.from("123456789:the-secret").toString("base64");
  assert.equal(seenInit.headers.authorization, `Basic ${expectedBasic}`);
  const body = new URLSearchParams(seenInit.body);
  assert.equal(body.get("grant_type"), "authorization_code");
  assert.equal(body.get("code"), "the-code");
  assert.equal(body.get("redirect_uri"), "https://ai-verdict.ru/cabinet/callback");
  assert.equal(body.get("code_verifier"), "the-verifier");
});

test("exchangeCode бросает ошибку при не-200 ответе", async () => {
  const fetchImpl = fakeFetch(async () => new Response("bad request", { status: 400 }));
  await assert.rejects(
    () =>
      exchangeCode(
        {
          code: "x",
          redirectUri: "https://ai-verdict.ru/cabinet/callback",
          codeVerifier: "v",
          clientId: "1",
          clientSecret: "s",
        },
        fetchImpl,
      ),
    /400/,
  );
});

test("exchangeCode бросает ошибку, если ответ без id_token", async () => {
  const fetchImpl = fakeFetch(
    async () => new Response(JSON.stringify({ access_token: "at" }), { status: 200 }),
  );
  await assert.rejects(() =>
    exchangeCode(
      {
        code: "x",
        redirectUri: "https://ai-verdict.ru/cabinet/callback",
        codeVerifier: "v",
        clientId: "1",
        clientSecret: "s",
      },
      fetchImpl,
    ),
  );
});
