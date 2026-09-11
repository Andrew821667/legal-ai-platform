import { NextRequest } from "next/server";

import { parseRublesInput } from "@/lib/money";
import { corePatch } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Сумма к учёту у уже составленного договора.
 *
 * Нужно для договоров, составленных до того, как сумма появилась как число,
 * и для правок: текст документа не меняется, меняется только то, что
 * складывается в итоги.
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

  const body = (await request.json().catch(() => ({}))) as { amount?: unknown };
  const amount = parseRublesInput(body.amount);
  if (!amount.ok) {
    return Response.json({ detail: amount.detail }, { status: 400 });
  }

  return corePatch(`/api/v1/lawyer/agreements/${agreementId}/amount`, {
    amount_minor: amount.minor,
  });
}
