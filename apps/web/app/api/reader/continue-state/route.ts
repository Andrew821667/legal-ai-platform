import { NextRequest, NextResponse } from "next/server";
import { callReaderCoreCached, ensureReaderKey } from "../core";
import { ensureTelegramUserMatch, verifyMiniAppRequest } from "@/lib/telegram-webapp-auth";

export async function GET(request: NextRequest) {
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

  const telegramUserIdRaw = String(request.nextUrl.searchParams.get("telegram_user_id") || "").trim();
  if (!telegramUserIdRaw) {
    return NextResponse.json({ detail: "telegram_user_id is required" }, { status: 400 });
  }
  const telegramUserId = Number(telegramUserIdRaw);
  if (!Number.isFinite(telegramUserId) || telegramUserId <= 0) {
    return NextResponse.json({ detail: "telegram_user_id must be a positive integer" }, { status: 400 });
  }
  const mismatch = ensureTelegramUserMatch(auth, telegramUserId);
  if (mismatch) {
    return mismatch;
  }

  try {
    const { response, data, cacheState } = await callReaderCoreCached(
      `/api/v1/reader/continue-state?telegram_user_id=${encodeURIComponent(String(telegramUserId))}`,
      { method: "GET" },
      { ttlMs: 10000, staleMs: 120000 },
    );
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }
    const headers: Record<string, string> = {};
    if (cacheState === "hit" || cacheState === "stale") {
      headers["X-Reader-Core-Cache"] = cacheState;
    }
    return NextResponse.json(data, { headers });
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || "Failed to fetch continue state" },
      { status: 500 },
    );
  }
}
