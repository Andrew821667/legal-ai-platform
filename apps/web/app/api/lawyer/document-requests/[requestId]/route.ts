import { NextRequest } from "next/server";

import { corePatch } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Отметка по пункту запроса: получен, не нужен или снова ждём. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STATUSES = new Set(["open", "received", "cancelled"]);

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ requestId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { requestId } = await params;
  if (!UUID.test(requestId)) {
    return Response.json({ detail: "Некорректный идентификатор пункта" }, { status: 400 });
  }
  const body = (await request.json().catch(() => ({}))) as { status?: unknown; document_id?: unknown };
  const status = String(body.status ?? "");
  if (!STATUSES.has(status)) {
    return Response.json({ detail: "Неизвестная отметка" }, { status: 400 });
  }
  const documentId = typeof body.document_id === "string" && UUID.test(body.document_id) ? body.document_id : null;
  return corePatch(`/api/v1/lawyer/document-requests/${requestId}`, { status, document_id: documentId });
}
