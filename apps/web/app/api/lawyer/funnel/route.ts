import { NextRequest, NextResponse } from "next/server";

import { coreGet } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";
import { createStatsCache, loadSiteStats, metrikaConfig } from "@/lib/metrika-funnel";

export const dynamic = "force-dynamic";

const PERIODS = new Set([30, 90, 365]);

// Один на процесс сайта: воронку открывают часто, а Метрика меняется медленно.
const siteStatsCache = createStatsCache();

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  // Только периоды с экрана: в адрес ядра не попадает ничего, кроме числа.
  const requested = Number(request.nextUrl.searchParams.get("days"));
  const days = PERIODS.has(requested) ? requested : 90;

  // Метрика — дополнение: её сбой или отсутствие токена не прячет воронку.
  const [core, site] = await Promise.all([
    coreGet(`/api/v1/lawyer/funnel?days=${days}`),
    siteStatsCache(String(days), () => loadSiteStats(metrikaConfig(process.env), days)),
  ]);
  if (!core.ok) return core;
  const funnel = (await core.json()) as Record<string, unknown>;
  return NextResponse.json({ ...funnel, site });
}
