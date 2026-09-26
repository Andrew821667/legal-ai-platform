import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Черновик условий договора по обращению: ядро спрашивает модель и отдаёт
 * поля формы. Ничего не сохраняется — договор по-прежнему составляет юрист.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Модель в ядре ждёт до 90 с; обрыв раньше показал бы «ядро не ответило»,
// хотя ответ с черновиком ещё в пути.
const MODEL_TIMEOUT_MS = 100_000;

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

  return corePost(`/api/v1/lawyer/intakes/${intakeId}/terms-draft`, undefined, {
    timeoutMs: MODEL_TIMEOUT_MS,
  });
}
