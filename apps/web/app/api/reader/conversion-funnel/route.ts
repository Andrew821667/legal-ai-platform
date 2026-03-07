import { NextRequest, NextResponse } from "next/server";
import { callReaderCoreCached, ensureReaderKey } from "../core";

export async function GET(request: NextRequest) {
  if (!ensureReaderKey()) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT/API_KEY_NEWS is not configured on web server" },
      { status: 500 },
    );
  }

  const hours = Number(request.nextUrl.searchParams.get("hours") || "168");
  if (!Number.isFinite(hours) || hours <= 0) {
    return NextResponse.json({ detail: "hours must be > 0" }, { status: 400 });
  }

  try {
    const { response, data, cacheState } = await callReaderCoreCached(
      `/api/v1/reader/conversion-funnel?hours=${encodeURIComponent(String(Math.floor(hours)))}`,
      { method: "GET" },
      { ttlMs: 15000, staleMs: 120000 },
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
      { detail: error?.message || "Failed to fetch conversion funnel" },
      { status: 500 },
    );
  }
}
