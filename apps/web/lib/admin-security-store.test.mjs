import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

import {
  clearLoginAttempts,
  createAdminSessionRecord,
  getAdminSessionRecord,
  getLoginBlockInfo,
  registerFailedLogin,
  revokeAllAdminSessions,
  revokeAdminSessionRecord,
} from "./admin-security-store.ts";

const throttleOptions = {
  authWindowSeconds: 60,
  authBlockSeconds: 120,
  authMaxAttempts: 3,
};

function withTempStore(run) {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "web-admin-security-"));
  const previousPath = process.env.ADMIN_SECURITY_STORE_PATH;
  process.env.ADMIN_SECURITY_STORE_PATH = path.join(tempDir, "store.json");
  try {
    run();
  } finally {
    if (previousPath === undefined) {
      delete process.env.ADMIN_SECURITY_STORE_PATH;
    } else {
      process.env.ADMIN_SECURITY_STORE_PATH = previousPath;
    }
    rmSync(tempDir, { recursive: true, force: true });
  }
}

test("login throttling is persisted and blocks after configured limit", () => {
  withTempStore(() => {
    const nowMs = Date.UTC(2026, 2, 10, 10, 0, 0);
    assert.equal(registerFailedLogin("client-a", nowMs, throttleOptions), null);
    assert.equal(registerFailedLogin("client-a", nowMs + 1_000, throttleOptions), null);

    const blocked = registerFailedLogin("client-a", nowMs + 2_000, throttleOptions);
    assert.equal(blocked, 120);
    assert.equal(getLoginBlockInfo("client-a", nowMs + 3_000, throttleOptions), 119);

    clearLoginAttempts("client-a");
    assert.equal(getLoginBlockInfo("client-a", nowMs + 4_000, throttleOptions), null);
  });
});

test("admin sessions can be revoked individually and in bulk", () => {
  withTempStore(() => {
    const nowMs = Date.UTC(2026, 2, 10, 11, 0, 0);
    createAdminSessionRecord({
      sessionId: "session-1",
      createdAtMs: nowMs,
      expiresAtMs: nowMs + 60_000,
      ipHash: "ip-1",
      userAgentHash: "ua-1",
      maxConcurrentSessions: 4,
    });
    createAdminSessionRecord({
      sessionId: "session-2",
      createdAtMs: nowMs + 1_000,
      expiresAtMs: nowMs + 60_000,
      ipHash: "ip-2",
      userAgentHash: "ua-2",
      maxConcurrentSessions: 4,
    });

    assert.ok(getAdminSessionRecord("session-1", nowMs + 2_000));
    revokeAdminSessionRecord("session-1", nowMs + 3_000, "manual_test");
    assert.equal(getAdminSessionRecord("session-1", nowMs + 4_000), null);

    const revoked = revokeAllAdminSessions(nowMs + 5_000, "incident_response");
    assert.equal(revoked, 1);
    assert.equal(getAdminSessionRecord("session-2", nowMs + 6_000), null);
  });
});
