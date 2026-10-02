import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";

import { LOGIN_TOKEN_MAX_TTL_SECONDS, mintLawyerLoginToken, verifyLawyerLoginToken } from "./lawyer-login-token.ts";
import { mintLawyerSessionToken } from "./lawyer-session-token.ts";

const SECRET = "shared-secret";
const NONCE = "0123456789abcdef0123456789abcdef";
const NOW = 1_790_000_000;

test("свежая ссылка входа проходит и несёт nonce и срок", () => {
  const token = mintLawyerLoginToken(848510279, SECRET, { ttl: 900, nonce: NONCE, issuedAt: NOW });
  assert.deepEqual(verifyLawyerLoginToken(token, SECRET, NOW + 10), {
    telegramUserId: 848510279, issuedAt: NOW, ttl: 900, nonce: NONCE, expiresAt: NOW + 900,
  });
});

test("подпись совпадает с ботом: HMAC над lawyer-login.<id>.<issuedAt>.<ttl>.<nonce>", () => {
  const token = mintLawyerLoginToken(1, SECRET, { ttl: 900, nonce: NONCE, issuedAt: NOW });
  const expected = createHmac("sha256", SECRET).update(`lawyer-login.1.${NOW}.900.${NONCE}`).digest("hex");
  assert.equal(token, `v2.1.${NOW}.900.${NONCE}.${expected}`);
});

test("просроченная, из будущего, со сроком больше недели — отказ", () => {
  const token = mintLawyerLoginToken(1, SECRET, { ttl: 900, nonce: NONCE, issuedAt: NOW });
  assert.equal(verifyLawyerLoginToken(token, SECRET, NOW + 901), null);
  assert.equal(verifyLawyerLoginToken(token, SECRET, NOW - 120), null);
  const long = mintLawyerLoginToken(1, SECRET, { ttl: LOGIN_TOKEN_MAX_TTL_SECONDS + 1, nonce: NONCE, issuedAt: NOW });
  assert.equal(verifyLawyerLoginToken(long, SECRET, NOW), null);
});

test("чужой секрет, подмена срока и токен сессии вместо ссылки — отказ", () => {
  const token = mintLawyerLoginToken(1, SECRET, { ttl: 900, nonce: NONCE, issuedAt: NOW });
  assert.equal(verifyLawyerLoginToken(token, "other", NOW), null);
  assert.equal(verifyLawyerLoginToken(token.replace(".900.", ".9000."), SECRET, NOW), null);
  // Прежний формат ссылки (он же токен сессии на 30 дней) больше не вход.
  assert.equal(verifyLawyerLoginToken(mintLawyerSessionToken(1, SECRET, NOW), SECRET, NOW), null);
  assert.equal(verifyLawyerLoginToken(token, "", NOW), null);
});
