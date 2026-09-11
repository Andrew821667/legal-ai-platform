import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Отправляет акт клиенту — ядро само шлёт сообщение в Telegram (тот же
 * приём, что у /agreements/{id}/deliver): единственное место доставки для
 * бота и рабочего места, а не две копии текста в разных местах.
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

  return corePost(`/api/v1/work-acts/${actId}/send`);
}
