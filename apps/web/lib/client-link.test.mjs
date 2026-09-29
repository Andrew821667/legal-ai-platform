import assert from "node:assert/strict";
import { test } from "node:test";

import { cleanLinkCode, LINK_FRESH_SECONDS, maskEmail, readBothSessions } from "./client-link.ts";
import { mintClientSessionToken, sealClientAccount } from "./client-session.ts";

const secret = "s".repeat(32);
const id = "0b6f6f0e-8f4a-4d7e-9a61-2f6d1c0a9b11";
const now = 2_000_000;

function cookies(telegramAt, accountAt) {
  return {
    sessionCookie: mintClientSessionToken(777, secret, telegramAt),
    accountCookie: sealClientAccount({ accountId: id, email: "anna@ya.ru", name: "Анна" }, secret, accountAt),
    secret,
    now,
  };
}

test("обе сессии свежие — объединять можно", () => {
  const both = readBothSessions(cookies(now - 60, now - 30));
  assert.deepEqual(both, {
    telegramUserId: 777,
    accountId: id,
    email: "anna@ya.ru",
    telegramFresh: true,
    accountFresh: true,
  });
});

test("вход старше 15 минут — не свежий: на общем компьютере мог остаться чужой", () => {
  const stale = readBothSessions(cookies(now - LINK_FRESH_SECONDS - 1, now - 30));
  assert.equal(stale.telegramFresh, false);
  assert.equal(stale.accountFresh, true);
  assert.equal(readBothSessions(cookies(now - 30, now - LINK_FRESH_SECONDS - 1)).accountFresh, false);
});

test("нет одной из сессий или чужой секрет — объединять не по чему", () => {
  const input = cookies(now - 60, now - 30);
  assert.equal(readBothSessions({ ...input, sessionCookie: "" }), null);
  assert.equal(readBothSessions({ ...input, accountCookie: "" }), null);
  assert.equal(readBothSessions({ ...input, secret: "x".repeat(32) }), null);
  assert.equal(readBothSessions({ ...input, secret: "" }), null);
});

test("код и почта для показа", () => {
  assert.equal(cleanLinkCode("  k7m4-x9pq "), "k7m4-x9pq");
  assert.equal(cleanLinkCode(42), "");
  assert.equal(cleanLinkCode("A".repeat(100)).length, 32);
  assert.equal(maskEmail("anna@yandex.ru"), "a***@yandex.ru");
  assert.equal(maskEmail(null), "");
});
