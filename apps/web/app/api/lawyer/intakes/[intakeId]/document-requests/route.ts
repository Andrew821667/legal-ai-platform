import { NextRequest } from "next/server";

import { collectTitles } from "@/lib/document-requests";
import { corePost, TELEGRAM_DELIVERY_TIMEOUT_MS } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Запросить у клиента документы списком: ядро сохранит список и напишет клиенту. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ intakeId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { intakeId } = await params;
  if (!UUID.test(intakeId)) {
    return Response.json({ detail: "Некорректный идентификатор обращения" }, { status: 400 });
  }
  const body = (await request.json().catch(() => ({}))) as { titles?: unknown; note?: unknown };
  const titles = collectTitles(Array.isArray(body.titles) ? body.titles.map(String) : [], "");
  if (!titles.length) {
    return Response.json({ detail: "Отметьте или впишите хотя бы один документ." }, { status: 400 });
  }
  const note = String(body.note ?? "").trim().slice(0, 1000) || null;
  // Ядро само пишет клиенту в Telegram — ждём столько же, сколько у договора.
  return corePost(`/api/v1/lawyer/intakes/${intakeId}/document-requests`, { titles, note }, {
    timeoutMs: TELEGRAM_DELIVERY_TIMEOUT_MS,
  });
}
