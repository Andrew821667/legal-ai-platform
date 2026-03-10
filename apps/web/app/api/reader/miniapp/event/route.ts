import { NextRequest, NextResponse } from "next/server";
import { callReaderCore, ensureReaderKey } from "../../core";
import { ensureTelegramUserMatch, verifyMiniAppRequest } from "@/lib/telegram-webapp-auth";

export async function POST(request: NextRequest) {
  if (!ensureReaderKey()) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT/API_KEY_NEWS is not configured on web server" },
      { status: 500 },
    );
  }

  const auth = verifyMiniAppRequest(request);
  if (auth instanceof NextResponse) {
    return auth;
  }

  try {
    const payload = await request.json();
    const telegramUserId = Number(payload?.telegram_user_id);
    const eventType = String(payload?.event_type || "").trim();

    if (!Number.isFinite(telegramUserId) || telegramUserId <= 0) {
      return NextResponse.json({ detail: "telegram_user_id is required" }, { status: 400 });
    }
    if (!eventType) {
      return NextResponse.json({ detail: "event_type is required" }, { status: 400 });
    }
    const mismatch = ensureTelegramUserMatch(auth, telegramUserId);
    if (mismatch) {
      return mismatch;
    }

    const { response, data } = await callReaderCore("/api/v1/reader/miniapp/event", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || "Failed to record miniapp event" },
      { status: 500 },
    );
  }
}
