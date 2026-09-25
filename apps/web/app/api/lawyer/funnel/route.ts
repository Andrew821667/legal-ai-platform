import { NextRequest } from "next/server";

import { coreGet } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

export const dynamic = "force-dynamic";

const PERIODS = new Set([30, 90, 365]);

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  // Только периоды с экрана: в адрес ядра не попадает ничего, кроме числа.
  const requested = Number(request.nextUrl.searchParams.get("days"));
  const days = PERIODS.has(requested) ? requested : 90;
  return coreGet(`/api/v1/lawyer/funnel?days=${days}`);
}
