import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import { resolveAdminClientContext } from "@/lib/admin-auth";
import {
  appendAdminAuditEvent,
  createAdminSessionRecord,
  getAdminSessionRecord,
  revokeAdminSessionRecord,
  revokeAllAdminSessions,
  touchAdminSessionRecord,
} from "@/lib/admin-security-store";

export const ADMIN_SESSION_COOKIE_NAME = "legal_ai_admin_session";

const DEFAULT_TTL_SECONDS = 60 * 60 * 8;
const DEFAULT_MAX_CONCURRENT = 2;
const DEFAULT_TOUCH_INTERVAL_SECONDS = 60;

type SessionTokenPayload = {
  expiresAt: number;
  nonce: string;
  sessionId: string;
};

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const parsed = Number(raw || "");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.round(parsed);
}

function getAdminSessionSecret(): string {
  return (process.env.ADMIN_PANEL_SESSION_SECRET || "").trim();
}

function getAdminSessionTtlSeconds(): number {
  const parsed = Number(process.env.ADMIN_PANEL_SESSION_TTL_SECONDS || DEFAULT_TTL_SECONDS);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_TTL_SECONDS;
  }
  return Math.round(parsed);
}

function getAdminSessionMaxConcurrent(): number {
  return parsePositiveInt(process.env.ADMIN_SESSION_MAX_CONCURRENT, DEFAULT_MAX_CONCURRENT);
}

function getAdminSessionTouchIntervalSeconds(): number {
  return parsePositiveInt(process.env.ADMIN_SESSION_TOUCH_INTERVAL_SECONDS, DEFAULT_TOUCH_INTERVAL_SECONDS);
}

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("hex");
}

function parseAdminSessionToken(token: string | undefined | null): SessionTokenPayload | null {
  if (!token) {
    return null;
  }
  const secret = getAdminSessionSecret();
  if (!secret) {
    return null;
  }

  const [sessionId, expiresRaw, nonce, signature] = token.split(".");
  if (!sessionId || !expiresRaw || !nonce || !signature) {
    return null;
  }

  const expiresAt = Number(expiresRaw);
  if (!Number.isFinite(expiresAt) || expiresAt <= 0) {
    return null;
  }

  const payload = `${sessionId}.${expiresRaw}.${nonce}`;
  const expected = sign(payload, secret);
  const expectedBytes = Buffer.from(expected);
  const signatureBytes = Buffer.from(signature);
  if (expectedBytes.length !== signatureBytes.length) {
    return null;
  }
  if (!timingSafeEqual(expectedBytes, signatureBytes)) {
    return null;
  }

  if (Math.floor(Date.now() / 1000) > expiresAt) {
    return null;
  }

  return {
    sessionId,
    expiresAt,
    nonce,
  };
}

export function createAdminSessionToken(input: {
  ipHash: string;
  userAgentHash: string;
}): { token: string; sessionId: string } | null {
  const secret = getAdminSessionSecret();
  if (!secret) {
    return null;
  }

  const createdAtMs = Date.now();
  const expiresAt = Math.floor(createdAtMs / 1000) + getAdminSessionTtlSeconds();
  const sessionId = randomBytes(18).toString("base64url");
  const nonce = randomBytes(12).toString("base64url");
  const payload = `${sessionId}.${expiresAt}.${nonce}`;
  const signature = sign(payload, secret);

  createAdminSessionRecord({
    sessionId,
    createdAtMs,
    expiresAtMs: expiresAt * 1000,
    ipHash: input.ipHash,
    userAgentHash: input.userAgentHash,
    maxConcurrentSessions: getAdminSessionMaxConcurrent(),
  });

  return {
    token: `${payload}.${signature}`,
    sessionId,
  };
}

export function attachAdminSessionCookie(response: NextResponse, token: string): void {
  response.cookies.set({
    name: ADMIN_SESSION_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: getAdminSessionTtlSeconds(),
  });
}

export function clearAdminSessionCookie(response: NextResponse): void {
  response.cookies.set({
    name: ADMIN_SESSION_COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
}

export function hasValidAdminSession(request: NextRequest): boolean {
  const token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)?.value;
  const parsed = parseAdminSessionToken(token);
  if (!parsed) {
    return false;
  }

  const nowMs = Date.now();
  const record = getAdminSessionRecord(parsed.sessionId, nowMs);
  if (!record) {
    return false;
  }

  const touchAfterMs = getAdminSessionTouchIntervalSeconds() * 1000;
  if (nowMs - record.lastSeenAtMs >= touchAfterMs) {
    touchAdminSessionRecord(parsed.sessionId, nowMs);
  }
  return true;
}

export function requireAdminSession(request: NextRequest): NextResponse | null {
  if (hasValidAdminSession(request)) {
    return null;
  }
  return NextResponse.json({ detail: "Admin session required" }, { status: 401 });
}

export function revokeCurrentAdminSession(
  request: NextRequest,
  reason: string,
): { revoked: boolean; sessionId: string | null } {
  const token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)?.value;
  const parsed = parseAdminSessionToken(token);
  if (!parsed) {
    return { revoked: false, sessionId: null };
  }

  revokeAdminSessionRecord(parsed.sessionId, Date.now(), reason);
  return { revoked: true, sessionId: parsed.sessionId };
}

export function revokeAllOtherAdminSessions(request: NextRequest, reason: string): number {
  const token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)?.value;
  const parsed = parseAdminSessionToken(token);
  return revokeAllAdminSessions(Date.now(), reason, parsed?.sessionId);
}

export function auditAdminSessionEvent(
  request: NextRequest,
  type: string,
  outcome: string,
  detail?: string,
  sessionId?: string,
): void {
  const client = resolveAdminClientContext(request.headers);
  appendAdminAuditEvent({
    id: randomBytes(12).toString("hex"),
    createdAtMs: Date.now(),
    type,
    outcome,
    detail,
    sessionId,
    ipHash: client.ipHash,
    userAgentHash: client.userAgentHash,
  });
}
