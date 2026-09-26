import { NextRequest } from "next/server";

import { coreDelete } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Закрыть свободное время. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function DELETE(request: NextRequest, ctx: { params: Promise<{ slotId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { slotId } = await ctx.params;
  if (!UUID.test(slotId)) return Response.json({ detail: "Время не найдено." }, { status: 404 });
  return coreDelete(`/api/v1/lawyer/consultations/slots/${slotId}`);
}
