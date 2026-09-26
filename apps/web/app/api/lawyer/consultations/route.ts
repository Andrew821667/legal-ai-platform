import { NextRequest } from "next/server";

import { coreGet, corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Время для консультаций: список записей и открытие нового времени. */

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  return coreGet("/api/v1/lawyer/consultations");
}

export async function POST(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const body = (await request.json().catch(() => ({}))) as { starts_at?: unknown; duration_min?: unknown };
  const starts = Array.isArray(body.starts_at) ? body.starts_at.map(String).slice(0, 60) : [];
  if (!starts.length) return Response.json({ detail: "Укажите дату и время." }, { status: 400 });
  const duration = Number(body.duration_min) || 60;
  return corePost("/api/v1/lawyer/consultations/slots", { starts_at: starts, duration_min: duration });
}
