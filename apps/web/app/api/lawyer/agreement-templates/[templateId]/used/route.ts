import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Заготовку подставили в форму — поднять её в списке. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ templateId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { templateId } = await params;
  if (!UUID.test(templateId)) {
    return Response.json({ detail: "Некорректный идентификатор заготовки" }, { status: 400 });
  }
  return corePost(`/api/v1/lawyer/agreement-templates/${templateId}/used`);
}
