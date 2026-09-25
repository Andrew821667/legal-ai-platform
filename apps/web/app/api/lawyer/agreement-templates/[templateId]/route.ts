import { NextRequest } from "next/server";

import { coreDelete } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Удалить заготовку условий договора. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ templateId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { templateId } = await params;
  if (!UUID.test(templateId)) {
    return Response.json({ detail: "Некорректный идентификатор заготовки" }, { status: 400 });
  }
  return coreDelete(`/api/v1/lawyer/agreement-templates/${templateId}`);
}
