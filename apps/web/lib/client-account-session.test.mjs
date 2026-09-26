import assert from "node:assert/strict";
import { test } from "node:test";

import { openClientAccount, sealClientAccount } from "./client-session.ts";
import { checkClientAccountCookie } from "./client-access.ts";
import { clientFields, clientKey, clientQuery } from "./client-ref.ts";
import { sealCookieValue } from "./signed-cookie.ts";

const secret = "s".repeat(32);
const id = "0b6f6f0e-8f4a-4d7e-9a61-2f6d1c0a9b11";

test("кука учётной записи: открывается своим секретом, не чужим", () => {
  const raw = sealClientAccount({ accountId: id, email: "a@ya.ru", name: "Анна" }, secret);
  assert.deepEqual(openClientAccount(raw, secret), { accountId: id, email: "a@ya.ru", name: "Анна" });
  assert.equal(openClientAccount(raw, "x".repeat(32)), null);
});

test("подписанную куку другого назначения за сессию не выдать", () => {
  const profileCookie = sealCookieValue({ fn: "Анна", method: "oidc", aid: id }, secret);
  assert.equal(openClientAccount(profileCookie, secret), null);
  const badId = sealCookieValue({ kind: "client_account", aid: "../../etc" }, secret);
  assert.equal(openClientAccount(badId, secret), null);
});

test("кука истекает через 7 дней", () => {
  const issued = 1_000_000;
  const raw = sealClientAccount({ accountId: id, email: null, name: null }, secret, issued);
  assert.ok(openClientAccount(raw, secret, issued + 6 * 86400));
  assert.equal(openClientAccount(raw, secret, issued + 8 * 86400), null);
});

test("проверка куки: пусто, нет секрета, истекла", () => {
  assert.equal(checkClientAccountCookie({ cookie: "", secret }).status, 401);
  assert.equal(checkClientAccountCookie({ cookie: "x.y", secret: "" }).status, 500);
  const raw = sealClientAccount({ accountId: id, email: null, name: null }, secret);
  assert.deepEqual(checkClientAccountCookie({ cookie: raw, secret }), { ok: true, accountId: id });
});

test("в ядро уходит один идентификатор: Telegram или учётная запись", () => {
  assert.deepEqual(clientFields({ telegramUserId: 42, accountId: null }), { telegram_user_id: 42 });
  assert.equal(clientQuery({ telegramUserId: 42, accountId: null }), "telegram_user_id=42");
  assert.deepEqual(clientFields({ telegramUserId: null, accountId: id }), { client_account_id: id });
  assert.equal(clientQuery({ telegramUserId: null, accountId: id }), `client_account_id=${id}`);
  assert.notEqual(clientKey({ telegramUserId: 42, accountId: null }), clientKey({ telegramUserId: null, accountId: "42" }));
});
