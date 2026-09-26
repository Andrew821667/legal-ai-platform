import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientQuery } from "@/lib/client-ref";
import { clientCoreGetFile } from "@/lib/client-core";

/** Платёжный QR своего акта — ядро само проверит, что акт этого клиента и ждёт оплаты. */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, ctx: { params: Promise<{ actId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { actId } = await ctx.params;
  if (!UUID.test(actId)) return Response.json({ detail: "Акт не найден." }, { status: 404 });
  return clientCoreGetFile(`/api/v1/work-acts/${actId}/payment-qr?${clientQuery(auth)}`);
}
