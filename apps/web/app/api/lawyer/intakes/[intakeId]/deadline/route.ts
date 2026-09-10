import { NextRequest } from "next/server";

import { corePatch } from "@/lib/lawyer-core";
import { normalizeDeadline } from "@/lib/intake-deadline";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Календарный срок по обращению.
 *
 * Слова клиента о сроке лежат отдельно и не меняются: «к этому четвергу» —
 * это то, что он сказал, а дата — то, что юрист из этого понял.
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

  const body = (await request.json().catch(() => ({}))) as { deadline_at?: unknown };
  const deadline = normalizeDeadline(body.deadline_at);
  if (!deadline.ok) {
    return Response.json({ detail: deadline.detail }, { status: 400 });
  }

  return corePatch(`/api/v1/legal-intakes/${intakeId}`, { deadline_at: deadline.value });
}
