import { NextRequest, NextResponse } from "next/server";
import { callReaderCore, callReaderCoreCached, ensureReaderKey } from "../../core";

export async function GET(request: NextRequest) {
  if (!ensureReaderKey()) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT/API_KEY_NEWS is not configured on web server" },
      { status: 500 },
    );
  }

  const telegramUserId = String(request.nextUrl.searchParams.get("telegram_user_id") || "").trim();
  if (!telegramUserId) {
    return NextResponse.json({ detail: "telegram_user_id is required" }, { status: 400 });
  }

  try {
    const { response, data, cacheState } = await callReaderCoreCached(
      `/api/v1/reader/miniapp/profile?telegram_user_id=${encodeURIComponent(telegramUserId)}`,
      { method: "GET" },
      { ttlMs: 12000, staleMs: 180000 },
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
      { detail: error?.message || "Failed to fetch miniapp profile" },
      { status: 500 },
    );
  }
}

export async function PATCH(request: NextRequest) {
  if (!ensureReaderKey()) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT/API_KEY_NEWS is not configured on web server" },
      { status: 500 },
    );
  }

  try {
    const payload = await request.json();
    const telegramUserId = Number(payload?.telegram_user_id);
    if (!Number.isFinite(telegramUserId) || telegramUserId <= 0) {
      return NextResponse.json({ detail: "telegram_user_id is required" }, { status: 400 });
    }

    const { response, data } = await callReaderCore("/api/v1/reader/miniapp/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || "Failed to update miniapp profile" },
      { status: 500 },
    );
  }
}
