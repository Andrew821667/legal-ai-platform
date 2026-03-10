import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";

export type LoginAttemptRecord = {
  failedAttempts: number;
  firstFailedAtMs: number;
  blockedUntilMs: number;
  updatedAtMs: number;
};

export type AdminSessionRecord = {
  sessionId: string;
  createdAtMs: number;
  lastSeenAtMs: number;
  expiresAtMs: number;
  revokedAtMs: number | null;
  revokeReason: string | null;
  ipHash: string;
  userAgentHash: string;
};

export type AdminAuditEvent = {
  id: string;
  createdAtMs: number;
  type: string;
  ipHash: string;
  userAgentHash: string;
  sessionId?: string;
  outcome?: string;
  detail?: string;
};

type AdminSecurityStore = {
  version: 1;
  loginAttempts: Record<string, LoginAttemptRecord>;
  sessions: Record<string, AdminSessionRecord>;
  auditEvents: AdminAuditEvent[];
};

type LoginThrottleOptions = {
  authWindowSeconds: number;
  authBlockSeconds: number;
  authMaxAttempts: number;
};

const STORE_RETENTION_MS = 30 * 24 * 60 * 60 * 1000;
const DEFAULT_AUDIT_LIMIT = 500;

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const parsed = Number(raw || "");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.round(parsed);
}

function getAuditLimit(): number {
  return parsePositiveInt(process.env.ADMIN_SECURITY_AUDIT_LIMIT, DEFAULT_AUDIT_LIMIT);
}

function getStorePath(): string {
  const configured = String(process.env.ADMIN_SECURITY_STORE_PATH || "").trim();
  if (configured) {
    return configured;
  }
  return path.join(process.cwd(), ".data", "web-admin-security.json");
}

function createEmptyStore(): AdminSecurityStore {
  return {
    version: 1,
    loginAttempts: {},
    sessions: {},
    auditEvents: [],
  };
}

function ensureStoreDirectory(filePath: string): void {
  const directory = path.dirname(filePath);
  if (!existsSync(directory)) {
    mkdirSync(directory, { recursive: true, mode: 0o700 });
  }
}

function loadStore(): AdminSecurityStore {
  const filePath = getStorePath();
  if (!existsSync(filePath)) {
    return createEmptyStore();
  }

  const raw = readFileSync(filePath, "utf-8");
  const parsed = JSON.parse(raw) as Partial<AdminSecurityStore> | null;
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Admin security store is corrupted");
  }

  return {
    version: 1,
    loginAttempts: parsed.loginAttempts && typeof parsed.loginAttempts === "object"
      ? parsed.loginAttempts
      : {},
    sessions: parsed.sessions && typeof parsed.sessions === "object"
      ? parsed.sessions
      : {},
    auditEvents: Array.isArray(parsed.auditEvents) ? parsed.auditEvents : [],
  };
}

function saveStore(store: AdminSecurityStore): void {
  const filePath = getStorePath();
  ensureStoreDirectory(filePath);
  const tmpPath = `${filePath}.tmp`;
  writeFileSync(tmpPath, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });
  renameSync(tmpPath, filePath);
}

function pruneStore(store: AdminSecurityStore, nowMs: number, options?: LoginThrottleOptions): void {
  const staleAttemptsAgeMs = options
    ? Math.max(options.authWindowSeconds, options.authBlockSeconds) * 1000
    : 24 * 60 * 60 * 1000;

  for (const [key, row] of Object.entries(store.loginAttempts)) {
    if (row.blockedUntilMs > nowMs) {
      continue;
    }
    if (nowMs - row.updatedAtMs > staleAttemptsAgeMs) {
      delete store.loginAttempts[key];
    }
  }

  for (const [sessionId, row] of Object.entries(store.sessions)) {
    const revokeAt = row.revokedAtMs ?? row.expiresAtMs;
    if (revokeAt < nowMs - STORE_RETENTION_MS) {
      delete store.sessions[sessionId];
    }
  }

  const auditLimit = getAuditLimit();
  if (store.auditEvents.length > auditLimit) {
    store.auditEvents = store.auditEvents.slice(-auditLimit);
  }
}

function withStore<T>(
  mutator: (store: AdminSecurityStore) => T,
  options?: LoginThrottleOptions,
  clockMs?: number,
): T {
  const nowMs = clockMs ?? Date.now();
  const store = loadStore();
  pruneStore(store, nowMs, options);
  const result = mutator(store);
  saveStore(store);
  return result;
}

export function appendAdminAuditEvent(event: AdminAuditEvent): void {
  withStore((store) => {
    store.auditEvents.push(event);
  });
}

export function getLoginBlockInfo(
  clientKey: string,
  nowMs: number,
  options: LoginThrottleOptions,
): number | null {
  return withStore((store) => {
    const row = store.loginAttempts[clientKey];
    if (!row || row.blockedUntilMs <= nowMs) {
      return null;
    }
    return Math.max(1, Math.ceil((row.blockedUntilMs - nowMs) / 1000));
  }, options, nowMs);
}

export function registerFailedLogin(
  clientKey: string,
  nowMs: number,
  options: LoginThrottleOptions,
): number | null {
  return withStore((store) => {
    const windowMs = options.authWindowSeconds * 1000;
    const blockMs = options.authBlockSeconds * 1000;
    const current = store.loginAttempts[clientKey];
    const row: LoginAttemptRecord = current && nowMs - current.firstFailedAtMs <= windowMs
      ? {
        failedAttempts: current.failedAttempts + 1,
        firstFailedAtMs: current.firstFailedAtMs,
        blockedUntilMs: current.blockedUntilMs,
        updatedAtMs: nowMs,
      }
      : {
        failedAttempts: 1,
        firstFailedAtMs: nowMs,
        blockedUntilMs: 0,
        updatedAtMs: nowMs,
      };

    if (row.failedAttempts >= options.authMaxAttempts) {
      row.blockedUntilMs = nowMs + blockMs;
    }

    store.loginAttempts[clientKey] = row;
    if (row.blockedUntilMs > nowMs) {
      return Math.max(1, Math.ceil((row.blockedUntilMs - nowMs) / 1000));
    }
    return null;
  }, options, nowMs);
}

export function clearLoginAttempts(clientKey: string): void {
  withStore((store) => {
    delete store.loginAttempts[clientKey];
  });
}

export function createAdminSessionRecord(input: {
  sessionId: string;
  createdAtMs: number;
  expiresAtMs: number;
  ipHash: string;
  userAgentHash: string;
  maxConcurrentSessions: number;
}): void {
  withStore((store) => {
    const activeSessions = Object.values(store.sessions)
      .filter((row) => row.revokedAtMs === null && row.expiresAtMs > input.createdAtMs)
      .sort((left, right) => left.createdAtMs - right.createdAtMs);

    while (activeSessions.length >= input.maxConcurrentSessions) {
      const oldest = activeSessions.shift();
      if (!oldest) {
        break;
      }
      const current = store.sessions[oldest.sessionId];
      if (current && current.revokedAtMs === null) {
        current.revokedAtMs = input.createdAtMs;
        current.revokeReason = "max_concurrent_sessions";
      }
    }

    store.sessions[input.sessionId] = {
      sessionId: input.sessionId,
      createdAtMs: input.createdAtMs,
      lastSeenAtMs: input.createdAtMs,
      expiresAtMs: input.expiresAtMs,
      revokedAtMs: null,
      revokeReason: null,
      ipHash: input.ipHash,
      userAgentHash: input.userAgentHash,
    };
  });
}

export function getAdminSessionRecord(sessionId: string, nowMs: number): AdminSessionRecord | null {
  return withStore((store) => {
    const row = store.sessions[sessionId];
    if (!row) {
      return null;
    }
    if (row.revokedAtMs !== null || row.expiresAtMs <= nowMs) {
      return null;
    }
    return row;
  }, undefined, nowMs);
}

export function touchAdminSessionRecord(sessionId: string, nowMs: number): void {
  withStore((store) => {
    const row = store.sessions[sessionId];
    if (!row || row.revokedAtMs !== null || row.expiresAtMs <= nowMs) {
      return;
    }
    row.lastSeenAtMs = nowMs;
  }, undefined, nowMs);
}

export function revokeAdminSessionRecord(
  sessionId: string,
  nowMs: number,
  reason: string,
): void {
  withStore((store) => {
    const row = store.sessions[sessionId];
    if (!row || row.revokedAtMs !== null) {
      return;
    }
    row.revokedAtMs = nowMs;
    row.revokeReason = reason;
  }, undefined, nowMs);
}

export function revokeAllAdminSessions(
  nowMs: number,
  reason: string,
  exceptSessionId?: string,
): number {
  return withStore((store) => {
    let revoked = 0;
    for (const row of Object.values(store.sessions)) {
      if (row.sessionId === exceptSessionId) {
        continue;
      }
      if (row.revokedAtMs !== null || row.expiresAtMs <= nowMs) {
        continue;
      }
      row.revokedAtMs = nowMs;
      row.revokeReason = reason;
      revoked += 1;
    }
    return revoked;
  }, undefined, nowMs);
}
