import { NextRequest } from "next/server";

import { coreGet, corePost, TELEGRAM_DELIVERY_TIMEOUT_MS } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Переписка с клиентом по делу: прочитать и ответить (кабинет клиента и его Telegram). */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, { params }: { params: Promise<{ leadId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { leadId } = await params;
  if (!UUID.test(leadId)) return Response.json({ detail: "Некорректный идентификатор клиента" }, { status: 400 });
  return coreGet(`/api/v1/lawyer/clients/${leadId}/messages`);
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ leadId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { leadId } = await params;
  if (!UUID.test(leadId)) return Response.json({ detail: "Некорректный идентификатор клиента" }, { status: 400 });
  const body = (await request.json().catch(() => null)) as { text?: unknown; intake_id?: unknown } | null;
  const text = typeof body?.text === "string" ? body.text.trim().slice(0, 4000) : "";
  if (!text) return Response.json({ detail: "Напишите ответ." }, { status: 400 });
  const intakeId = typeof body?.intake_id === "string" && UUID.test(body.intake_id) ? body.intake_id : undefined;
  // Ответ уходит клиенту и в Telegram — ждём, как у договора.
  return corePost(`/api/v1/lawyer/clients/${leadId}/messages`, { text, ...(intakeId ? { intake_id: intakeId } : {}) }, {
    timeoutMs: TELEGRAM_DELIVERY_TIMEOUT_MS,
  });
}
