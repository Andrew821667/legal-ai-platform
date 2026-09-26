import { NextRequest } from "next/server";

import { corePost, TELEGRAM_DELIVERY_TIMEOUT_MS } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Подтвердить оплату, снять бронь или отметить чек за консультацию. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ACTIONS = new Set(["confirm", "release", "receipt"]);

export async function POST(request: NextRequest, ctx: { params: Promise<{ slotId: string; action: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { slotId, action } = await ctx.params;
  if (!UUID.test(slotId) || !ACTIONS.has(action)) return Response.json({ detail: "Не найдено." }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { ref?: unknown };
  const payload = action === "receipt" ? { ref: String(body.ref ?? "").trim().slice(0, 500) || null } : {};
  // Подтверждение пишет клиенту в Telegram — ждём как у договора.
  return corePost(`/api/v1/lawyer/consultations/${slotId}/${action}`, payload, {
    timeoutMs: action === "confirm" ? TELEGRAM_DELIVERY_TIMEOUT_MS : undefined,
  });
}
