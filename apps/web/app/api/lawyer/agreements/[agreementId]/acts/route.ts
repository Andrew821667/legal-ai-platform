import { NextRequest } from "next/server";

import { parseRublesInput } from "@/lib/money";
import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Акт выполненных работ по подписанному договору.
 *
 * Юрист сам заполняет текст и сумму — обычно оставляя предмет договора как
 * есть, но акт описывает, что фактически сделано, и может от него
 * отличаться. Ядро само откажет, если договор ещё не подписан.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ agreementId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { agreementId } = await params;
  if (!UUID.test(agreementId)) {
    return Response.json({ detail: "Некорректный идентификатор договора" }, { status: 400 });
  }

  const body = (await request.json().catch(() => ({}))) as {
    description_text?: unknown;
    amount?: unknown;
  };
  const description = String(body.description_text ?? "").trim();
  if (description.length < 2) {
    return Response.json({ detail: "Опишите, что сделано." }, { status: 400 });
  }
  const amount = parseRublesInput(body.amount);
  if (!amount.ok) {
    return Response.json({ detail: amount.detail }, { status: 400 });
  }
  if (amount.minor === null) {
    return Response.json({ detail: "Укажите сумму к оплате." }, { status: 400 });
  }

  return corePost("/api/v1/work-acts", {
    agreement_id: agreementId,
    description_text: description,
    amount_minor: amount.minor,
    prepared_by_telegram_user_id: auth.telegramUserId,
  });
}
