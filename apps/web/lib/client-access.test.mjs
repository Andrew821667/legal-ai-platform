import assert from "node:assert/strict";
import { test } from "node:test";

import { checkClientSessionCookie } from "./client-access.ts";
import { mintClientSessionToken } from "./client-session.ts";

const SECRET = "client-secret";

test("валидный токен в куке проходит", () => {
  const token = mintClientSessionToken(848510279, SECRET);
  const result = checkClientSessionCookie({ cookie: token, secret: SECRET });
  assert.deepEqual(result, { ok: true, telegramUserId: 848510279 });
});

test("без куки — 401 с просьбой войти", () => {
  const result = checkClientSessionCookie({ cookie: "", secret: SECRET });
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.status, 401);
  assert.match(!result.ok ? result.detail : "", /Войдите/);
});

test("без секрета на сервере — 500, а не тихий пропуск", () => {
  const token = mintClientSessionToken(1, SECRET);
  const result = checkClientSessionCookie({ cookie: token, secret: "" });
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.status, 500);
});

test("токен, подписанный другим секретом, не проходит", () => {
  const token = mintClientSessionToken(1, "другой-секрет");
  const result = checkClientSessionCookie({ cookie: token, secret: SECRET });
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.status, 401);
  assert.match(!result.ok ? result.detail : "", /истёк/);
});

test("протухший токен отклоняется с понятным текстом", () => {
  const DAY = 24 * 60 * 60;
  const now = 1_700_000_000;
  const token = mintClientSessionToken(1, SECRET, now - 7 * DAY - 1);
  const result = checkClientSessionCookie({ cookie: token, secret: SECRET, now });
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.status, 401);
  assert.match(!result.ok ? result.detail : "", /истёк/);
});
