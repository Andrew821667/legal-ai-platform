import { NextRequest } from "next/server";

import { coreDelete, corePut } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Изменить заготовку условий договора (в том числе привязку к пакету сайта) или удалить её. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const PRACTICES = new Set(["legal", "engineering", "hybrid"]);

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ templateId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { templateId } = await params;
  if (!UUID.test(templateId)) {
    return Response.json({ detail: "Некорректный идентификатор заготовки" }, { status: 400 });
  }
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const practice = typeof body.practice === "string" && PRACTICES.has(body.practice) ? body.practice : null;
  return corePut(`/api/v1/lawyer/agreement-templates/${templateId}`, { ...body, practice });
}

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
