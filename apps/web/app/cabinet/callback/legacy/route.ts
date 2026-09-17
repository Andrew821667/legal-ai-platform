import { NextRequest, NextResponse } from "next/server";

import { establishClientSession } from "../../_lib/establish-session";
import { publicOrigin } from "@/lib/public-origin";
import { verifyTelegramLoginWidget } from "@/lib/telegram-login-legacy";
import { telegramLoginMode } from "@/lib/telegram-login-mode";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Callback legacy iframe-виджета (telegram-widget.js): Telegram сам делает
 * GET-редирект сюда с data-auth-url, без промежуточного JS-обработчика.
 * next не поддерживается — виджет не умеет пронести произвольное состояние
 * через свой редирект, поэтому всегда возвращаем в /cabinet.
 */
export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);

  if (telegramLoginMode() !== "legacy") {
    return NextResponse.redirect(new URL("/cabinet?login=misconfigured", origin));
  }

  const botToken = (process.env.LEAD_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "").trim();
  const profile = verifyTelegramLoginWidget(request.nextUrl.searchParams, botToken);
  if (!profile) {
    return NextResponse.redirect(new URL("/cabinet?login=token", origin));
  }

  return establishClientSession(profile, request, "/cabinet");
}
