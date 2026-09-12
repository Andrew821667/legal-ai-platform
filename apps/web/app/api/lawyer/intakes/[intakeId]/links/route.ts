import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Связать обращение с делом другого клиента.
 *
 * Найдено вживую: два обращения оказались одним и тем же имущественным
 * спором с двух сторон, а проверка конфликта у каждого шла независимо.
 * Связь — только пометка для контекста; договоры, NDA и документы каждого
 * обращения остаются раздельными.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ALLOWED_ROLES = new Set(["main", "subordinate", "joint"]);

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ intakeId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { intakeId } = await params;
  if (!UUID.test(intakeId)) {
    return Response.json({ detail: "Некорректный идентификатор обращения" }, { status: 400 });
  }

  const body = (await request.json().catch(() => ({}))) as {
    linked_lead_id?: unknown;
    role?: unknown;
    note?: unknown;
  };
  const linkedLeadId = String(body.linked_lead_id ?? "");
  if (!UUID.test(linkedLeadId)) {
    return Response.json({ detail: "Некорректный идентификатор клиента" }, { status: 400 });
  }
  const role = String(body.role ?? "");
  if (!ALLOWED_ROLES.has(role)) {
    return Response.json({ detail: "Неизвестная роль связи" }, { status: 400 });
  }
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 500) : undefined;

  return corePost(`/api/v1/lawyer/intakes/${intakeId}/links`, {
    linked_lead_id: linkedLeadId,
    role,
    ...(note ? { note } : {}),
  });
}
