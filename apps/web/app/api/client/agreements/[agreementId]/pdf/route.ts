import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientQuery } from "@/lib/client-ref";
import { clientCoreGetFile } from "@/lib/client-core";

/** PDF своего договора — ядро само проверит, что он этого клиента и не черновик. */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, ctx: { params: Promise<{ agreementId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { agreementId } = await ctx.params;
  if (!UUID.test(agreementId)) return Response.json({ detail: "Договор не найден." }, { status: 404 });
  return clientCoreGetFile(
    `/api/v1/service-agreements/${agreementId}/pdf?${clientQuery(auth)}`,
  );
}
