import { NextRequest } from "next/server";

import { corePost, TELEGRAM_DELIVERY_TIMEOUT_MS } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Чек из «Мой налог» по оплаченному акту: записать и, если надо, отправить
 * клиенту. Самозанятый обязан передать чек покупателю — в том числе ссылкой.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ actId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { actId } = await params;
  if (!UUID.test(actId)) {
    return Response.json({ detail: "Некорректный идентификатор акта" }, { status: 400 });
  }
  const body = (await request.json().catch(() => ({}))) as { ref?: unknown; send_to_client?: unknown };
  const ref = typeof body.ref === "string" && body.ref.trim() ? body.ref.trim().slice(0, 500) : null;
  return corePost(
    `/api/v1/work-acts/${actId}/receipt`,
    { ref, send_to_client: body.send_to_client === true },
    { timeoutMs: TELEGRAM_DELIVERY_TIMEOUT_MS },
  );
}
