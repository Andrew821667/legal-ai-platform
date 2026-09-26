import { NextRequest, NextResponse } from "next/server";

import { feedUrls } from "@/lib/calendar-feed";
import { lawyerSessionSecret, requireLawyer } from "@/lib/lawyer-auth";
import { publicOrigin } from "@/lib/public-origin";

/** Адрес подписки на сроки — только вошедшему юристу и только его собственный. */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const secret = lawyerSessionSecret();
  if (!secret) {
    return NextResponse.json({ detail: "Сервер не настроен: нет LAWYER_SESSION_SECRET" }, { status: 500 });
  }
  const origin = process.env.NEXT_PUBLIC_SITE_URL || publicOrigin(request.headers, request.nextUrl.host);
  return NextResponse.json(feedUrls(origin, auth.telegramUserId, secret), {
    headers: { "cache-control": "no-store" },
  });
}
