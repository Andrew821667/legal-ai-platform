import { NextRequest, NextResponse } from "next/server";

import { requireAdminSession } from "@/lib/admin-session";
import { loadYandexAnalyticsPayload } from "@/lib/analytics/yandex";

export async function GET(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  const payload = await loadYandexAnalyticsPayload();
  const status = payload.error ? 500 : 200;
  return NextResponse.json(payload, { status });
}
