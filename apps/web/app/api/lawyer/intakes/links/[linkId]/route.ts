import { NextRequest } from "next/server";

import { coreDelete } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Снять связь между обращениями. Обе стороны равноправны — годится id связи с любого конца. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ linkId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { linkId } = await params;
  if (!UUID.test(linkId)) {
    return Response.json({ detail: "Некорректный идентификатор связи" }, { status: 400 });
  }

  return coreDelete(`/api/v1/lawyer/intakes/links/${linkId}`);
}
