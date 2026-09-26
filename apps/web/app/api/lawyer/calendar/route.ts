import { NextRequest, NextResponse } from "next/server";

import { buildIcs, verifyFeedToken } from "@/lib/calendar-feed";
import type { CalendarEvent } from "@/lib/calendar-feed";
import { coreGet } from "@/lib/lawyer-core";
import { allowedLawyerIds, lawyerSessionSecret } from "@/lib/lawyer-auth";
import { publicOrigin } from "@/lib/public-origin";

/**
 * Лента сроков для календаря телефона. Календарь приходит без куки и без
 * Telegram — пускает подпись в адресе (см. lib/calendar-feed). Юрист, которого
 * убрали из списка, теряет ленту сразу; смена LAWYER_SESSION_SECRET отзывает
 * все выданные адреса.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// На любой отказ — одинаковый 404: адрес либо рабочий, либо его нет.
const notFound = () => new NextResponse("Not found", { status: 404 });

export async function GET(request: NextRequest) {
  const lawyerId = Number(request.nextUrl.searchParams.get("u"));
  const token = request.nextUrl.searchParams.get("t") || "";
  if (!Number.isSafeInteger(lawyerId) || !allowedLawyerIds().includes(lawyerId)) return notFound();
  if (!verifyFeedToken(lawyerSessionSecret(), lawyerId, token)) return notFound();

  const core = await coreGet("/api/v1/lawyer/calendar");
  if (!core.ok) return new NextResponse("Calendar is temporarily unavailable", { status: 503 });
  const { events } = (await core.json()) as { events: CalendarEvent[] };
  const ics = buildIcs(events || [], { now: new Date(), origin: publicOrigin(request.headers, request.nextUrl.host) });
  return new NextResponse(ics, {
    headers: {
      "content-type": "text/calendar; charset=utf-8",
      "content-disposition": 'inline; filename="ai-verdict-sroki.ics"',
      "cache-control": "private, no-store",
      // Адрес с секретом не должен уходить в Referer со ссылок в событиях.
      "referrer-policy": "no-referrer",
    },
  });
}
