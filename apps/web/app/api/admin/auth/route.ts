import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

import {
  attachAdminSessionCookie,
  clearAdminSessionCookie,
  createAdminSessionToken,
  hasValidAdminSession,
} from "@/lib/admin-session";

function safeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

type LoginAttemptRow = {
  failedAttempts: number;
  firstFailedAtMs: number;
  blockedUntilMs: number;
};

const LOGIN_ATTEMPTS = new Map<string, LoginAttemptRow>();
const MAX_TRACKED_LOGIN_KEYS = 10_000;

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

function resolveClientKey(request: NextRequest): string {
  const forwarded = String(request.headers.get("x-forwarded-for") || "").split(",")[0]?.trim();
  const real = String(request.headers.get("x-real-ip") || "").trim();
  const ip = forwarded || real || "unknown";
  return ip.slice(0, 120);
}

function pruneLoginAttempts(nowMs: number): void {
  const staleAgeMs = Math.max(AUTH_WINDOW_SECONDS, AUTH_BLOCK_SECONDS) * 1000;
  for (const [key, row] of LOGIN_ATTEMPTS) {
    if (row.blockedUntilMs > nowMs) {
      continue;
    }
    if (nowMs - row.firstFailedAtMs > staleAgeMs) {
      LOGIN_ATTEMPTS.delete(key);
    }
  }
  while (LOGIN_ATTEMPTS.size > MAX_TRACKED_LOGIN_KEYS) {
    const oldestKey = LOGIN_ATTEMPTS.keys().next().value;
    if (!oldestKey) {
      break;
    }
    LOGIN_ATTEMPTS.delete(oldestKey);
  }
}

function checkLoginBlocked(clientKey: string, nowMs: number): number | null {
  pruneLoginAttempts(nowMs);
  const row = LOGIN_ATTEMPTS.get(clientKey);
  if (!row || row.blockedUntilMs <= nowMs) {
    return null;
  }
  return Math.max(1, Math.ceil((row.blockedUntilMs - nowMs) / 1000));
}

function registerFailedLogin(clientKey: string, nowMs: number): number | null {
  const windowMs = AUTH_WINDOW_SECONDS * 1000;
  const blockMs = AUTH_BLOCK_SECONDS * 1000;
  const current = LOGIN_ATTEMPTS.get(clientKey);
  const row: LoginAttemptRow = current
    && nowMs - current.firstFailedAtMs <= windowMs
    ? {
      failedAttempts: current.failedAttempts + 1,
      firstFailedAtMs: current.firstFailedAtMs,
      blockedUntilMs: current.blockedUntilMs,
    }
    : {
      failedAttempts: 1,
      firstFailedAtMs: nowMs,
      blockedUntilMs: 0,
    };

  if (row.failedAttempts >= AUTH_MAX_ATTEMPTS) {
    row.blockedUntilMs = nowMs + blockMs;
  }

  LOGIN_ATTEMPTS.set(clientKey, row);
  if (row.blockedUntilMs > nowMs) {
    return Math.max(1, Math.ceil((row.blockedUntilMs - nowMs) / 1000));
  }
  return null;
}

function clearLoginAttempts(clientKey: string): void {
  LOGIN_ATTEMPTS.delete(clientKey);
}

export async function GET(request: NextRequest) {
  if (!hasValidAdminSession(request)) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }
  return NextResponse.json({ ok: true }, { status: 200 });
}

export async function POST(request: NextRequest) {
  const clientKey = resolveClientKey(request);
  const nowMs = Date.now();
  const blockedForSeconds = checkLoginBlocked(clientKey, nowMs);
  if (blockedForSeconds !== null) {
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

  const configuredPassword = process.env.ADMIN_PANEL_PASSWORD || "";
  const configuredSessionSecret = process.env.ADMIN_PANEL_SESSION_SECRET || "";

  if (!configuredPassword) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_PASSWORD не настроен на сервере" },
      { status: 500 },
    );
  }
  if (!configuredSessionSecret.trim()) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_SESSION_SECRET не настроен на сервере" },
      { status: 500 },
    );
  }

  let payload: { password?: string };
  try {
    payload = (await request.json()) as { password?: string };
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const password = typeof payload.password === "string" ? payload.password : "";
  if (!password) {
    return NextResponse.json({ detail: "Пароль не передан" }, { status: 400 });
  }

  if (!safeEqual(password, configuredPassword)) {
    const retryAfterSeconds = registerFailedLogin(clientKey, nowMs);
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
    return NextResponse.json({ detail: "Неверный пароль" }, { status: 401 });
  }

  const sessionToken = createAdminSessionToken();
  if (!sessionToken) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_SESSION_SECRET is not configured on server" },
      { status: 500 },
    );
  }

  clearLoginAttempts(clientKey);
  const response = NextResponse.json({ ok: true }, { status: 200 });
  attachAdminSessionCookie(response, sessionToken);
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true }, { status: 200 });
  clearAdminSessionCookie(response);
  return response;
}
