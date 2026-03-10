import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

export const ADMIN_SESSION_COOKIE_NAME = "legal_ai_admin_session";

const DEFAULT_TTL_SECONDS = 60 * 60 * 8;

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

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("hex");
}

export function createAdminSessionToken(): string | null {
  const secret = getAdminSessionSecret();
  if (!secret) {
    return null;
  }
  const expiresAt = Math.floor(Date.now() / 1000) + getAdminSessionTtlSeconds();
  const nonce = randomBytes(16).toString("hex");
  const payload = `${expiresAt}.${nonce}`;
  const signature = sign(payload, secret);
  return `${payload}.${signature}`;
}

export function isAdminSessionTokenValid(token: string | undefined | null): boolean {
  if (!token) {
    return false;
  }
  const secret = getAdminSessionSecret();
  if (!secret) {
    return false;
  }

  const [expiresRaw, nonce, signature] = token.split(".");
  if (!expiresRaw || !nonce || !signature) {
    return false;
  }

  const expiresAt = Number(expiresRaw);
  if (!Number.isFinite(expiresAt) || expiresAt <= 0) {
    return false;
  }
  if (Math.floor(Date.now() / 1000) > expiresAt) {
    return false;
  }

  const payload = `${expiresRaw}.${nonce}`;
  const expected = sign(payload, secret);
  const expectedBytes = Buffer.from(expected);
  const signatureBytes = Buffer.from(signature);
  if (expectedBytes.length !== signatureBytes.length) {
    return false;
  }
  return timingSafeEqual(expectedBytes, signatureBytes);
}

export function attachAdminSessionCookie(response: NextResponse, token: string): void {
  response.cookies.set({
    name: ADMIN_SESSION_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
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
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
}

export function hasValidAdminSession(request: NextRequest): boolean {
  const token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)?.value;
  return isAdminSessionTokenValid(token);
}

export function requireAdminSession(request: NextRequest): NextResponse | null {
  if (hasValidAdminSession(request)) {
    return null;
  }
  return NextResponse.json({ detail: "Admin session required" }, { status: 401 });
}
