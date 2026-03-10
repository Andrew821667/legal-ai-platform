import { NextRequest, NextResponse } from "next/server";

import {
  normalizeTotpCode,
  resolveAdminClientContext,
  verifyAdminPassword,
  verifyTotpCode,
} from "@/lib/admin-auth";
import {
  appendAdminAuditEvent,
  clearLoginAttempts,
  getLoginBlockInfo,
  registerFailedLogin,
} from "@/lib/admin-security-store";
import {
  attachAdminSessionCookie,
  auditAdminSessionEvent,
  clearAdminSessionCookie,
  createAdminSessionToken,
  hasValidAdminSession,
  revokeAllOtherAdminSessions,
  revokeCurrentAdminSession,
} from "@/lib/admin-session";

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const parsed = Number(raw || "");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.round(parsed);
}

const AUTH_WINDOW_SECONDS = parsePositiveInt(process.env.ADMIN_AUTH_WINDOW_SECONDS, 15 * 60);
const AUTH_BLOCK_SECONDS = parsePositiveInt(process.env.ADMIN_AUTH_BLOCK_SECONDS, 15 * 60);
const AUTH_MAX_ATTEMPTS = parsePositiveInt(process.env.ADMIN_AUTH_MAX_ATTEMPTS, 10);
const TOTP_WINDOW_STEPS = parsePositiveInt(process.env.ADMIN_PANEL_TOTP_WINDOW_STEPS, 1);

function getConfiguredPasswordHash(): string {
  return String(process.env.ADMIN_PANEL_PASSWORD_HASH || "").trim();
}

function getConfiguredTotpSecret(): string {
  return String(process.env.ADMIN_PANEL_TOTP_SECRET || "").trim();
}

function getThrottleOptions() {
  return {
    authWindowSeconds: AUTH_WINDOW_SECONDS,
    authBlockSeconds: AUTH_BLOCK_SECONDS,
    authMaxAttempts: AUTH_MAX_ATTEMPTS,
  };
}

export async function GET(request: NextRequest) {
  if (!hasValidAdminSession(request)) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }
  return NextResponse.json({ ok: true, can_revoke_all: true }, { status: 200 });
}

export async function POST(request: NextRequest) {
  const client = resolveAdminClientContext(request.headers);
  const nowMs = Date.now();
  const blockedForSeconds = getLoginBlockInfo(client.clientKey, nowMs, getThrottleOptions());
  if (blockedForSeconds !== null) {
    auditAdminSessionEvent(request, "admin_login_blocked", "blocked", "rate_limited");
    return NextResponse.json(
      {
        detail: "Слишком много неуспешных попыток входа. Повторите позже.",
        retry_after_seconds: blockedForSeconds,
      },
      {
        status: 429,
        headers: {
          "Retry-After": String(blockedForSeconds),
        },
      },
    );
  }

  const configuredPasswordHash = getConfiguredPasswordHash();
  const configuredSessionSecret = String(process.env.ADMIN_PANEL_SESSION_SECRET || "").trim();
  const configuredTotpSecret = getConfiguredTotpSecret();

  if (!configuredPasswordHash) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_PASSWORD_HASH не настроен на сервере" },
      { status: 500 },
    );
  }
  if (!configuredSessionSecret) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_SESSION_SECRET не настроен на сервере" },
      { status: 500 },
    );
  }
  if (!configuredTotpSecret) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_TOTP_SECRET не настроен на сервере" },
      { status: 500 },
    );
  }

  let payload: { password?: string; totp?: string };
  try {
    payload = (await request.json()) as { password?: string; totp?: string };
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const password = typeof payload.password === "string" ? payload.password : "";
  const totp = typeof payload.totp === "string" ? normalizeTotpCode(payload.totp) : "";

  if (!password) {
    return NextResponse.json({ detail: "Пароль не передан" }, { status: 400 });
  }
  if (!totp) {
    return NextResponse.json({ detail: "TOTP код не передан" }, { status: 400 });
  }

  if (!verifyAdminPassword(password, configuredPasswordHash)) {
    const retryAfterSeconds = registerFailedLogin(client.clientKey, nowMs, getThrottleOptions());
    appendAdminAuditEvent({
      id: `${nowMs}-password`,
      createdAtMs: nowMs,
      type: "admin_login",
      outcome: retryAfterSeconds !== null ? "blocked" : "denied",
      detail: "password_hash_mismatch",
      ipHash: client.ipHash,
      userAgentHash: client.userAgentHash,
    });
    if (retryAfterSeconds !== null) {
      return NextResponse.json(
        {
          detail: "Слишком много неуспешных попыток входа. Повторите позже.",
          retry_after_seconds: retryAfterSeconds,
        },
        {
          status: 429,
          headers: {
            "Retry-After": String(retryAfterSeconds),
          },
        },
      );
    }
    return NextResponse.json({ detail: "Неверные учетные данные" }, { status: 401 });
  }

  if (!verifyTotpCode(configuredTotpSecret, totp, nowMs, TOTP_WINDOW_STEPS)) {
    const retryAfterSeconds = registerFailedLogin(client.clientKey, nowMs, getThrottleOptions());
    appendAdminAuditEvent({
      id: `${nowMs}-totp`,
      createdAtMs: nowMs,
      type: "admin_login",
      outcome: retryAfterSeconds !== null ? "blocked" : "denied",
      detail: "totp_mismatch",
      ipHash: client.ipHash,
      userAgentHash: client.userAgentHash,
    });
    if (retryAfterSeconds !== null) {
      return NextResponse.json(
        {
          detail: "Слишком много неуспешных попыток входа. Повторите позже.",
          retry_after_seconds: retryAfterSeconds,
        },
        {
          status: 429,
          headers: {
            "Retry-After": String(retryAfterSeconds),
          },
        },
      );
    }
    return NextResponse.json({ detail: "Неверные учетные данные" }, { status: 401 });
  }

  const session = createAdminSessionToken({
    ipHash: client.ipHash,
    userAgentHash: client.userAgentHash,
  });
  if (!session) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_SESSION_SECRET is not configured on server" },
      { status: 500 },
    );
  }

  clearLoginAttempts(client.clientKey);
  const response = NextResponse.json({ ok: true }, { status: 200 });
  attachAdminSessionCookie(response, session.token);
  auditAdminSessionEvent(request, "admin_login", "success", "authenticated", session.sessionId);
  return response;
}

export async function DELETE(request: NextRequest) {
  let scope = "current";
  try {
    const payload = (await request.json()) as { scope?: string };
    scope = typeof payload.scope === "string" ? payload.scope : "current";
  } catch {
    scope = request.nextUrl.searchParams.get("scope") || "current";
  }

  const response = NextResponse.json({ ok: true, scope }, { status: 200 });
  if (scope === "all") {
    if (!hasValidAdminSession(request)) {
      return NextResponse.json({ detail: "Admin session required" }, { status: 401 });
    }
    const revoked = revokeAllOtherAdminSessions(request, "logout_all");
    auditAdminSessionEvent(request, "admin_logout", "success", `revoked_all:${revoked}`);
    return NextResponse.json({ ok: true, scope: "all", revoked_sessions: revoked }, { status: 200 });
  }

  const revoked = revokeCurrentAdminSession(request, "logout_current");
  auditAdminSessionEvent(request, "admin_logout", revoked.revoked ? "success" : "noop", scope, revoked.sessionId || undefined);
  clearAdminSessionCookie(response);
  return response;
}
