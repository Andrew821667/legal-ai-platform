import { NextRequest, NextResponse } from "next/server";

import {
  getMiniAppBotTokens,
  TELEGRAM_INIT_DATA_HEADER,
  verifyTelegramWebAppInitDataWithAny,
} from "./telegram-initdata";

export type ClientContext = { telegramUserId: number };

export function requireClient(request: NextRequest): ClientContext | NextResponse {
  const initData = (request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "").trim();
  const tokens = getMiniAppBotTokens();
  if (!initData || tokens.length === 0) {
    return NextResponse.json(
      { detail: "Откройте кабинет из бота-ассистента." },
      { status: 401 },
    );
  }
  const auth = verifyTelegramWebAppInitDataWithAny(initData, tokens);
  if (!auth) {
    return NextResponse.json(
      { detail: "Сеанс Telegram истёк. Закройте Mini App и откройте его снова из бота." },
      { status: 401 },
    );
  }
  return { telegramUserId: auth.telegramUserId };
}
