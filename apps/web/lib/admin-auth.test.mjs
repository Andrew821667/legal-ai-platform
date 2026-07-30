import test from "node:test";
import assert from "node:assert/strict";

import {
  hashAdminPassword,
  resolveAdminClientContext,
  verifyAdminPassword,
} from "./admin-auth.ts";

test("hashAdminPassword verifies correct password and rejects wrong one", () => {
  const hash = hashAdminPassword("S3curePassword!");
  assert.ok(hash.startsWith("$2"));
  assert.equal(verifyAdminPassword("S3curePassword!", hash), true);
  assert.equal(verifyAdminPassword("wrong-password", hash), false);
});

test("resolveAdminClientContext hashes IP and user agent without leaking raw values", () => {
  const headers = new Headers({
    "x-forwarded-for": "203.0.113.25, 10.0.0.1",
    "user-agent": "Mozilla/5.0 Test Agent",
  });

  const context = resolveAdminClientContext(headers);

  assert.match(context.ipHash, /^[a-f0-9]{64}$/);
  assert.match(context.userAgentHash, /^[a-f0-9]{64}$/);
  assert.match(context.clientKey, /^[a-f0-9]{64}$/);
  assert.notEqual(context.ipHash.includes("203.0.113.25"), true);
});

test("spoofed X-Forwarded-For entries cannot change the throttling key", () => {
  // Всё, кроме последнего элемента, присылает сам клиент. Один и тот же
  // отправитель, подставляющий разные значения, должен получать один ключ,
  // иначе лимит попыток входа обходится сменой заголовка на каждом запросе.
  const attempt = (spoofed) =>
    resolveAdminClientContext(
      new Headers({
        "x-forwarded-for": `${spoofed}, 198.51.100.7`,
        "user-agent": "Mozilla/5.0 Test Agent",
      }),
    ).clientKey;

  assert.equal(attempt("203.0.113.25"), attempt("203.0.113.99"));
  assert.equal(attempt("203.0.113.25"), attempt("not-an-ip"));
});

test("changing the user agent cannot change the throttling key", () => {
  // User-Agent подменяется одной строкой, поэтому в ключ он не входит.
  const attempt = (userAgent) =>
    resolveAdminClientContext(
      new Headers({ "x-forwarded-for": "198.51.100.7", "user-agent": userAgent }),
    ).clientKey;

  assert.equal(attempt("Mozilla/5.0 Test Agent"), attempt("curl/8.0"));
});

test("different real clients still get different throttling keys", () => {
  // Обратная проверка: троттлинг не должен склеивать всех в один ключ,
  // иначе перебор с одного адреса заблокировал бы посторонних.
  const first = resolveAdminClientContext(
    new Headers({ "x-forwarded-for": "198.51.100.7" }),
  ).clientKey;
  const second = resolveAdminClientContext(
    new Headers({ "x-forwarded-for": "198.51.100.8" }),
  ).clientKey;

  assert.notEqual(first, second);
});

test("x-real-ip is used when x-forwarded-for is absent", () => {
  const context = resolveAdminClientContext(
    new Headers({ "x-real-ip": "198.51.100.7" }),
  );
  const viaForwarded = resolveAdminClientContext(
    new Headers({ "x-forwarded-for": "198.51.100.7" }),
  );

  assert.equal(context.clientKey, viaForwarded.clientKey);
});
