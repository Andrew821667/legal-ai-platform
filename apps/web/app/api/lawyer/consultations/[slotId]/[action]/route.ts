import { NextRequest } from "next/server";

import { corePost, TELEGRAM_DELIVERY_TIMEOUT_MS } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Подтвердить оплату, снять бронь, отметить чек или назначить согласованное время. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ACTIONS = new Set(["confirm", "release", "receipt", "schedule"]);

export async function POST(request: NextRequest, ctx: { params: Promise<{ slotId: string; action: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { slotId, action } = await ctx.params;
  if (!UUID.test(slotId) || !ACTIONS.has(action)) return Response.json({ detail: "Не найдено." }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { ref?: unknown; starts_at?: unknown };
  let payload: Record<string, unknown> = {};
  if (action === "receipt") payload = { ref: String(body.ref ?? "").trim().slice(0, 500) || null };
  if (action === "schedule") {
    const startsAt = String(body.starts_at ?? "");
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+03:00$/.test(startsAt)) {
      return Response.json({ detail: "Укажите дату и время." }, { status: 400 });
    }
    payload = { starts_at: startsAt };
  }
  // Подтверждение пишет клиенту в Telegram — ждём как у договора.
  return corePost(`/api/v1/lawyer/consultations/${slotId}/${action}`, payload, {
    timeoutMs: action === "confirm" || action === "schedule" ? TELEGRAM_DELIVERY_TIMEOUT_MS : undefined,
  });
}
