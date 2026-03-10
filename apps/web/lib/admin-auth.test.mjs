import test from "node:test";
import assert from "node:assert/strict";

import {
  generateTotpCode,
  generateTotpSecret,
  hashAdminPassword,
  resolveAdminClientContext,
  verifyAdminPassword,
  verifyTotpCode,
} from "./admin-auth.ts";

test("hashAdminPassword verifies correct password and rejects wrong one", () => {
  const hash = hashAdminPassword("S3curePassword!");
  assert.ok(hash.startsWith("$2"));
  assert.equal(verifyAdminPassword("S3curePassword!", hash), true);
  assert.equal(verifyAdminPassword("wrong-password", hash), false);
});

test("TOTP verification accepts current code within allowed window", () => {
  const secret = generateTotpSecret();
  const nowMs = Date.UTC(2026, 2, 10, 12, 0, 0);
  const code = generateTotpCode(secret, nowMs);

  assert.equal(verifyTotpCode(secret, code, nowMs, 1), true);
  assert.equal(verifyTotpCode(secret, code, nowMs + 31_000, 0), false);
  assert.equal(verifyTotpCode(secret, code, nowMs + 25_000, 1), true);
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
