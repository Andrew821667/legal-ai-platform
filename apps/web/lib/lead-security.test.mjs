import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";

import {
  __resetLeadSecurityStateForTests,
  evaluateLeadSubmission,
  normalizeLeadContact,
  recordLeadAttempt,
  rememberAcceptedLeadFingerprint,
  verifyTurnstileToken,
} from "./lead-security.ts";

const BASE_CONFIG = {
  honeypotField: "company_website",
  minSubmitSeconds: 4,
  ipMaxAttempts: 2,
  ipWindowSeconds: 60,
  contactMaxAttempts: 3,
  contactWindowSeconds: 3600,
  challengeMode: "off",
  turnstileSecretKey: "",
};

beforeEach(() => {
  __resetLeadSecurityStateForTests();
});

test("honeypot submission is silently dropped", () => {
  const result = evaluateLeadSubmission(
    {
      payload: {
        contact: "team@example.com",
        company_website: "https://spam.invalid",
        _started_at_ms: 1_800_000_000_000,
      },
      normalizedContact: normalizeLeadContact("team@example.com"),
      ip: "198.51.100.10",
      userAgent: "Mozilla/5.0",
      nowMs: 1_800_000_010_000,
    },
    BASE_CONFIG,
  );

  assert.equal(result.action, "silent_drop");
  assert.ok(result.reasonCodes.includes("honeypot_filled"));
});

test("too fast submission is silently dropped", () => {
  const result = evaluateLeadSubmission(
    {
      payload: {
        contact: "team@example.com",
        _started_at_ms: 1_800_000_000_000,
      },
      normalizedContact: normalizeLeadContact("team@example.com"),
      ip: "198.51.100.11",
      userAgent: "Mozilla/5.0",
      nowMs: 1_800_000_001_000,
    },
    BASE_CONFIG,
  );

  assert.equal(result.action, "silent_drop");
  assert.ok(result.reasonCodes.includes("submission_too_fast"));
});

test("ip rate limit blocks repeated requests", () => {
  const nowMs = 1_800_000_100_000;
  const baseInput = {
    payload: {
      contact: "team@example.com",
      _started_at_ms: nowMs - 10_000,
    },
    normalizedContact: normalizeLeadContact("team@example.com"),
    ip: "198.51.100.12",
    userAgent: "Mozilla/5.0",
  };

  const first = evaluateLeadSubmission({ ...baseInput, nowMs }, BASE_CONFIG);
  recordLeadAttempt(first, BASE_CONFIG, nowMs);

  const second = evaluateLeadSubmission({ ...baseInput, nowMs: nowMs + 1_000 }, BASE_CONFIG);
  recordLeadAttempt(second, BASE_CONFIG, nowMs + 1_000);

  const third = evaluateLeadSubmission({ ...baseInput, nowMs: nowMs + 2_000 }, BASE_CONFIG);

  assert.equal(first.action, "accept");
  assert.equal(second.action, "accept");
  assert.equal(third.action, "rate_limit");
  assert.ok(third.reasonCodes.includes("ip_rate_limited"));
});

test("accepted fingerprint is deduplicated", () => {
  const nowMs = 1_800_000_200_000;
  const input = {
    payload: {
      contact: "team@example.com",
      offer: "consultation",
      _started_at_ms: nowMs - 10_000,
    },
    normalizedContact: normalizeLeadContact("team@example.com"),
    ip: "198.51.100.13",
    userAgent: "Mozilla/5.0",
    nowMs,
  };

  const first = evaluateLeadSubmission(input, BASE_CONFIG);
  recordLeadAttempt(first, BASE_CONFIG, nowMs);
  rememberAcceptedLeadFingerprint(first.fingerprint, nowMs);

  const second = evaluateLeadSubmission({ ...input, nowMs: nowMs + 5_000 }, BASE_CONFIG);

  assert.equal(first.action, "accept");
  assert.equal(second.action, "duplicate");
  assert.ok(second.reasonCodes.includes("duplicate_fingerprint"));
});

test("adaptive challenge is required for suspicious requests", () => {
  const result = evaluateLeadSubmission(
    {
      payload: {
        contact: "team@example.com",
        _started_at_ms: 1_800_000_000_000,
      },
      normalizedContact: normalizeLeadContact("team@example.com"),
      ip: "198.51.100.14",
      userAgent: "curl/8.0.1",
      nowMs: 1_800_000_010_000,
    },
    {
      ...BASE_CONFIG,
      challengeMode: "adaptive",
      turnstileSecretKey: "turnstile-secret",
    },
  );

  assert.equal(result.action, "accept");
  assert.equal(result.requiresChallenge, true);
  assert.ok(result.reasonCodes.includes("suspicious_user_agent"));
});

test("turnstile verification returns success from upstream response", async () => {
  const ok = await verifyTurnstileToken(
    "token-123",
    "198.51.100.15",
    "turnstile-secret",
    async () =>
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );

  assert.equal(ok, true);
});
