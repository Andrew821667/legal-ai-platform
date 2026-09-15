import { NextRequest } from "next/server";

import { parseIntakeLinkPayload } from "@/lib/intake-link-payload";
import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Связать обращение с делом другого клиента.
 *
 * Найдено вживую: два обращения оказались одним и тем же имущественным
 * спором с двух сторон, а проверка конфликта у каждого шла независимо.
 * Связь — только пометка для контекста; договоры, NDA и документы каждого
 * обращения остаются раздельными.
 *
 * У клиента может быть несколько дел — тогда ядро требует указать конкретное
 * (linked_intake_id), иначе отвечает 409, и форма предлагает выбрать.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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

  const parsed = parseIntakeLinkPayload(await request.json().catch(() => ({})));
  if (!parsed.ok) {
    return Response.json({ detail: parsed.error }, { status: 400 });
  }
  return corePost(`/api/v1/lawyer/intakes/${intakeId}/links`, parsed.payload);
}
