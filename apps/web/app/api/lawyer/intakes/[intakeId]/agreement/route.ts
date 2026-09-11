import { NextRequest } from "next/server";

import { checkAgreementDraft } from "@/lib/agreement-draft";
import { parseRublesInput } from "@/lib/money";
import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Составление договора по обращению.
 *
 * Раньше этот мастер жил только в переписке с ботом: рабочее место показывало
 * «условия ещё не предложены» и отправляло составлять их в другое место.
 * Кто составил — берём из проверенной сессии, а не из тела запроса.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Столько же, сколько предлагает мастер в боте: два входа в один документ не
// должны давать разный срок жизни предложения.
const EXPIRES_IN_DAYS = 7;

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

  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const draft = checkAgreementDraft(body);
  if (!draft.ok) {
    return Response.json({ detail: draft.detail }, { status: 400 });
  }
  // Сумма к учёту — отдельно от формулировки в документе: по тексту итоги
  // не сложить, а число без формулировки в договор не положить.
  const amount = parseRublesInput(body.amount);
  if (!amount.ok) {
    return Response.json({ detail: amount.detail }, { status: 400 });
  }

  return corePost("/api/v1/service-agreements", {
    ...draft.value,
    amount_minor: amount.minor,
    intake_id: intakeId,
    prepared_by_telegram_user_id: auth.telegramUserId,
    expires_in_days: EXPIRES_IN_DAYS,
  });
}
