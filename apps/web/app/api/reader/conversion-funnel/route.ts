import { NextRequest, NextResponse } from "next/server";
import { callReaderCore, ensureReaderKey } from "../core";

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

  const { response, data } = await callReaderCore(
    `/api/v1/reader/conversion-funnel?hours=${encodeURIComponent(String(Math.floor(hours)))}`,
  );
  if (!response.ok) {
    return NextResponse.json(data, { status: response.status });
  }
  return NextResponse.json(data);
}

