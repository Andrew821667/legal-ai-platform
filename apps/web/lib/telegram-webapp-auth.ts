import { NextRequest, NextResponse } from "next/server";

import {
  TELEGRAM_INIT_DATA_HEADER,
  getMiniAppBotTokens,
  verifyTelegramWebAppInitDataWithAny,
  allowUnverifiedMiniAppAuth,
  requireMiniAppTelegramAuth,
} from "@/lib/telegram-initdata";

export {
  TELEGRAM_INIT_DATA_HEADER,
  getMiniAppBotTokens,
  verifyTelegramWebAppInitData,
  verifyTelegramWebAppInitDataWithAny,
} from "@/lib/telegram-initdata";

export type MiniAppAuthContext = {
  verifiedTelegramUserId: number | null;
};

export function verifyMiniAppRequest(request: NextRequest): MiniAppAuthContext | NextResponse {
  const initData = (request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "").trim();
  const botTokens = getMiniAppBotTokens();
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

  if (botTokens.length === 0) {
    if (allowUnverified || !requireAuth) {
      return { verifiedTelegramUserId: null };
    }
    return NextResponse.json(
      { detail: "READER_BOT_TOKEN or TELEGRAM_BOT_TOKEN is not configured on web server" },
      { status: 500 },
    );
  }

  const verification = verifyTelegramWebAppInitDataWithAny(initData, botTokens);
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
