import { createHmac, timingSafeEqual } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

export const TELEGRAM_INIT_DATA_HEADER = "x-telegram-init-data";

const DEFAULT_MAX_AGE_SECONDS = 60 * 60;

type TelegramWebAppUser = {
  id?: unknown;
};

type VerificationResult = {
  telegramUserId: number;
};

function buildDataCheckString(params: URLSearchParams): string {
  const rows: string[] = [];
  params.forEach((value, key) => {
    if (key === "hash") {
      return;
    }
    rows.push(`${key}=${value}`);
  });
  rows.sort();
  return rows.join("\n");
}

function getAuthMaxAgeSeconds(): number {
  const parsed = Number(process.env.MINIAPP_TELEGRAM_AUTH_MAX_AGE_SECONDS || DEFAULT_MAX_AGE_SECONDS);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_MAX_AGE_SECONDS;
  }
  return Math.round(parsed);
}

function getMiniAppBotToken(): string {
  return (process.env.READER_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "").trim();
}

function allowUnverifiedMiniAppAuth(): boolean {
  return process.env.MINIAPP_ALLOW_UNVERIFIED === "1";
}

function requireMiniAppTelegramAuth(): boolean {
  const raw = String(process.env.MINIAPP_REQUIRE_TELEGRAM_AUTH || "").trim().toLowerCase();
  if (!raw) {
    return true;
  }
  return raw !== "0" && raw !== "false" && raw !== "no";
}

function parseTelegramUserId(rawUser: string | null): number | null {
  if (!rawUser) {
    return null;
  }
  let parsed: TelegramWebAppUser;
  try {
    parsed = JSON.parse(rawUser) as TelegramWebAppUser;
  } catch {
    return null;
  }
  const value = Number(parsed.id);
  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }
  return value;
}

export function verifyTelegramWebAppInitData(initData: string, botToken: string): VerificationResult | null {
  const params = new URLSearchParams(initData);
  const hash = (params.get("hash") || "").trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(hash)) {
    return null;
  }

  const authDateRaw = Number(params.get("auth_date") || "0");
  if (!Number.isFinite(authDateRaw) || authDateRaw <= 0) {
    return null;
  }

  const now = Math.floor(Date.now() / 1000);
  const maxAgeSeconds = getAuthMaxAgeSeconds();
  if (authDateRaw > now + 60 || now - authDateRaw > maxAgeSeconds) {
    return null;
  }

  const telegramUserId = parseTelegramUserId(params.get("user"));
  if (!telegramUserId) {
    return null;
  }

  const dataCheckString = buildDataCheckString(params);
  const secretKey = createHmac("sha256", "WebAppData").update(botToken).digest();
  const expectedHash = createHmac("sha256", secretKey).update(dataCheckString).digest("hex");

  const expectedBytes = Buffer.from(expectedHash, "hex");
  const providedBytes = Buffer.from(hash, "hex");
  if (expectedBytes.length !== providedBytes.length) {
    return null;
  }
  if (!timingSafeEqual(expectedBytes, providedBytes)) {
    return null;
  }

  return { telegramUserId };
}

export type MiniAppAuthContext = {
  verifiedTelegramUserId: number | null;
};

export function verifyMiniAppRequest(request: NextRequest): MiniAppAuthContext | NextResponse {
  const initData = (request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "").trim();
  const botToken = getMiniAppBotToken();
  const allowUnverified = allowUnverifiedMiniAppAuth();
  const requireAuth = requireMiniAppTelegramAuth();

  if (!initData) {
    if (allowUnverified || !requireAuth) {
      return { verifiedTelegramUserId: null };
    }
    return NextResponse.json(
      { detail: "Telegram WebApp initData header is required" },
      { status: 401 },
    );
  }

  if (!botToken) {
    if (allowUnverified || !requireAuth) {
      return { verifiedTelegramUserId: null };
    }
    return NextResponse.json(
      { detail: "READER_BOT_TOKEN or TELEGRAM_BOT_TOKEN is not configured on web server" },
      { status: 500 },
    );
  }

  const verification = verifyTelegramWebAppInitData(initData, botToken);
  if (!verification) {
    if (allowUnverified || !requireAuth) {
      return { verifiedTelegramUserId: null };
    }
    return NextResponse.json(
      { detail: "Invalid Telegram WebApp initData" },
      { status: 401 },
    );
  }

  return { verifiedTelegramUserId: verification.telegramUserId };
}

export function ensureTelegramUserMatch(
  context: MiniAppAuthContext,
  requestedTelegramUserId: number,
): NextResponse | null {
  if (
    context.verifiedTelegramUserId !== null
    && context.verifiedTelegramUserId !== requestedTelegramUserId
  ) {
    return NextResponse.json(
      { detail: "telegram_user_id does not match verified Telegram user" },
      { status: 403 },
    );
  }
  return null;
}
